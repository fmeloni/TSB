#!/usr/bin/env python3
"""Debug aid for the Ultra-38 spikes: single-step a program in VICE and stop where TSB code goes wrong.

Usage: trace38.py <crt> <img.rep> <prog.bas> [--keys TEXT] [--frames N] [--from LABEL|$ADDR] [--steps N]

Runs the program (tokenized and RUN as in the command suite), lets N IRQs pass, puts TEXT into the keyboard
buffer, then (optionally after reaching LABEL) single-steps and prints the last 60 instructions (PC, port, A X Y SP)
when the CPU executes $8000-$BFFF RAM at an address that is not an instruction start of the image (img.rep), or a
BRK, or the BASIC warm start $E37B. The image is the generated source's ACME report (instruction starts)."""
import collections, os, re, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vicemon, demo_capture  # noqa: E402


def starts(rep):
    s, lab = set(), {}
    for raw in open(rep, encoding="latin-1"):
        m = re.match(r"^\s*\d+\s+([0-9a-f]{4})\s+([0-9a-f]+)(\.\.\.)?\s*(.*)$", raw.rstrip("\n"))
        if not m: continue
        a = int(m.group(1), 16); code = m.group(4).split(";")[0]
        t = re.match(r"^([A-Za-z_][\w.]*)", code)
        if t: lab.setdefault(t.group(1), a)
        if re.search(r"\b(lda|sta|ldx|ldy|stx|sty|jsr|jmp|rts|rti|pha|pla|php|plp|inc|dec|inx|iny|dex|dey|tax|tay|txa|"
                     r"tya|tsx|txs|cmp|cpx|cpy|bne|beq|bcc|bcs|bpl|bmi|bvc|bvs|and|ora|eor|adc|sbc|asl|lsr|rol|ror|"
                     r"bit|clc|sec|cli|sei|clv|cld|sed|nop|brk)\b", code) and not code.lstrip().startswith("!") \
                or re.match(r"\s*!by(te)?\s+\$2c\s*$", code):
            s.add(a)
    lbl = rep[:-4] + ".lbl"
    if os.path.exists(lbl):
        for ln in open(lbl):
            m = re.match(r"\s*([A-Za-z_][\w.]*)\s*=\s*\$([0-9a-fA-F]+)", ln)
            if m: lab[m.group(1)] = int(m.group(2), 16)
    return s, lab


def main(a):
    crt, rep, bas = a[0], a[1], a[2]
    o = dict(keys="", frames="60", steps="200000")
    frm = None
    i = 3
    while i < len(a):
        if a[i] == "--from": frm = a[i + 1]
        else: o[a[i][2:]] = a[i + 1]
        i += 2
    ok, lab = starts(rep)
    with vicemon.Vice(crt=crt, timeout=3600) as v:
        demo_capture.inject_and_run(v, bas)
        v.frames(int(o["frames"]))
        if o["keys"]:
            k = vicemon.petscii(o["keys"].replace("\\r", "\r"))
            v.poke(0x0277, k, "cpu"); v.poke(0xC6, [len(k)], "cpu")
        if frm:
            addr = lab[frm] if frm in lab else int(frm.lstrip("$"), 16)
            cid = v.checkpoint(addr); v.resume(); v.wait_stopped(); v.delete_checkpoint(cid)
        hist = collections.deque(maxlen=60)
        for n in range(int(o["steps"])):
            v.cmd(0x71, struct.pack("<BH", 0, 1)); v.wait_stopped()
            r = v.registers(); pc = r[3]
            port = v.mem(1, 1, "cpu")[0]
            hist.append((pc, port, r[0], r[1], r[2], r[4]))
            bad = None
            if 0x8000 <= pc < 0xC000 and (pc >= 0xA000 and port & 1) is False and pc not in ok: bad = "not an instruction start"
            if 0xA000 <= pc < 0xC000 and not port & 1 and pc not in ok: bad = "not an instruction start (BASIC ROM out)"
            if 0x8000 <= pc < 0xA000 and pc not in ok: bad = "not an instruction start"
            if pc == 0xE37B: bad = "BASIC warm start"
            if r[4] & 0xFF < 0x80: bad = "stack below $0180"
            if v.mem(pc, pc, "cpu")[0] in (0x02, 0x12, 0x22, 0x32, 0x42, 0x52, 0x62, 0x72, 0x92, 0xB2, 0xD2, 0xF2):
                bad = "JAM opcode"
            if v.mem(pc, pc, "cpu")[0] == 0 and (pc < 0xA000 or not port & 1): bad = "BRK"
            if bad:
                print(f"STOP after {n} steps: {bad}")
                inv = {}
                for k2, a2 in lab.items(): inv.setdefault(a2, k2)
                for pc_, p_, A, X, Y, S in hist:
                    print(f"  {pc_:04X} {inv.get(pc_, ''):12} port {p_:02X}  A {A:02X} X {X:02X} Y {Y:02X} SP {S:02X}")
                return 1
        print("no problem in", o["steps"], "steps")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
