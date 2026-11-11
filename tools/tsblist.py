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


def petchr(c, lossless=False):
    if lossless: return chr(c) if 0x20 <= c <= 0x5F and c not in (0x7B, 0x7D) else "{$%02X}" % c
    if c == 0x0D: return "\n"
    if 0x20 <= c <= 0x5F: return chr(c)
    if 0xC1 <= c <= 0xDA: return chr(c - 0x80)  # shifted letters
    return "{$%02X}" % c


def listing(prg, words, lossless=False):
    la = prg[0] | prg[1] << 8; m = prg[2:]; p = 0; lines = []
    while p + 4 <= len(m):
        nxt = m[p] | m[p + 1] << 8
        if nxt == 0: break
        num = m[p + 2] | m[p + 3] << 8; p += 4; s = ""; quote = False
        while p < len(m) and m[p]:
            c = m[p]; p += 1
            if c == 0x22: quote = not quote; s += '"'
            elif quote or lossless and (c < 0x20 or 0x60 <= c < 0x80) and c != 0x64: s += petchr(c, lossless)
            elif c == 0x64 and p < len(m) and m[p]:
                t = m[p]; p += 1
                if t >= 0x80: t ^= 0x8F
                s += words[t - 1] if 0 < t <= len(words) else "{TSB%d}" % t
            elif c >= 0x80: s += V2[c - 0x80] if c - 0x80 < len(V2) else "{$%02X}" % c
            else: s += petchr(c, lossless)
        p += 1; lines.append(f"{num} {s}")
    return la, lines


V2B = [w.encode() for w in V2]


def _rawbytes(text):
    """Line text -> PETSCII bytes. Letters of either case -> $41-$5A; {$XX} -> that byte."""
    out = bytearray(); i = 0
    while i < len(text):
        if text.startswith("{$", i) and text[i + 4:i + 5] == "}":
            out.append(int(text[i + 2:i + 4], 16)); i += 5; continue
        out.append(ord(text[i].upper()) if text[i].isalpha() else ord(text[i])); i += 1
    return bytes(out)


def _tsb_table():
    lbl = os.path.join(ROOT, "build/tsbneo_disk.lbl"); prg = os.path.join(ROOT, "build/tsbneo_disk.prg")
    addr = next(int(l.split("$")[1].split()[0], 16) for l in open(lbl) if l.split()[:1] == ["tabbef"])
    img = open(prg, "rb").read()[2:]; p = addr - 0x8000; t = bytearray()
    while img[p]: t.append(img[p]); p += 1
    return bytes(t) + b"\0"


def crunch(text, table=None):
    """Tokenize one line body the way TSB Neo does: TSB's tokenizer (tsbneo.a 'tokenize'), then the
    BASIC V2 CRUNCH at $A57C. Returns the stored bytes (without line link/number/terminator)."""
    tab = table or _tsb_table()
    b = bytearray(_rawbytes(text)); y = 0
    while y < len(b):                                   # --- TSB pass
        c = b[y]
        if c == 0x22:
            q = b.find(b'"', y + 1); y = len(b) if q < 0 else q + 1; continue
        if c == 0x40: break                             # "@" of DESIGN: rest of line untouched
        if c == 0x44 and b[y + 1:y + 4] == b"ATA": break
        if c == 0x52 and b[y + 1:y + 3] == b"EM": break
        if not 0x41 <= c < 0xDB: y += 1; continue
        z = y; x = 0; code = 0; found = False
        while True:
            yy = z
            while True:
                t = tab[x]
                d = (b[yy] - t) & 0xFF if yy < len(b) else (0 - t) & 0xFF
                if d == 0: yy += 1; x += 1; continue
                if d == 0x80: found = True
                break
            if found: break
            while tab[x] and not tab[x] & 0x80: x += 1   # skip rest of this word
            if not tab[x]: break
            x += 1; code += 1
            if not tab[x]: break
        if found and yy != z:
            b[z:yy + 1] = bytes([0x64, code + 1]); y = z + 2
        else:
            y += 1
    out = bytearray(); x = 0; data = False              # --- V2 CRUNCH ($A57C)
    while x < len(b):
        c = b[x]
        if c >= 0x80:
            if c == 0xFF: out.append(c)
            x += 1; continue
        if c == 0x20 or data and c != 0x22 and c != 0x3A:
            out.append(c); x += 1; continue
        if c == 0x22:
            q = b.find(b'"', x + 1); q = len(b) - 1 if q < 0 else q
            out += b[x:q + 1]; x = q + 1; continue
        if c == 0x3F: out.append(0x99); x += 1; continue
        if 0x30 <= c < 0x3C:
            out.append(c); x += 1; data = data and c != 0x3A; continue
        tok = None
        for i, w in enumerate(V2B):
            n = len(w)
            if b[x:x + n] == w: tok = 0x80 + i; break
            if n > 1 and b[x:x + n - 1] == w[:-1] and x + n - 1 < len(b) and b[x + n - 1] == w[-1] | 0x80:
                tok = 0x80 + i; break
        if tok is None:
            out.append(c); x += 1; continue
        out.append(tok); x += n
        if tok == 0x8F: out += b[x:]; break                 # REM
        if tok == 0x83: data = True
    return bytes(out)


def make_prg(lines, start=0x0801, table=None):
    """[(number, text)] or ["10 PRINT ..."] -> PRG bytes (load address + linked lines)."""
    tab = table or _tsb_table(); body = bytearray(); a = start
    for ln in lines:
        if isinstance(ln, str):
            num, _, text = ln.strip().partition(" "); num = int(num)
        else:
            num, text = ln
        c = crunch(text, tab); nxt = a + 4 + len(c) + 1
        body += bytes([nxt & 255, nxt >> 8, num & 255, num >> 8]) + c + b"\0"; a = nxt
    return bytes([start & 255, start >> 8]) + body + b"\0\0"


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
