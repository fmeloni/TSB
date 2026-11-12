#!/usr/bin/env python3
"""Static inventory of TSB Neo for the Ultra-38 design (phase B1).

Usage: neoinventory.py <acme report of TSBneo/tsbneo.a> [--json out.json]

Reads the ACME report (acme -r) of the disk build and classifies every instruction:
  - calls/jumps from TSB code to the BASIC ROM ($A000-$BFFF) and KERNAL ($E000-$FFFF),
    recognised by the source operand (a literal or an equate, not a TSB label);
  - writes to the processor port $01 and the value written where it is visible;
  - absolute writes into TSB's own code area $8000-$BFFF (impossible from flash);
  - absolute reads of BASIC ROM / KERNAL data;
  - JSR/JMP between TSB's regions $8000-$9FFF, $A000-$BFFF, $C000-$CFFF.
"""
import json, re, sys, collections

# 6502 opcodes: mnemonic, addressing mode, length
MODES = {"imp": 1, "acc": 1, "imm": 2, "zp": 2, "zpx": 2, "zpy": 2, "izx": 2, "izy": 2,
         "rel": 2, "abs": 3, "abx": 3, "aby": 3, "ind": 3}
OPS = {}
def op(code, mn, mode): OPS[code] = (mn, mode)
for mn, codes in {
    "adc": (0x69, 0x65, 0x75, None, 0x61, 0x71, 0x6d, 0x7d, 0x79),
    "and": (0x29, 0x25, 0x35, None, 0x21, 0x31, 0x2d, 0x3d, 0x39),
    "cmp": (0xc9, 0xc5, 0xd5, None, 0xc1, 0xd1, 0xcd, 0xdd, 0xd9),
    "eor": (0x49, 0x45, 0x55, None, 0x41, 0x51, 0x4d, 0x5d, 0x59),
    "lda": (0xa9, 0xa5, 0xb5, None, 0xa1, 0xb1, 0xad, 0xbd, 0xb9),
    "ora": (0x09, 0x05, 0x15, None, 0x01, 0x11, 0x0d, 0x1d, 0x19),
    "sbc": (0xe9, 0xe5, 0xf5, None, 0xe1, 0xf1, 0xed, 0xfd, 0xf9),
    "sta": (None, 0x85, 0x95, None, 0x81, 0x91, 0x8d, 0x9d, 0x99),
}.items():
    for code, mode in zip(codes, ("imm", "zp", "zpx", "zpy", "izx", "izy", "abs", "abx", "aby")):
        if code is not None: op(code, mn, mode)
for mn, (zp, zpx, ab, abx) in {"asl": (0x06, 0x16, 0x0e, 0x1e), "lsr": (0x46, 0x56, 0x4e, 0x5e),
                               "rol": (0x26, 0x36, 0x2e, 0x3e), "ror": (0x66, 0x76, 0x6e, 0x7e),
                               "inc": (0xe6, 0xf6, 0xee, 0xfe), "dec": (0xc6, 0xd6, 0xce, 0xde)}.items():
    op(zp, mn, "zp"); op(zpx, mn, "zpx"); op(ab, mn, "abs"); op(abx, mn, "abx")
for code, mn in ((0x0a, "asl"), (0x4a, "lsr"), (0x2a, "rol"), (0x6a, "ror")): op(code, mn, "acc")
for code, mode in ((0xa2, "imm"), (0xa6, "zp"), (0xb6, "zpy"), (0xae, "abs"), (0xbe, "aby")): op(code, "ldx", mode)
for code, mode in ((0xa0, "imm"), (0xa4, "zp"), (0xb4, "zpx"), (0xac, "abs"), (0xbc, "abx")): op(code, "ldy", mode)
for code, mode in ((0x86, "zp"), (0x96, "zpy"), (0x8e, "abs")): op(code, "stx", mode)
for code, mode in ((0x84, "zp"), (0x94, "zpx"), (0x8c, "abs")): op(code, "sty", mode)
for code, mode in ((0xe0, "imm"), (0xe4, "zp"), (0xec, "abs")): op(code, "cpx", mode)
for code, mode in ((0xc0, "imm"), (0xc4, "zp"), (0xcc, "abs")): op(code, "cpy", mode)
for code, mode in ((0x24, "zp"), (0x2c, "abs")): op(code, "bit", mode)
for code, mn in ((0x10, "bpl"), (0x30, "bmi"), (0x50, "bvc"), (0x70, "bvs"), (0x90, "bcc"), (0xb0, "bcs"),
                 (0xd0, "bne"), (0xf0, "beq")): op(code, mn, "rel")
op(0x20, "jsr", "abs"); op(0x4c, "jmp", "abs"); op(0x6c, "jmp", "ind")
for code, mn in ((0x00, "brk"), (0x08, "php"), (0x18, "clc"), (0x28, "plp"), (0x38, "sec"), (0x40, "rti"),
                 (0x48, "pha"), (0x58, "cli"), (0x60, "rts"), (0x68, "pla"), (0x78, "sei"), (0x88, "dey"),
                 (0x8a, "txa"), (0x98, "tya"), (0x9a, "txs"), (0xa8, "tay"), (0xaa, "tax"), (0xb8, "clv"),
                 (0xba, "tsx"), (0xc8, "iny"), (0xca, "dex"), (0xd8, "cld"), (0xe8, "inx"), (0xea, "nop"),
                 (0xf8, "sed")): op(code, mn, "imp")
WRITES = {"sta", "stx", "sty", "inc", "dec", "asl", "lsr", "rol", "ror"}

LINE = re.compile(r"^\s*(\d+)\s+([0-9a-f]{4})\s+([0-9a-f]+)\s+(.*)$")
EQU = re.compile(r"^\s*([A-Za-z_][\w.]*)\s*=\s*(\$[0-9a-fA-F]+|\d+)")


def region(a):
    if 0x8000 <= a < 0xA000: return "8000"
    if 0xA000 <= a < 0xC000: return "A000"
    if 0xC000 <= a < 0xD000: return "C000"
    return "other"


def parse(rep):
    equates, labels, rows = {}, {}, []
    for raw in open(rep, encoding="latin-1"):
        line = raw.rstrip("\n")
        m = LINE.match(line)
        if not m:
            body = re.sub(r"^\s*\d+\s+", "", line)
            e = EQU.match(body)
            if e:
                equates[e.group(1)] = int(e.group(2)[1:], 16) if e.group(2)[0] == "$" else int(e.group(2))
            continue
        lno, addr, hexb, src = int(m.group(1)), int(m.group(2), 16), bytes.fromhex(m.group(3)), m.group(4)
        code = src.split(";")[0]
        lab = re.match(r"^([A-Za-z_][\w.]*)", code)
        if lab and not code.startswith((" ", "\t")):
            labels[lab.group(1)] = addr
        rows.append((lno, addr, hexb, src))
    return equates, labels, rows


def main(argv):
    out = inventory(argv[1])
    if "--json" in argv:
        json.dump(out, open(argv[argv.index("--json") + 1], "w"), indent=1)
    for k in ("instruction_bytes_per_region", "instructions_per_region", "rom_call_summary", "cross_region_jsr_jmp",
              "code_area_write_targets"):
        print(k, json.dumps(out[k]))
    print("pointer_sites", len(out["pointer_sites"]),
          dict(collections.Counter(p["region"] for p in out["pointer_sites"])))
    print("port_writes", len(out["port_writes"]), "code_area_writes", len(out["code_area_writes"]),
          "rom_data_reads", len(out["rom_data_reads"]), "indirect_jumps", len(out["indirect_jumps"]))


def inventory(rep):
    equates, labels, rows = parse(rep)
    insns = []
    for lno, addr, hexb, src in rows:
        code = src.split(";")[0].strip()
        lab = re.match(r"^([A-Za-z_][\w.]*)\s+", code)
        stmt = code[lab.end():] if lab and lab.group(1) not in OPS_MN else code
        if stmt.startswith(("+", "-")) and not re.match(r"^[+-]\s*[a-z]{3}\b", stmt):
            stmt = re.sub(r"^[+-]+\s*", "", stmt)
        stmt = re.sub(r"^[+-]+\s+", "", stmt)
        mm = re.match(r"^([a-z]{3})\b\s*(.*)$", stmt)
        if not mm or mm.group(1) not in OPS_MN or not hexb or hexb[0] not in OPS:
            continue
        mn, mode = OPS[hexb[0]]
        if mn != mm.group(1) or len(hexb) != MODES[mode]:
            continue
        opnd = mm.group(2).strip()
        val = hexb[1] | (hexb[2] << 8) if len(hexb) == 3 else (hexb[1] if len(hexb) == 2 else None)
        insns.append(dict(line=lno, addr=addr, mn=mn, mode=mode, val=val, opnd=opnd, src=src.strip()))

    def operand_kind(opnd):
        """'literal', 'equate:<name>', 'label:<name>' or 'expr'."""
        if re.match(r"^[+-]+$", opnd): return "label:anon"
        tok = re.match(r"^\(?\s*([$%]?[\w.]+)", opnd)
        if not tok: return "expr"
        t = tok.group(1)
        if t.startswith("$") or t.isdigit(): return "literal"
        if t in labels: return "label:" + t
        if t in equates: return "equate:" + t
        return "expr"

    out = collections.OrderedDict()
    size = collections.Counter()
    for i in insns: size[region(i["addr"])] += MODES[i["mode"]]
    out["instruction_bytes_per_region"] = dict(size)
    out["instructions_per_region"] = dict(collections.Counter(region(i["addr"]) for i in insns))

    rom_calls, rom_reads, port, codewrites, xregion, indirect = [], [], [], [], collections.Counter(), []
    for k, i in enumerate(insns):
        kind = operand_kind(i["opnd"])
        ext = not kind.startswith("label:")
        if i["mn"] in ("jsr", "jmp") and i["mode"] == "abs":
            t = i["val"]
            if ext and (0xA000 <= t < 0xC000 or t >= 0xE000):
                rom_calls.append(dict(at="%04x" % i["addr"], region=region(i["addr"]), kind=i["mn"],
                                      target="%04x" % t, rom="basic" if t < 0xC000 else "kernal", line=i["line"]))
            elif not ext:
                xregion[(i["mn"], region(i["addr"]), region(t))] += 1
        if i["mode"] == "ind":
            indirect.append(dict(at="%04x" % i["addr"], src=i["src"], line=i["line"]))
        if i["mn"] in WRITES and i["mode"] in ("zp", "abs") and i["val"] == 1:
            prev = [insns[j]["src"].split(";")[0].strip() for j in range(max(0, k - 3), k)]
            port.append(dict(at="%04x" % i["addr"], region=region(i["addr"]), line=i["line"], before=prev,
                             src=i["src"]))
        if i["mn"] in WRITES and i["mode"] in ("abs", "abx", "aby") and 0x8000 <= i["val"] < 0xC000:
            codewrites.append(dict(at="%04x" % i["addr"], target="%04x" % i["val"], line=i["line"], src=i["src"]))
        if i["mn"] not in WRITES and i["mn"] not in ("jsr", "jmp") and i["mode"] in ("abs", "abx", "aby") \
                and ext and (0xA000 <= i["val"] < 0xC000 or i["val"] >= 0xE000):
            rom_reads.append(dict(at="%04x" % i["addr"], target="%04x" % i["val"], line=i["line"], src=i["src"]))
    ptr = []
    for i in insns:
        if i["mode"] in ("izy", "izx"):
            ptr.append(dict(at="%04x" % i["addr"], region=region(i["addr"]), mn=i["mn"], zp="%02x" % i["val"],
                            write=i["mn"] in WRITES, line=i["line"]))
    out["pointer_sites"] = ptr
    out["sites"] = {
        "jsr_jmp_label": [dict(at="%04x" % i["addr"], kind=i["mn"], src=region(i["addr"]), dst=region(i["val"]),
                               to="%04x" % i["val"], name=operand_kind(i["opnd"])[6:])
                          for i in insns if i["mn"] in ("jsr", "jmp") and i["mode"] == "abs"
                          and operand_kind(i["opnd"]).startswith("label:")],
    }
    # calls into BASIC's RAM routines: CHRGET $0073 / CHRGOT $0079 (and the $54 JMP used by the ROM-call helper)
    out["sites"]["zpcall"] = [dict(at="%04x" % i["addr"], kind=i["mn"], to="%04x" % i["val"], src=region(i["addr"]))
                              for i in insns if i["mn"] in ("jsr", "jmp") and i["mode"] == "abs" and i["val"] < 0x100]
    disp = [r for r in rows if "; execute command" in r[3] and r[2] == b"\x60"]
    out["sites"]["dispatch"] = ["%04x" % r[1] for r in disp]
    out["rom_calls"] = rom_calls
    out["rom_call_summary"] = {
        "sites": len(rom_calls),
        "by_region_and_rom": dict(collections.Counter("%s->%s" % (c["region"], c["rom"]) for c in rom_calls)),
        "distinct_basic": len({c["target"] for c in rom_calls if c["rom"] == "basic"}),
        "distinct_kernal": len({c["target"] for c in rom_calls if c["rom"] == "kernal"}),
    }
    out["cross_region_jsr_jmp"] = {"%s %s->%s" % k: v for k, v in sorted(xregion.items())}
    out["port_writes"] = port
    out["code_area_writes"] = codewrites
    out["code_area_write_targets"] = len({w["target"] for w in codewrites})
    out["rom_data_reads"] = rom_reads
    out["indirect_jumps"] = indirect
    out["labels"] = labels
    return out

OPS_MN = {v[0] for v in OPS.values()}

if __name__ == "__main__":
    main(sys.argv)
