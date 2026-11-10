#!/usr/bin/env python3
"""List TSB / Simons' BASIC programs from a D64 (or a .prg) as text.

    tools/tsblist.py <disk.d64> <name>     list one program (name as in the directory, any case)
    tools/tsblist.py <disk.d64>            print the directory with load addresses
    tools/tsblist.py <file.prg>

Keywords come from TSB's own table (label tabbef in build/tsbneo_disk.prg; run make build first).
TSB tokens are $64 followed by the keyword number (1-based); a following byte >= $80 is EOR $8F.
"""
import os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
V2 = ("END FOR NEXT DATA INPUT# INPUT DIM READ LET GOTO RUN IF RESTORE GOSUB RETURN REM STOP ON WAIT LOAD "
      "SAVE VERIFY DEF POKE PRINT# PRINT CONT LIST CLR CMD SYS OPEN CLOSE GET NEW TAB( TO FN SPC( THEN NOT "
      "STEP + - * / ^ AND OR > = < SGN INT ABS USR FRE POS SQR RND LOG EXP COS SIN TAN ATN PEEK LEN STR$ "
      "VAL ASC CHR$ LEFT$ RIGHT$ MID$ GO").split()
SPT = [21] * 17 + [19] * 7 + [18] * 6 + [17] * 10
TYPES = {0: "DEL", 1: "SEQ", 2: "PRG", 3: "USR", 4: "REL"}


def tsb_words():
    lbl = os.path.join(ROOT, "build/tsbneo_disk.lbl"); prg = os.path.join(ROOT, "build/tsbneo_disk.prg")
    addr = next(int(l.split("$")[1].split()[0], 16) for l in open(lbl) if l.split()[:1] == ["tabbef"])
    img = open(prg, "rb").read()[2:]; p = addr - 0x8000; words = []; w = ""
    while img[p]:
        c = img[p]; p += 1
        if c & 0x80: words.append(w + chr(c & 0x7F).upper()); w = ""
        else: w += chr(c).upper()
    return words


def off(t, s): return (sum(SPT[:t - 1]) + s) * 256


def directory(d):
    t, s = 18, 1
    while t:
        sec = d[off(t, s):off(t, s) + 256]
        for i in range(8):
            e = sec[i * 32:i * 32 + 32]
            if e[2]:
                yield e[5:21].replace(b"\xa0", b"").decode("latin1"), e[2] & 7, e[30] | e[31] << 8, e[3], e[4]
        t, s = sec[0], sec[1]


def read_file(d, t, s):
    out = b""
    while t:
        sec = d[off(t, s):off(t, s) + 256]
        out += sec[2:] if sec[0] else sec[2:sec[1] + 1]
        t, s = sec[0], sec[1]
    return out


def petchr(c):
    if c == 0x0D: return "\n"
    if 0x20 <= c <= 0x5F: return chr(c)
    if 0xC1 <= c <= 0xDA: return chr(c - 0x80)  # shifted letters
    return "{$%02X}" % c


def listing(prg, words):
    la = prg[0] | prg[1] << 8; m = prg[2:]; p = 0; lines = []
    while p + 4 <= len(m):
        nxt = m[p] | m[p + 1] << 8
        if nxt == 0: break
        num = m[p + 2] | m[p + 3] << 8; p += 4; s = ""; quote = False
        while p < len(m) and m[p]:
            c = m[p]; p += 1
            if c == 0x22: quote = not quote; s += '"'
            elif quote: s += petchr(c)
            elif c == 0x64 and p < len(m) and m[p]:
                t = m[p]; p += 1
                if t >= 0x80: t ^= 0x8F
                s += words[t - 1] if 0 < t <= len(words) else "{TSB%d}" % t
            elif c >= 0x80: s += V2[c - 0x80] if c - 0x80 < len(V2) else "{$%02X}" % c
            else: s += petchr(c)
        p += 1; lines.append(f"{num} {s}")
    return la, lines


def main(a):
    words = tsb_words()
    if a[0].lower().endswith(".prg"):
        la, ls = listing(open(a[0], "rb").read(), words); print("\n".join(ls)); return
    d = open(a[0], "rb").read()
    if len(a) == 1:
        for name, ty, blocks, t, s in directory(d):
            la = read_file(d, t, s)[:2] if ty == 2 else b""
            print(f"{name:18} {TYPES[ty]} {blocks:4} " + ("$%04X" % (la[0] | la[1] << 8) if la else ""))
        return
    for name, ty, blocks, t, s in directory(d):
        if name.lower() == a[1].lower():
            la, ls = listing(read_file(d, t, s), words)
            print(f"; {name} load ${la:04X}"); print("\n".join(ls)); return
    raise SystemExit("not found: " + a[1])


if __name__ == "__main__":
    main(sys.argv[1:])
