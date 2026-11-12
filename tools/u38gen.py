#!/usr/bin/env python3
"""Ultra-38 source generator (phase B2): TSB Neo's source with every crossing routed through the layout-H stubs.

Usage: u38gen.py b21 <outdir>      B2.1 speed spike: TSB Neo stays in RAM at $8000-$CFFF, same addresses
                                   (every replacement has the size of what it replaces); thunks, common block and
                                   the RAM core image at $6000-$7FFF; MEMSIZ $6000.
       u38gen.py report             print the classification (what is routed where) and the hot-helper closure.

What is routed (reports/B2-spike.md, "B2.1"):
  - JSR to the BASIC ROM ($A000-$BFFF, and the BASIC part of the KERNAL ROM $E000-$E4D2) -> RC thunk
  - JMP to those -> RX thunk (exit); JMP ($A002) -> RX to $E37B
  - JSR/JMP between Neo's regions $8000-$9FFF (core, bank 1), $A000-$BFFF (commands, bank 2) and
    $C000-$CFFF (bank 4) -> FC/FJ thunk (far call / far jump), unless the target lies in the closure of the hot
    helpers (copied into every bank in layout H, so the call stays in the bank)
  - command dispatch table entries (sprtab, RTS dispatch) to another region -> FJ thunk
  - jsr basromein / jsr basromaus -> "lda #$36 : nop" (4 cycles, same size, A = the port value Neo expects);
    jmp basromein/aus -> lda #$36 : rts
  - the six BASIC vectors, LOAD/SAVE, IRQ, NMI, BRK -> entry stubs in $DFxx
  - TSB's ROM-call helper pspeibe (jsr $54) -> RC through the target in $55/$56
  - reads of the BASIC ROM's error table $A326/$A327 -> read helper (cold)
"""
import collections, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import neoinventory, neoprofile  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "TSBneo", "tsbneo.a")
BANK = {"8000": 1, "A000": 2, "C000": 4}
# B1 hot helpers (tools/ultra38model.py over tests/bench): copied into every bank in layout H
HOT = ["vglae", "kerromaus", "inca6a7", "mkline", "endsmb", "l20pl40", "l23pl40", "incbasbz", "bef0", "sfrmevl",
       "sgetbytc", "sgetadr", "cgoto1", "sgoto1", "basromaus", "cgoto0", "a8a9bogm"]
COPY_MAX = int(os.environ.get("U38_COPY_MAX", "32"))
# port helpers: KERNAL/char ROM on/off become RAM helpers or disappear in layout H; never a far call
PORTH = ["kerromein", "kerromaus", "charen0", "charen1"]
# jsr basromein/basromaus -> "lda #$36 : nop": 3 bytes, 4 cycles. TSB code always runs with $36 in layout H, and
# Neo uses the port value these helpers leave in A (dispatch: sta portspei, restored later by prestor).
NOP3 = "lda #$36\t; u38: was jsr basromein/aus\n\tnop"
# BASIC ROM jump targets that never return to the jumper's caller (true exits): main loop, NEWSTT, GONE,
# READY, error output, LIST loop, warm start; $B2EA takes arguments its caller pushed (PLACE on arrays)
NONRET = {0xA474, 0xA7AE, 0xA7E7, 0xA483, 0xA486, 0xA43A, 0xA447, 0xAF08, 0xE386, 0xE37B, 0xA6F6, 0xA71A, 0xB2EA,
          0xA437, 0xE0F9}
# BASIC routines that reset the stack (CLR keeps one return address, SP = $FA): RCS thunk
SPRESET = {0xA655, 0xA659, 0xA660, 0xE422}
# KERNAL entries that go through TSB's LOAD/SAVE vectors: called in BASIC state (RC)
KVEC = {0xFFD5, 0xFFD8}      # NOP abs ($0C): 3 bytes, 4 cycles, no flags, reads $EAEA (RAM)


def is_basic(t):
    return 0xA000 <= t < 0xC000 or 0xE000 <= t < 0xE4D3


ROW = re.compile(r"^\s*(\d+)\s+([0-9a-f]{4})\s+([0-9a-f]+)(\.\.\.)?\s*(.*)$")


def rows_all(rep):
    """Report rows: list of (file, line, addr, bytes (maybe truncated), src); and labels {name: addr}."""
    out, cur, labels = [], None, {}
    for raw in open(rep, encoding="latin-1"):
        m = re.match(r"^; \*+ Source: (.*)$", raw.strip())
        if m: cur = m.group(1); continue
        m = ROW.match(raw.rstrip("\n"))
        if not m: continue
        src = m.group(5)
        lab = re.match(r"^([A-Za-z_][\w.]*)", src)
        if lab and lab.group(1) not in neoinventory.OPS_MN: labels.setdefault(lab.group(1), int(m.group(2), 16))
        out.append((cur, int(m.group(1)), int(m.group(2), 16), bytes.fromhex(m.group(3)), src))
    return out, labels


def rows_main(rep):
    rows, _ = rows_all(rep)
    return [r[1:] for r in rows if r[0] == "tsbneo.a"]


def decode(rows, labels, equ=()):
    """Instructions of the main file: dicts like neoinventory's, plus 'kind' of the operand."""
    ins = []
    for lno, addr, hexb, src in rows:
        code = src.split(";")[0]
        lab = re.match(r"^([A-Za-z_][\w.]*)", code)
        stmt = code[lab.end():] if lab and lab.group(1) not in neoinventory.OPS_MN else code
        stmt = re.sub(r"^\s*[+-]*\s*", "", stmt).strip()
        mm = re.match(r"^([a-z]{3})\b\s*(.*)$", stmt)
        if not mm or not hexb or hexb[0] not in neoinventory.OPS: continue
        mn, mode = neoinventory.OPS[hexb[0]]
        if mn != mm.group(1) or len(hexb) != neoinventory.MODES[mode]: continue
        opnd = mm.group(2).strip()
        val = hexb[1] | (hexb[2] << 8) if len(hexb) == 3 else (hexb[1] if len(hexb) == 2 else None)
        t = re.match(r"^\(?\s*([$%]?[\w.]+)", opnd)
        if re.match(r"^[+-]+$", opnd): kind = "label"
        elif not t: kind = "expr"
        elif t.group(1).startswith("$") or t.group(1).isdigit(): kind = "literal"
        elif t.group(1) in equ: kind = "equate"
        elif t.group(1) in labels: kind = "label"
        else: kind = "equate"
        ins.append(dict(line=lno, addr=addr, mn=mn, mode=mode, val=val, opnd=opnd, kind=kind, src=src, len=len(hexb)))
    return ins


def closure(ins, start_addrs, region=None):
    """Addresses reachable from start_addrs inside the same region (fall-through, branches, jsr/jmp)."""
    region = region or neoinventory.region
    by = {i["addr"]: k for k, i in enumerate(ins)}
    seen, todo = set(), list(start_addrs)
    while todo:
        a = todo.pop()
        reg = region(a)
        while a in by and a not in seen and region(a) == reg:
            seen.add(a); i = ins[by[a]]
            if i["mode"] == "rel":
                off = i["val"] - 256 if i["val"] >= 128 else i["val"]
                todo.append(a + 2 + off)
            if i["mn"] in ("jsr", "jmp") and i["mode"] == "abs" and i["kind"] == "label" \
                    and region(i["val"]) == reg:
                todo.append(i["val"])
            if i["mn"] in ("rts", "rti") or (i["mn"] == "jmp"): break
            nk = by[a] + 1
            if nk >= len(ins): break
            a = ins[nk]["addr"]
    return seen


class Gen:
    region = staticmethod(neoinventory.region)
    bank = BANK
    flash = False

    def __init__(self):
        self.rep = neoprofile.report()
        self.equ, labs, _ = neoinventory.parse(self.rep)
        lbl = self.rep[:-4] + ".lbl"
        if not os.path.exists(lbl) or os.path.getmtime(lbl) < os.path.getmtime(SRC):
            import subprocess
            subprocess.check_call([os.environ.get("ACME", "acme"), "-f", "plain", "-o", self.rep[:-4] + ".bin", "-l", lbl,
                                   "tsbneo.a"], cwd=os.path.join(ROOT, "TSBneo"))
        self.labels = {}
        for ln in open(lbl):
            m = re.match(r"\s*([A-Za-z_][\w.]*)\s*=\s*\$([0-9a-fA-F]+)", ln)
            if m: self.labels[m.group(1)] = int(m.group(2), 16)
        self.rows = rows_main(self.rep)
        self.ins = decode(self.rows, self.labels, self.equ)
        self.addr2label = {}
        for n, a in self.labels.items(): self.addr2label.setdefault(a, n)
        self.hot = closure(self.ins, region=self.region, start_addrs=[self.labels[h] for h in HOT + PORTH])
        # plus every helper that is called across regions and is at most COPY_MAX bytes with everything it reaches
        # in its own region (B2.1 finding: DO's search calls inc20 once per program byte)
        by = {i["addr"]: i for i in self.ins}
        for t in {i["val"] for i in self.ins if i["mn"] in ("jsr", "jmp") and i["mode"] == "abs"
                  and i["kind"] == "label" and self.region(i["addr"]) != self.region(i["val"])
                  and "other" not in (self.region(i["addr"]), self.region(i["val"]))}:
            c = closure(self.ins, region=self.region, start_addrs=[t])
            if sum(by[a]["len"] for a in c if a in by) <= COPY_MAX: self.hot |= c
        self.lines = open(SRC, encoding="latin-1").read().split("\n")
        self.edits = {}          # line number -> new text
        self.rc, self.rx, self.fc, self.fj = {}, {}, {}, {}   # name -> target / (target, bank)
        self.rt, self.rcs, self.ft, self.mixed = {}, {}, {}, set()
        self.notes = collections.Counter()

    def name_of(self, a):
        return self.addr2label.get(a) or "L%04x" % a

    # --- line editing (size-preserving) ---------------------------------------------------------------
    def sub_operand(self, line, old_mn, new_text):
        s = self.edits.get(line, self.lines[line - 1])
        code, sep, com = s.partition(";")
        m = re.search(r"\b%s\b\s*[^\s;]+" % old_mn, code)
        assert m, (line, s)
        code = code[:m.start()] + new_text + code[m.end():]
        self.edits[line] = code + sep + com

    def classify(self):
        """Edits for the B2.1/B2.2 transformation."""
        L = self.labels
        sprtab = L["sprtab"]
        for i in self.ins:
            reg = self.region(i["addr"])
            if reg == "other": continue
            if i["mn"] in ("jsr", "jmp") and i["mode"] == "abs":
                t = i["val"]
                if i["kind"] in ("literal", "equate") and (is_basic(t) or t == 0x7400 or t in KVEC):
                    if t in SPRESET:
                        n = "rcs_%04x" % t; self.rcs[n] = t; self.notes["stack-resetting BASIC routine -> RCS"] += 1
                    elif i["mn"] == "jsr":
                        n = "rc_%04x" % t; self.rc[n] = t; self.notes["rom jsr -> RC"] += 1
                    elif t in NONRET or self.labels["sgetari"] <= i["addr"] < self.labels["sgetari"] + 0x20:
                        # (sgetari's V2 exits: the IEVAL handler itself, entered from EVAL; no ev_ret frame there)
                        n = "rx_%04x" % t; self.rx[n] = t; self.notes["rom jmp (no return) -> RX"] += 1
                    else:
                        self.rc["rc_%04x" % t] = t
                        n = "rt_%04x" % t; self.rt[n] = t; self.notes["rom jmp (tail call) -> RT"] += 1
                    self.sub_operand(i["line"], i["mn"], "%s %s" % (i["mn"], n))
                elif i["kind"] in ("literal", "equate") and t in (0xF4A5, 0xF5ED) and \
                        self.labels["sysload"] <= i["addr"] <= self.labels["syssave"] + 8:
                    n = "rx_%04x" % t; self.rx[n] = t; self.notes["LOAD/SAVE vector handler exit -> RX"] += 1
                    self.sub_operand(i["line"], i["mn"], "%s %s" % (i["mn"], n))
                elif i["kind"] == "label" and i["opnd"] in ("basromein", "basromaus"):
                    if i["mn"] == "jsr":
                        self.set_insn(i, NOP3); self.notes["jsr basromein/aus removed"] += 1
                    else:
                        self.set_insn(i, "lda #$36\n\trts"); self.notes["jmp basromein/aus -> rts"] += 1
                elif i["kind"] == "label" and self.region(t) not in (reg, "other") and t not in self.hot \
                        and self.bank.get(self.region(t)) is not None:
                    tb = self.bank[self.region(t)]
                    nm = self.name_of(t)
                    if i["mn"] == "jsr":
                        n = "fc_%s" % nm; self.fc[n] = (t, tb, self.bank.get(reg)); self.notes["cross jsr -> FC"] += 1
                    elif self.flash and self.returns(t) == {"rts"}:
                        # tail call into a routine that returns: far call + rts (a far jump would return in the
                        # wrong bank)
                        self.fc["fc_%s" % nm] = (t, tb, self.bank.get(reg))
                        n = "ft_%s" % nm; self.ft[n] = (t, tb); self.notes["cross jmp to a returning routine -> FT"] += 1
                    else:
                        n = "fj_%s" % nm; self.fj[n] = (t, tb); self.notes["cross jmp -> FJ"] += 1
                        if self.flash and "rts" in self.returns(t): self.mixed.add(nm)
                    self.sub_operand(i["line"], i["mn"], "%s %s" % (i["mn"], n))
                elif i["kind"] == "label" and self.region(t) not in (reg, "other"):
                    self.notes["cross call to a hot helper (stays in bank)"] += 1
            if i["mn"] == "jmp" and i["mode"] == "ind" and i["val"] == 0xA002:
                self.rx["rx_e37b"] = 0xE37B
                self.set_insn(i, "jmp rx_e37b"); self.notes["jmp ($a002) -> RX $e37b"] += 1
            if i["mn"] == "jsr" and i["val"] == 0x54:   # pspeibe: ROM call through $54
                self.set_insn(i, "jsr rc_help"); self.notes["pspeibe jsr $54 -> RC"] += 1
            if i["mn"] == "lda" and i["mode"] == "abx" and i["val"] in (0xA326, 0xA327):
                self.set_insn(i, "jsr romrd_%04x" % i["val"]); self.notes["ROM table read -> helper"] += 1
        # tsberrs prints a message whose text may be in the BASIC ROM ($22/$23 from the $A326 table): ROM read helper
        t = [i for i in self.ins if i["addr"] == L["tsberrs"]][0]
        assert t["src"].startswith("tsberrs\tldy #0")
        self.set_insn(t, "jmp tsberrs_u38\n\t!byte $ea")
        self.set_insn([i for i in self.ins if i["addr"] == L["tsberrs"] + 2][0], "")
        self.notes["tsberrs (ROM message text) -> helper"] += 1
        # IEVAL: the TSB-function paths of sgetari end with rts; they get the ev_ret frame (the V2 path must not)
        sg = [i for i in self.ins if L["sgetari"] <= i["addr"] < L["sgetari"] + 0x40]
        j = [i for i in sg if i["mn"] == "jmp" and i["opnd"] == "csgetari1"][0]
        self.set_insn(j, "jmp ev_csg"); self.notes["IEVAL TSB path: ev_ret frame"] += 1
        for lab in ("gethex", "getbin"):
            d = [i for i in self.ins if L[lab] <= i["addr"] < L[lab] + 8 and i["opnd"] == "getdouble"][0]
            self.set_insn(d, "jsr ev_getdbl"); self.notes["IEVAL TSB path: ev_ret frame"] += 1
        # KERNAL-off spans (hi-res pixels): kerromaus disappears, the bitmap accesses go through the $DFxx helpers
        for i in self.ins:
            if i["mn"] == "jsr" and i["opnd"] == "kerromaus":
                self.set_insn(i, NOP3.replace("basromein/aus", "kerromaus")); self.notes["jsr kerromaus removed"] += 1
        for lab, op, tab in (("hset", "ora", "gbittabs"), ("herase", "and", "gbittabl"), ("hinvert", "eor", "gbittabs")):
            a = L[lab]; blk = [i for i in self.ins if a <= i["addr"] < a + 7]
            assert [i["mn"] for i in blk] == ["lda", op, "sta"] and blk[1]["opnd"] == tab + ",x", blk
            self.set_insn(blk[0], "lda %s,x\n\tjmp h_%s\n\tnop" % (tab, op))
            self.set_insn(blk[1], ""); self.set_insn(blk[2], "")
            self.notes["pixel read-modify-write -> KERNAL-off helper"] += 1
        for lab in ("testdot", "tdot0"):
            a = L[lab]; blk = [i for i in self.ins if a <= i["addr"] < a + 5]
            assert [i["mn"] for i in blk] == ["lda", "and"] and blk[1]["opnd"] == "gbittabs,x", blk
            self.set_insn(blk[0], "jsr h_tst\n\tnop\n\tnop"); self.set_insn(blk[1], "")
            self.notes["pixel test -> KERNAL-off helper"] += 1
        # CHAR: the char ROM is switched in only around each read (I/O, hence the $DFxx stubs, stay visible for PLOT)
        cz = L["charzei"]
        c0 = [i for i in self.ins if cz <= i["addr"] < cz + 8 and i["mn"] == "jsr" and i["opnd"] == "charen0"][0]
        self.set_insn(c0, NOP3.replace("basromein/aus", "charen0"))
        rd = [i for i in self.ins if cz < i["addr"] < cz + 0x80 and i["mn"] == "lda" and i["opnd"] == "($fe),y"][0]
        nx = [i for i in self.ins if i["addr"] == rd["addr"] + 2][0]
        assert nx["mn"] == "and" and nx["opnd"] == "$ac"
        self.set_insn(rd, "jsr h_chrand\n\tnop"); self.set_insn(nx, "")
        self.notes["CHAR: char ROM read -> helper"] += 1
        # basromein/basromaus themselves stay: Neo's overlays (TSB.MEM, TSB.EXT, TSB.HSG) call them at fixed addresses
        # the IRQ handler returns to c_irq instead of the KERNAL
        sirq_end = [i for i in self.ins if i["mn"] == "jmp" and i["val"] == 0xEA31]
        assert len(sirq_end) == 1
        self.set_insn(sirq_end[0], "rts\n\t!byte $ea,$ea")
        # vectors
        self.edit_text(L["tsbvecs"], "!wo warmstart,sloop,tokenize,slist,sbasbef,sgetari",
                       "!wo u_ierror,u_imain,u_icrnch,u_iqplop,u_igone,u_ieval")
        self.edit_text(L["loadsave"], "!wo sysload,syssave", "!wo u_load,u_save")
        for i in self.ins:
            if i["opnd"] in ("#>sirq", "#<sirq"):
                self.set_insn(i, "lda %s" % i["opnd"].replace("sirq", "u_irq"))
        # NMI/BRK vectors in COLD: replace the block from "ldx #>ssnmi" to "sta nmivec" (28 bytes)
        a = [i for i in self.ins if i["opnd"] == "#>ssnmi"][0]
        b = [i for i in self.ins if i["mn"] == "sta" and i["opnd"] == "nmivec"][0]
        blk = [i for i in self.ins if a["addr"] <= i["addr"] <= b["addr"]]
        size = sum(i["len"] for i in blk)
        self.set_insn(blk[0], "jsr u38_setvec\n\tjmp +\n\t!fill %d,$ea\n+" % (size - 6))
        for i in blk[1:]: self.set_insn(i, "")
        self.notes["COLD vector block -> u38_setvec"] += 1
        # command dispatch table: entries in another region than the dispatcher (core)
        disp_reg = self.region(L["sprtab"])
        for lno in range(self.line_of(sprtab), len(self.lines) + 1):
            s = self.lines[lno - 1]
            m = re.match(r"^(\w*\s*!wo\s+)(\w+)-1(.*)$", s)
            if not m:
                if re.match(r"^\s*(!if\b|\}|!byte|!by\b)", s) and not s.strip().startswith("!by 0"): continue
                if lno > self.line_of(sprtab) and not s.strip().startswith(";") and s.strip(): break
                continue
            if m.group(2) not in L: continue      # (the cartridge=1 branch of an !if)
            t = L[m.group(2)]
            if self.region(t) != disp_reg and t not in self.hot and self.bank.get(self.region(t)) is not None:
                n = "fj_" + m.group(2); self.fj[n] = (t, self.bank[self.region(t)])
                self.edits[lno] = m.group(1) + n + "-1" + m.group(3); self.notes["dispatch table -> FJ"] += 1
        # code that restores dispatch entries (RENUM/PLACE after MEM) must store the same values
        for i in self.ins:
            m = re.match(r"^#([<>])(\w+)-1$", i["opnd"])
            if m and ("fj_" + m.group(2)) in self.fj:
                self.set_insn(i, "%s #%sfj_%s-1" % (i["mn"], m.group(1), m.group(2)))
        bad = [i for i in self.ins if re.match(r"^#[<>]\w+$", i["opnd"]) and i["opnd"][2:] in ("befplace",)]
        for i in bad:   # "lda #>befplace" (sic, no -1) next to "#<befplace-1": same high byte in Neo
            if "fj_befplace" in self.fj: self.set_insn(i, "%s #>fj_befplace-1" % i["mn"])

    def returns(self, x):
        """Outcomes of a JMP to x, at the jumper's stack depth: 'rts' (returns to the jumper's caller), 'exit' (BASIC
        ROM exit, error, interpreter loop), 'unknown'. JSRs are assumed to return."""
        if not hasattr(self, "_ret"): self._ret = {}
        if x in self._ret: return self._ret[x]
        by = {i["addr"]: k for k, i in enumerate(self.ins)}
        seen, todo, out = set(), [x], set()
        while todo:
            a = todo.pop()
            while a not in seen:
                seen.add(a)
                if a not in by: out.add("unknown"); break
                i = self.ins[by[a]]
                if i["mode"] == "rel":
                    off = i["val"] - 256 if i["val"] >= 128 else i["val"]; todo.append(a + 2 + off)
                if i["mn"] == "rts": out.add("rts"); break
                if i["mn"] == "rti": out.add("exit"); break
                if i["mn"] == "jmp":
                    t = i["val"]
                    if i["mode"] == "ind": out.add("exit" if t in (0x300, 0x308, 0xA002) else "unknown")
                    elif i["kind"] == "label" and 0x8000 <= t < 0xD000: todo.append(t)
                    elif t in NONRET: out.add("exit")
                    elif 0xA000 <= t < 0xC000 or t >= 0xE000: out.add("rts")
                    else: out.add("unknown")
                    break
                k = by[a] + 1
                if k >= len(self.ins): break
                a = self.ins[k]["addr"]
        self._ret[x] = out
        return out

    def set_insn(self, i, text):
        s = self.lines[i["line"] - 1]
        code, sep, com = s.partition(";")
        m = re.match(r"^([A-Za-z_][\w.]*|[+-]+)?(\s*)", code)
        lab = m.group(1) or ""
        self.edits[i["line"]] = (lab + "\t" + text).rstrip() + ("\t;" + com if com else "")

    def edit_text(self, addr, old, new):
        ln = self.line_of(addr)
        assert old in self.lines[ln - 1], (old, self.lines[ln - 1])
        self.edits[ln] = self.lines[ln - 1].replace(old, new)

    def line_of(self, addr):
        return [i for i in self.ins if i["addr"] == addr][0]["line"] if any(i["addr"] == addr for i in self.ins) \
            else [r[0] for r in self.rows if r[1] == addr][0]

    def irq_check(self):
        """The IRQ handler (sirq and what it reaches) must make no stub call: interrupts do not save t_a/t_p/jv."""
        reach = closure(self.ins, region=self.region, start_addrs=[self.labels["sirq"]])
        bad = [i for i in self.ins if i["addr"] in reach and i["line"] in self.edits
               and re.search(r"\b(rc_|rx_|fc_|fj_|rt_|rcs_)", self.edits[i["line"]])]
        return reach, bad

    # --- output ---------------------------------------------------------------------------------------
    def source(self):
        return "\n".join(self.edits.get(n + 1, l) for n, l in enumerate(self.lines))

    def thunks(self, bank_of_site=None):
        out = []
        for n, t in sorted(self.rc.items()):
            out.append("%s\t+RC $%04x, RC_BANK" % (n, t))
        for n, t in sorted(self.rx.items()):
            out.append("%s\t+RX $%04x" % (n, t))
        for n, t in sorted(self.rt.items()):
            out.append("%s\t+RT rc_%04x" % (n, t))
        for n, t in sorted(self.rcs.items()):
            out.append("%s\t+RCS $%04x, RC_BANK" % (n, t))
        for n, (t, tb, b) in sorted(self.fc.items()):
            out.append("%s\t+FC $%04x, %d, RC_BANK" % (n, t, tb))
        for n, (t, tb) in sorted(self.fj.items()):
            out.append("%s\t+FJ $%04x, %d" % (n, t, tb))
        return "\n".join(out) + "\n"


B21_TOP = r"""; generated by tools/u38gen.py b21 -- B2.1 speed spike image ($6000-$CFFF)
	!cpu 6510
	EF_ON		= $04		; spike: cartridge stays off (TSB Neo in RAM); same cycles as $07
	BANK_CORE	= 1
	RC_BANK		= 1		; spike: one copy of every thunk
	U38_IGONE_BANK = 1
	U38_IEVAL_BANK = 1
	U38_IERROR_BANK = 1
	U38_IMAIN_BANK = 1
	U38_ICRNCH_BANK = 1
	U38_IQPLOP_BANK = 1
	U38_BRK_BANK = 1
	U38_LOAD_BANK = 1
	U38_SAVE_BANK = 1
	U38_IRQ_BANK = 1
	U38_NMI_BANK = 1

	U38_IGONE	= sbasbef
!ifdef U38_FASTEVAL {
	U38_IEVAL	= sgetari + 7	; after "lda #0 : sta $0d : jsr chrget" (done by f_ieval in RAM)
} else {
	U38_IEVAL	= sgetari
}
	U38_IERROR	= warmstart
	U38_IMAIN	= sloop
	U38_ICRNCH	= tokenize
	U38_IQPLOP	= slist
	U38_BRK		= sbrk
	U38_LOAD	= sysload
	U38_SAVE	= syssave
	U38_IRQ		= sirq
	U38_NMI		= snmi
	!src "core38.a"
	!src "tsbneo.a"

	* = $6000
u38_area
	+U38_COMMON
; COLD's vector block (replaces 28 bytes in befcold): NMI/BRK to the entry stubs, JiffyDOS keys off
u38_setvec
	ldx #>ssnmi
	stx $fffa+1		; RAM NMI vector (KERNAL off): TSB Neo's own handler, it runs in RAM here
	stx $9b			; JiffyDOS keys off (TSB Neo writes $80)
	lda #<ssnmi
	sta $fffa
	lda #<u_nmi
	sta nmivec
	lda #>u_nmi
	sta nmivec+1
!ifdef U38_FASTEVAL {
	lda #<f_ieval		; IEVAL vector: RAM fast path
	sta $030a
	lda #>f_ieval
	sta $030b
}
	lda #<u_brk
	sta brkvec
	lda #>u_brk
	sta brkvec+1
	rts
; ROM call of TSB Neo's helper pspeibe: target already in $55/$56
rc_help	sta t_a
	lda #RC_BANK
	pha
	lda help+1
	sta jv+1
	lda help+2
	sta jv+2
	jmp rc_stub
; reads of the BASIC ROM's error-address table (OUT, error messages): cold
romrd_a326
	lda #ST_BASIC
	sta CPU_PORT
	lda $a326,x
romrd_back
	pha
	lda #ST_TSB
	sta CPU_PORT
	pla
	rts
romrd_a327
	lda #ST_BASIC
	sta CPU_PORT
	lda $a327,x
	jmp romrd_back
; IEVAL handler, TSB function paths: the ev_ret frame under the handler's return
ev_csg	+EV_JMP csgetari1
ev_getdbl
	+EV_PUSH getdouble
; hi-res pixels: operation (opcode of ora/and/eor #imm) into the $DFxx helper, mask in A
h_ora	pha
	lda #$09
	sta k_op
	pla
	jmp k_rmw
h_and	pha
	lda #$29
	sta k_op
	pla
	jmp k_rmw
h_eor	pha
	lda #$49
	sta k_op
	pla
	jmp k_rmw
h_chrand
	php
	sei			; I/O (and with it $0314's stub) is off while the char ROM is in
	lda CPU_PORT
	and #$fb
	sta CPU_PORT
	lda ($fe),y
	pha
	lda CPU_PORT
	ora #$04
	sta CPU_PORT
	pla
	plp
	and $ac
	rts
h_tst	jsr k_rd
	and gbittabs,x
	rts
; message text output (TSB's tsberrs): text in the BASIC ROM is read in BASIC state
tsberrs_u38
	ldy #0
	sty $13
-	jsr romrd_22
	php
	and #$7f
	jsr bsout
	iny
	plp
	bpl -
	rts
romrd_22
	lda $23
	cmp #$a0
	bcc +
	cmp #$c0
	bcs +
	lda #ST_BASIC
	sta CPU_PORT
	lda ($22),y
	jmp romrd_back
+	lda ($22),y
	rts
!ifdef U38_FASTEVAL {
; option O1: IEVAL fast path in RAM (BASIC state): V2 operands never enter flash
f_ieval	lda #0
	sta $0d
	jsr $0073
	bcs +
	jmp $bcf3
+	cmp #$24
	beq ++
	cmp #$25
	beq ++
	cmp #$64
	beq ++
	jmp $ae92
++	jmp u_ieval		; "$", "%", TSB function: into sgetari after its CHRGET (A, C kept)
}
u38_install
	+U38_INSTALL
	rts
	!src "thunks.a"
	+U38_DF_IMAGE
	+U38_FF_IMAGE
u38_area_end
!if u38_area_end > $8000 { !error "B2.1 spike: thunk area overflows into $8000" }
"""


# ----------------------------------------------------------------------------------------------------------------
# B2.2 flash build: TSB Neo's code from flash. Neo's regions are split at routine boundaries into four parts, each
# assembled at $A000 in its own ROMH bank (labels via !pseudopc), plus the RAM part $C000-$CFFF (Neo's data and its
# code there, run from RAM as in Neo). Crossings between parts go through the stubs; calls into the RAM part are
# plain. Each bank: part code from $A000, then its thunks/helpers ("extras"), then the common block at COMMON_AT.
# ----------------------------------------------------------------------------------------------------------------
PARTS = [("R", 0xC000, 0xD000, None)]      # flash parts are added by split_parts()
SPLIT = [(0x8000, 0xA00E, 3), (0xA00E, 0xC000, 3)]   # TSB Neo's $8000 and $A000 regions, parts each
# ($A000-$A00D belongs to the routine that starts at $9FF4 and runs across Neo's region boundary)


def split_parts(ins, labels):
    """Split points at routine boundaries: a labelled instruction right after an unconditional rts/rti/jmp, with no
    branch across it, closest to equal sizes."""
    global PARTS
    by = sorted(ins, key=lambda i: i["addr"])
    lab = set(labels.values())
    branches = []
    for i in by:
        if i["mode"] == "rel":
            off = i["val"] - 256 if i["val"] >= 128 else i["val"]; branches.append((i["addr"], i["addr"] + 2 + off))
    cands = []
    for p_, i in zip(by, by[1:]):
        if p_["addr"] + p_["len"] == i["addr"] and i["addr"] in lab and (p_["mn"] in ("rts", "rti") or
                                                                        (p_["mn"] == "jmp")):
            a = i["addr"]
            if not any(min(x, y) < a <= max(x, y) for x, y in branches): cands.append(a)
    parts, names, bank = [], iter("ABCDEFGHIJ"), 1
    for s0, e0, n in SPLIT:
        cuts = [s0]
        for k in range(1, n):
            ideal = s0 + (e0 - s0) * k // n
            cuts.append(min((c for c in cands if cuts[-1] < c < e0), key=lambda c: abs(c - ideal)))
        cuts.append(e0)
        for a, b in zip(cuts, cuts[1:]):
            parts.append((next(names), a, b, bank)); bank += 1
    PARTS = parts + [("R", 0xC000, 0xD000, None)]
    return PARTS
COMMON_AT = 0xB800
# RAM helpers in Neo's unused gap $C3E8-$C3FF (24 bytes): BASIC-ROM reads and newopen (called in BASIC state)
GAP_HELPERS = """rd_a326	lda $a326,x
	rts
rd_a327	lda $a327,x
	rts
rd_22	lda ($22),y
	rts
newopen_ram
	jsr $e219		; (TSB Neo's newopen, run in BASIC state from the ROM-call table)
	lda drive
	sta $ba
	jmp $e1c1
"""


def part_of(a):
    for k, s, e, b in PARTS:
        if s <= a < e: return k
    return "other"


WRITES_MN = {"sta", "stx", "sty", "inc", "dec", "asl", "lsr", "rol", "ror"}


class FlashGen(Gen):
    region = staticmethod(part_of)
    bank = {k: b for k, s, e, b in PARTS if b}
    flash = True

    def __init__(self):
        Gen.__init__(self)
        split_parts(self.ins, self.labels)
        FlashGen.bank = {k: b for k, s, e, b in PARTS if b}
        self.bank = FlashGen.bank
        self.hot = set()        # no copies in the flash spike except the port helpers (per bank, below)

    def build(self, out):
        self.classify()
        L = self.labels
        # one element per original source line (an edit may span several lines)
        lines = [self.edits.get(i + 1, l) for i, l in enumerate(self.lines)]
        # line -> part (by the address of the line's first byte in the report)
        lpart = {}
        for lno, a, hb, src in self.rows: lpart.setdefault(lno, part_of(a))
        # rename thunk references per part; port helpers called from another part -> per-bank copy
        refs = collections.defaultdict(set)
        cur = "A"
        TH = re.compile(r"\b((?:rc|rx|rt|rcs|fc|fj|ft)_\w+|rc_help|romrd_a32[67]|tsberrs_u38|ev_csg|ev_getdbl|h_ora|h_and|"
                        r"h_eor|h_tst|h_chrand|u38_setvec)\b")
        for n in range(len(lines)):
            cur = lpart.get(n + 1, cur)
            if n + 1 not in self.edits and not re.search(r"\b(kerromein|charen0|charen1)\b", lines[n]): continue
            out_l = []
            for sub in lines[n].split("\n"):
                code, sep, com = sub.partition(";")
                def ren(m):
                    refs[cur].add(m.group(1)); return m.group(1) + "__" + cur
                code = TH.sub(ren, code)
                for h in ("kerromein", "charen0", "charen1"):
                    if re.search(r"\b(jsr|jmp)\s+%s\b" % h, code) and part_of(L[h]) != cur:
                        code = re.sub(r"\b%s\b" % h, h + "__" + cur, code); refs[cur].add(h)
                out_l.append(code + sep + com)
            lines[n] = "\n".join(out_l)
        mapped, acc = {}, 0
        for i, l in enumerate(lines):
            mapped[i + 1] = acc; acc += l.count("\n") + 1
        # data tables read from another flash part: a copy of the table in the reading bank
        neo = open(self.rep[:-4] + ".bin", "rb").read()
        laddrs = sorted(set(a for n, a in L.items() if 0x8000 <= a < 0xC000))
        self.datacopies = collections.defaultdict(dict)
        for i in self.ins:
            sp = part_of(i["addr"])
            if sp not in self.bank or i["mn"] in ("jsr", "jmp") or i["mn"] in WRITES_MN: continue
            if i["mode"] not in ("abs", "abx", "aby") or i["kind"] != "label": continue
            m = re.match(r"^(\w+)", i["opnd"]); name = m.group(1)
            if name not in L or not (0x8000 <= L[name] < 0xC000) or part_of(L[name]) in (sp, "other", "R"): continue
            a0 = L[name]; nxt = [x for x in laddrs if x > a0]; end = min(max(nxt[0] if nxt else 0, a0 + 64), a0 + 256)
            self.datacopies[sp][name] = neo[a0 - 2 - 0x8000:end - 0x8000]
            ln = i["line"] - 1
            lines[ln] = re.sub(r"\b%s\b" % name, name + "__" + sp, lines[ln], count=1)
            self.notes["data table read across banks -> copy"] += 1
        # the same for table reads in rewritten lines (pixel helpers: "lda gbittabs,x")
        tabs = set(n for d in self.datacopies.values() for n in d) | {"gbittabs", "gbittabl"}
        cur = "A"
        for n in range(len(lines)):
            cur = lpart.get(n + 1, cur)
            if cur not in self.bank or n + 1 not in self.edits: continue
            def ren2(m):
                name = m.group(2)
                if name not in tabs or part_of(L[name]) == cur: return m.group(0)
                a0 = L[name]
                self.datacopies[cur].setdefault(name, neo[a0 - 2 - 0x8000:a0 + 64 - 0x8000])
                return m.group(1) + name + "__" + cur
            lines[n] = re.sub(r"\b((?:lda|ora|and|eor|cmp|adc|sbc|ldx|ldy)\s+)(\w+)(?=[,+\-\s;]|$)", ren2, lines[n])
        # MEMSIZ $A000; Ultra-38 start-up screen instead of Neo's banner and "tuned"
        txt = "\n".join(lines)
        txt = re.sub(r"(\nipr4\s+jsr chrgot[^\n]*\n\s*jmp )rx_a7e7__A", r"\1go_chk__A\t; u38: GO 64 / GO NEO", txt)
        assert "go_chk__A" in txt
        refs["A"].add("rx_a7e7")
        txt = txt.replace("\tldy #$80\n\tjsr $fd8c", "\tldy #$a0\t; Ultra-38: MEMSIZ $A000\n\tjsr $fd8c")
        assert "ldy #$a0" in txt
        txt, n1 = re.subn(r"(sidrescue\s+lda #\$d4\s*\n\s+sta mregadr\+1\s*\n\s+jmp )\S+", r"\1u38_banner__A", txt)
        txt, n2 = re.subn(r"dscbmout\s+ldy #0[^\n]*\n-\s+lda tuned,y",
                          "dscbmout\tjmp endsmb\t; Ultra-38: no \"tuned\"\n-\t!byte $ea,$ea", txt)
        txt, n3 = re.subn(r"(\n\s+!wo )newopen\b", r"\1newopen_ram", txt)
        txt, n4 = re.subn(r"\n\s+!fill 24[^\n]*mind the gap",
                          "\n" + GAP_HELPERS + "\t!fill 24 - 22, 0\t; rest of the gap", txt)
        assert (n1, n2, n3, n4) == (1, 1, 1, 1), (n1, n2, n3, n4)
        # part boundaries: !pseudopc blocks
        lines = txt.split("\n")
        starts = {}
        for k, s_, e, b in PARTS:      # the line after the previous part's last byte (labels before code go along)
            starts[k] = max([r[0] for r in self.rows if r[1] < s_] or [0]) + 1 if b else None
        # part A starts right after "*=$8000"
        a0 = [i for i, l in enumerate(lines) if re.match(r"^\s*\*\s*=\s*\$8000", l)][0]
        ins_at = {a0 + 1: "!pseudopc $a000 {\t; part A (bank 1)"}
        fl = [p_ for p_ in PARTS if p_[3]]
        prev = fl[0][0]
        for k, s_, e, b in fl[1:]:
            ins_at[mapped[starts[k]]] = "part%s_end\n}\n!pseudopc $a000 {\t; part %s (bank %d)" % (prev, k, b); prev = k
        r0 = [i for i, l in enumerate(lines) if '!src "memhook.inc"' in l][0]
        ins_at[r0] = "part%s_end\n}\t; end of the flash parts; part R ($C000-$CFFF) is RAM" % prev
        outl = []
        for i, l in enumerate(lines):
            if i in ins_at: outl.append(ins_at[i])
            outl.append(l)
        os.makedirs(out, exist_ok=True)
        open(os.path.join(out, "tsbneo.a"), "w", encoding="latin-1").write("\n".join(outl))
        for f in ("memhook.inc", "MD_memhook.inc"):
            open(os.path.join(out, f), "wb").write(open(os.path.join(ROOT, "TSBneo", f), "rb").read())
        open(os.path.join(out, "core38.a"), "w").write(open(os.path.join(ROOT, "additions/ultra38/core38.a")).read())
        # extras per bank and the common block
        ex = []
        for k, s_, e, b in PARTS:
            sect = self.extras(k, b, refs[k])
            if b:
                ex.append("\n; ---- bank %d extras (part %s)\n\t* = $%04x\n!pseudopc %s_end {\n%s_x_start\n%s\n%s_x_end\n}"
                          % (b, k, 0x1000 * b, "part" + k, k, sect, k))
            else:
                common_r = sect
        open(os.path.join(out, "extras.a"), "w").write("\n".join(ex) + "\n")
        open(os.path.join(out, "u38_flash.a"), "w").write(FLASH_TOP)
        open(os.path.join(out, "checks.a"), "w").write("".join(
            '!if %s_x_end > common_start { !error "part %s (bank %d) overflows into the common block" }\n' % (k, k, b)
            for k, s_, e, b in PARTS if b))
        import json
        json.dump(PARTS, open(os.path.join(out, "parts.json"), "w"))
        eb = {"IGONE": "sbasbef", "IEVAL": "sgetari", "IERROR": "warmstart", "IMAIN": "sloop", "ICRNCH": "tokenize",
              "IQPLOP": "slist", "BRK": "sbrk", "LOAD": "sysload", "SAVE": "syssave", "IRQ": "sirq", "NMI": "snmi"}
        open(os.path.join(out, "entrybanks.a"), "w").write(
            "".join("\tU38_%s_BANK = %d\n" % (k, self.bank[part_of(L[v])]) for k, v in eb.items()))
        open(os.path.join(out, "common.a"), "w").write(
            "\t* = $0400\n!pseudopc $%04x {\ncommon_start\n\t+U38_COMMON\n%s\ncommon_end\n}\n" % (COMMON_AT, common_r))
        return refs

    def extras(self, k, b, names):
        bk = str(b) if b else "-1"
        out = []
        for full in sorted(names):
            n = full
            S = "__" + k
            if n in self.rc: out.append("%s%s\t+RC $%04x, %s" % (n, S, self.rc[n], bk))
            elif n == "rx_a447":    # TSB error text (in flash) printed by the BASIC ROM: copy it to $0200 first
                out.append("rx_a447%s\n\tldy #0\n-\tlda ($22),y\n\tsta $0200,y\n\tiny\n\tasl\n\tbcc -\n\tlda #$00\n\tsta $22\n"
                           "\tlda #$02\n\tsta $23\n\t+RX $a447" % S)
            elif n in self.rx: out.append("%s%s\t+RX $%04x" % (n, S, self.rx[n]))
            elif n in self.rt:
                out.append("%s%s\t+RT rc_%04x%s" % (n, S, self.rt[n], S))
                if ("rc_%04x" % self.rt[n]) not in names: out.append("rc_%04x%s\t+RC $%04x, %s" % (self.rt[n], S, self.rt[n], bk))
            elif n in self.rcs: out.append("%s%s\t+RCS $%04x, %s" % (n, S, self.rcs[n], bk))
            elif n in self.fc: t, tb, _ = self.fc[n]; out.append("%s%s\t+FC %s, %d, %s" % (n, S, n[3:], tb, bk))
            elif n in self.fj: t, tb = self.fj[n]; out.append("%s%s\t+FJ %s, %d" % (n, S, n[3:], tb))
            elif n in self.ft:
                t, tb = self.ft[n]; out.append("%s%s\tjsr fc_%s%s\n\trts" % (n, S, n[3:], S))
                if ("fc_" + n[3:]) not in names: out.append("fc_%s%s\t+FC %s, %d, %s" % (n[3:], S, n[3:], tb, bk))
            elif n in ("ev_csg", "ev_getdbl"):
                t = "csgetari1" if n == "ev_csg" else "getdouble"
                tp = part_of(self.labels[t])
                if tp == k:
                    out.append(SPECIAL[n].replace("{S}", S).replace("{B}", bk))
                elif n == "ev_csg":      # the TSB function chain is in another bank: far jump after the frame
                    out.append("ev_csg%s\t+EV_JMP ev_fj%s\nev_fj%s\t+FJ csgetari1, %d" % (S, S, S, self.bank[tp]))
                else:                    # far call: EV_PUSH leaves the caller's return on top, the FC thunk returns there
                    out.append("ev_getdbl%s\t+EV_PUSH ev_fc%s\nev_fc%s\t+FC getdouble, %d, %s" % (S, S, S, self.bank[tp], bk))
            elif n in SPECIAL:
                txt = SPECIAL[n].replace("{S}", S).replace("{B}", bk)
                for tab in re.findall(r"\{(\w+)\}", txt):     # data tables used by a helper: copy if in another part
                    a0 = self.labels[tab]
                    if part_of(a0) == k: txt = txt.replace("{%s}" % tab, tab)
                    else:
                        neo = open(self.rep[:-4] + ".bin", "rb").read()
                        self.datacopies[k].setdefault(tab, neo[a0 - 2 - 0x8000:a0 + 64 - 0x8000])
                        txt = txt.replace("{%s}" % tab, tab + "__" + k)
                out.append(txt)
            elif n in ("kerromein", "charen0", "charen1"): out.append(PORTCOPY[n].replace("{S}", S))
            else: raise SystemExit("no thunk for %s in part %s" % (n, k))
        for name, data in sorted(getattr(self, "datacopies", {}).get(k, {}).items()):
            out.append("%s__%s_blk\t!byte %s\n%s__%s = %s__%s_blk + 2" % (name, k, ",".join("$%02x" % b for b in data),
                                                                       name, k, name, k))
        if k == "A":
            out.append(SPECIAL_A)
            # targets without a label in the source: their flash address (part start $A000 + offset)
            for n in sorted(set(x[3:] for x in list(self.fc) + list(self.fj) + list(self.ft))):
                if re.match(r"^L[0-9a-f]{4}$", n):
                    a = int(n[1:], 16); pk = part_of(a); ps = [p_ for p_ in PARTS if p_[0] == pk][0][1]
                    out.append("%s = $%04x" % (n, 0xA000 + a - ps))
        return "\n".join(out)


FLASH_TOP = r"""; generated by tools/u38gen.py flash -- B2.2 Ultra-38 flash spike
	!cpu 6510
	EF_ON		= $07
	BANK_CORE	= 1
	!src "entrybanks.a"
	U38_IGONE	= sbasbef
	U38_IEVAL	= sgetari
	U38_IERROR	= warmstart
	U38_IMAIN	= sloop
	U38_ICRNCH	= tokenize
	U38_IQPLOP	= slist
	U38_BRK		= sbrk
	U38_LOAD	= sysload
	U38_SAVE	= syssave
	U38_IRQ		= sirq
	U38_NMI		= snmi
	!src "core38.a"
	!src "tsbneo.a"
	!src "extras.a"
	!src "common.a"
	!src "checks.a"
	* = $0c00
	+U38_DF_IMAGE
	+U38_FF_IMAGE
"""
PORTCOPY = {"kerromein": "kerromein{S}\n\tlda pport\n\tora #2\n\tsta pport\n\trts",
            "charen1": "charen1{S}\n\tlda pport\n\tora #4\n\tsta pport\n\trts",
            "charen0": "charen0{S}\n\tsei\n\tlda pport\n\tand #$fb\n\tsta pport\n\trts"}
SPECIAL = {
    "rc_help": "rc_help{S}\n\tsta t_a\n!if {B} < 0 { lda core_bank } else { lda #{B} }\n\tpha\n\tlda help+1\n\tsta jv+1\n"
               "\tlda help+2\n\tsta jv+2\n\tjmp rc_stub",
    "romrd_a326": "romrd_a326{S}\t+RC rd_a326, {B}",
    "romrd_a327": "romrd_a327{S}\t+RC rd_a327, {B}",
    "tsberrs_u38": "tsberrs_u38{S}\n\tldy #0\n\tsty $13\n-\tlda $23\n\tcmp #$a0\n\tbcc +\n\tcmp #$c0\n\tbcs +\n"
                   "\tjsr rd22{S}\n\tjmp ++\n+\tlda ($22),y\n++\tphp\n\tand #$7f\n\tjsr bsout\n\tiny\n\tplp\n\tbpl -\n\trts\n"
                   "rd22{S}\t+RC rd_22, {B}",
    "ev_csg": "ev_csg{S}\t+EV_JMP csgetari1",
    "ev_getdbl": "ev_getdbl{S}\t+EV_PUSH getdouble",
    "h_ora": "h_ora{S}\n\tpha\n\tlda #$09\n\tsta k_op\n\tpla\n\tjmp k_rmw",
    "h_and": "h_and{S}\n\tpha\n\tlda #$29\n\tsta k_op\n\tpla\n\tjmp k_rmw",
    "h_eor": "h_eor{S}\n\tpha\n\tlda #$49\n\tsta k_op\n\tpla\n\tjmp k_rmw",
    "h_tst": "h_tst{S}\n\tjsr k_rd\n\tand {gbittabs},x\n\trts",
    "h_chrand": "h_chrand{S}\n\tphp\n\tsei\n\tlda CPU_PORT\n\tand #$fb\n\tsta CPU_PORT\n\tlda ($fe),y\n\tpha\n\tlda CPU_PORT\n"
                "\tora #$04\n\tsta CPU_PORT\n\tpla\n\tplp\n\tand $ac\n\trts",
    "u38_setvec": "u38_setvec{S}\n\tldx #$80\n\tstx $9b\t\t; JiffyDOS keys off (as TSB Neo)\n\tlda #<ram_nmi\n\tsta $fffa\n"
                  "\tlda #>ram_nmi\n\tsta $fffb\n\tlda #<u_nmi\n\tsta nmivec\n\tlda #>u_nmi\n\tsta nmivec+1\n"
                  "\tlda #<u_brk\n\tsta brkvec\n\tlda #>u_brk\n\tsta brkvec+1\n\trts",
}


# core bank (part A) additions: start-up screen (12 Nov amendment) and the generic GO with its mode table
SPECIAL_A = r"""
; ---- Ultra-38 start-up screen: border/background 6, text 15; row 1 banner, row 3 bytes free, READY. below.
; The number is MEMSIZ - TXTTAB, computed here (one space after SYSTEM: Fafa's spec).
u38_banner__A
	lda #6
	sta $d020
	sta $d021
	lda #15
	sta $0286
	ldy #0
-	lda u38_scr1,y
	beq +
	jsr bsout
	iny
	bne -
+	sec
	lda $37
	sbc $2b
	tax
	lda $38
	sbc $2c
	jsr rc_bdcd__A		; LINPRT: the number, no leading space
	ldy #0
-	lda u38_scr2,y
	beq +
	jsr bsout
	iny
	bne -
+	jmp rcs_a644__A		; NEW, as BASIC's own start message ($E422) ends
rc_bdcd__A	+RC $bdcd, 1
rcs_a644__A	+RCS $a644, 1
; (the source runs under !ct pet: lower-case letters here are PETSCII $41-$5A, upper case on the screen)
u38_scr1	!byte $93, $0d
	!text "     *** commodore 64 tsb ultra ***", $0d, $0d
	!text " 64k ram system ", 0
u38_scr2	!text " basic bytes free", $0d, 0

; ---- GO: TSB's statement hook sees the V2 token GO ($CB) before the BASIC ROM does. A known mode name after it
; (spaces skipped; then end of statement) switches mode; anything else (GO TO ...) goes on to BASIC V2.
go_chk__A
	php
	cmp #$cb
	beq +
	plp
	jmp rx_a7e7__A
+	plp
	ldx #0			; mode table index
go_next	ldy #1
-	lda (progz),y
	iny
	cmp #$20
	beq -
	dey
	sty $22			; offset of the argument
go_cmp	lda go_names,x
	beq go_end		; whole name matched: end of statement?
	cmp (progz),y
	bne go_skip
	inx
	iny
	bne go_cmp
go_end	lda (progz),y
	beq go_hit
	cmp #$3a
	beq go_hit
	cmp #$20
	beq go_hit
go_skip	lda go_names,x		; to the next table entry
	beq +
	inx
	bne go_skip
+	inx
	inx
	inx
	lda go_names,x
	bne go_next
	lda #$cb		; not ours: GO as in BASIC V2 (GO TO), A/flags as CHRGOT left them
	sec
	jmp rx_a7e7__A
go_hit	lda go_names+1,x
	sta $22
	lda go_names+2,x
	sta $23
	jmp ($0022)
; mode table: name (PETSCII as typed, plain characters after the GO token), 0, handler. Ultra-51 gets one more row.
go_names
	!text "64", 0
	!word go_64
	!text "neo", 0
	!word go_neo
	!byte 0
; GO 64: cartridge off, KERNAL reset: a stock C64 (38911 BYTES FREE)
go_64	ldx #go64_end - go64_tr - 1
-	lda go64_tr,x
	sta $0200,x
	dex
	bpl -
	jmp $0200
go64_tr	sei
	lda #$37		; standard port: the KERNAL reset looks for CBM80 before it sets $01
	sta $01
	lda #$04
	sta $de02
	jmp $fce2
go64_end
; GO NEO: 8K mode, bank 0: the KERNAL reset starts the TSB Neo launcher (as the v0.1 CRT): stock TSB Neo 2.60.228
go_neo	ldx #goneo_end - goneo_tr - 1
-	lda goneo_tr,x
	sta $0200,x
	dex
	bpl -
	jmp $0200
goneo_tr sei
	lda #$37		; ROML at $8000 is visible to the KERNAL's CBM80 check only with LORAM and HIRAM set
	sta $01
	lda #0
	sta $de00
	lda #$06
	sta $de02
	jmp $fce2
goneo_end
"""


def main(a):
    if a and a[0] == "flash":
        g = FlashGen(); refs = g.build(a[1])
        for k, v in g.notes.most_common(): print(f"{v:5}  {k}")
        print("far jumps to routines that sometimes return (checked by hand):", sorted(g.mixed))
        return 0
    g = Gen(); g.classify()
    if a and a[0] == "report":
        for k, v in g.notes.most_common(): print(f"{v:5}  {k}")
        print("rc targets", len(g.rc), "rx targets", len(g.rx), "fc", len(g.fc), "fj", len(g.fj))
        hb = len([i for i in g.ins if i["addr"] in g.hot])
        print("hot closure: %d instructions, %d bytes" % (hb, sum(i["len"] for i in g.ins if i["addr"] in g.hot)))
        reach, bad = g.irq_check()
        print("IRQ handler reach: %d instructions, stub calls: %s" % (len(reach), [b["src"] for b in bad]))
        return 0
    if a and a[0] == "b21":
        out = a[1]; os.makedirs(out, exist_ok=True)
        reach, bad = g.irq_check()
        if bad: raise SystemExit("IRQ handler makes stub calls: %s" % [b["src"] for b in bad])
        txt = g.source().replace("\tldy #$80\n\tjsr $fd8c", "\tldy #$60\t; B2.1 spike: MEMSIZ $6000 (thunks above)\n\tjsr $fd8c")
        assert "ldy #$60" in txt
        open(os.path.join(out, "tsbneo.a"), "w", encoding="latin-1").write(txt)
        for f in ("memhook.inc", "MD_memhook.inc"):
            open(os.path.join(out, f), "wb").write(open(os.path.join(ROOT, "TSBneo", f), "rb").read())
        open(os.path.join(out, "thunks.a"), "w").write(g.thunks())
        open(os.path.join(out, "core38.a"), "w").write(open(os.path.join(ROOT, "additions/ultra38/core38.a")).read())
        open(os.path.join(out, "u38_b21.a"), "w").write(B21_TOP)
        for k, v in g.notes.most_common(): print(f"{v:5}  {k}")
        return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
