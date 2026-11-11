#!/usr/bin/env python3
"""Neo-only detector: the rules Ultra applies at RUN (plan task 1.3, implemented in ROM in task 5.3).

Works on the tokenized program exactly as it sits in memory, so every rule here is one a 6502 routine can
apply at RUN by walking the BASIC lines: no disk access, no evaluation of variables. Only *literal* addresses
are seen; addresses computed at run time are not (hence "seems to").

Usage:
  neodetect.py <file.prg>                       verdict for one program
  neodetect.py <disk.d64> [name ...]            verdict for every BASIC program on the disk (or the named ones)
  neodetect.py <disk.d64> --check <expect.json> compare verdicts with expectations; exit 1 on any mismatch
  add -v to print every hit, --json for machine-readable output.

Rules (an address A is "in TSB" when $8000 <= A <= $CFFF, the RAM TSB Neo occupies and Ultra gives to BASIC):
  N1  PEEK, POKE, WAIT, SYS, D!PEEK, D!POKE, MEMPEEK whose address argument starts with a literal in TSB.
  N2  TSB LOAD with a literal load address in TSB (LOAD name,dev,0,addr).
  N3  SCRLD DEF with a literal target page in TSB ($80-$CF).
  N4  a vector in $0300-$0333 set to a literal that points into TSB (D!POKE vec,addr or POKE vec+1,hi).
  N5  (U2+) the KERNAL screen pointer $0288 set to a page in TSB, or VIC bank 3 selected via $DD00:
      the program then draws into $C000-$CFFF itself, where Neo keeps colour data and the MEM screen.
  N6  MEMCLR / MEMDEF with a literal C64 address in TSB: a hit in $C000-$C3FF (hi-res colour data) or
      $CC00-$CFFF (MEM screen) is reported as "remap" (Ultra's TSB code must redirect it to the moved
      area; no warning); anywhere else in TSB it flags like N1.
  X   exemption: once a literal POKE 56,hi (MEMTOP high byte) or D!POKE 55,addr appears, addresses from that
      page up to $CFFF no longer count for N1-N3/N5/N6 (the program reserved them; Ultra-native style).
  i   info only: LOAD name,dev,1 with no address (target known only from the file header). Not a flag
      at RUN; see reports/1.3-detector.md for the LOAD-time check.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tsblist  # noqa: E402

TSB_LO, TSB_HI = 0x8000, 0xCFFF
REMAP = [(0xC000, 0xC3FF, "hi-res colour data"), (0xCC00, 0xCFFF, "MEM screen")]
# BASIC/KERNAL vectors in $0300-$0333 (low byte address); the high byte is at +1.
VECTORS = [0x0300, 0x0302, 0x0304, 0x0306, 0x0308, 0x030A, 0x0311, 0x0314, 0x0316, 0x0318, 0x031A, 0x031C,
           0x031E, 0x0320, 0x0322, 0x0324, 0x0326, 0x0328, 0x032A, 0x032C, 0x032E, 0x0330, 0x0332]

V2 = {0x80 + i: w for i, w in enumerate(tsblist.V2)}
TOK = {w: t for t, w in V2.items()}


def in_tsb(a):
    return TSB_LO <= a <= TSB_HI


def lex(body, words):
    """One BASIC line (bytes after the line number) -> list of (kind, value). kind: kw, num, str, ch."""
    out, p = [], 0
    while p < len(body):
        c = body[p]
        if c == 0x22:
            q = body.find(b'"', p + 1)
            q = len(body) if q < 0 else q
            out.append(("str", body[p + 1:q])); p = q + 1; continue
        if c == 0x64 and p + 1 < len(body):
            t = body[p + 1]
            t = t ^ 0x8F if t >= 0x80 else t
            out.append(("kw", words[t - 1] if 0 < t <= len(words) else "TSB%d" % t)); p += 2; continue
        if c >= 0x80:
            w = V2.get(c, "?")
            out.append(("kw", w)); p += 1
            if w in ("REM", "DATA"):  # rest of line (DATA: up to ':') is not code
                if w == "REM": break
                q = p
                inq = False
                while q < len(body) and (inq or body[q] != 0x3A):
                    inq ^= body[q] == 0x22; q += 1
                p = q
            continue
        if c == 0x24 and p + 1 < len(body) and chr(body[p + 1]) in "0123456789ABCDEF":  # $hex
            q = p + 1
            while q < len(body) and chr(body[q]) in "0123456789ABCDEF": q += 1
            out.append(("num", int(body[p + 1:q], 16))); p = q; continue
        if c == 0x25 and p + 1 < len(body) and body[p + 1] in b"01":  # %binary
            q = p + 1
            while q < len(body) and body[q] in b"01": q += 1
            out.append(("num", int(body[p + 1:q], 2))); p = q; continue
        if 0x30 <= c <= 0x39 or (c == 0x2E and p + 1 < len(body) and 0x30 <= body[p + 1] <= 0x39):
            q = p
            while q < len(body) and (0x30 <= body[q] <= 0x39 or body[q] in b". "): q += 1
            txt = body[p:q].replace(b" ", b"").decode()
            try:
                v = float(txt)
            except ValueError:
                v = None
            out.append(("num", int(v) if v is not None and v == int(v) else v)); p = q; continue
        if c != 0x20:
            out.append(("ch", chr(c)))
        p += 1
    return out


def args_after(toks, i):
    """Split the argument list that starts at toks[i] into top-level comma-separated pieces, until ':' or a
    closing ')' at depth 0 or a statement keyword."""
    res, cur, depth = [], [], 0
    while i < len(toks):
        k, v = toks[i]
        if k == "ch" and v == "(":
            depth += 1
        elif k == "ch" and v == ")":
            if depth == 0: break
            depth -= 1
        elif k == "ch" and v == ":" and depth == 0:
            break
        elif k == "kw" and v in ("THEN", "ELSE", "GOTO") and depth == 0:
            break
        elif k == "ch" and v == "," and depth == 0:
            res.append(cur); cur = []; i += 1; continue
        cur.append(toks[i]); i += 1
    res.append(cur)
    return res


def lead(arg):
    """Value of an argument that starts with a literal (after an optional '('), else None."""
    j = 0
    while j < len(arg) and arg[j] == ("ch", "("): j += 1
    if j < len(arg) and arg[j][0] == "num" and isinstance(arg[j][1], int):
        return arg[j][1]
    return None


def scan(prg, words):
    m = prg[2:]; p = 0; hits = []; memtop = None
    while p + 4 <= len(m):
        if (m[p] | m[p + 1] << 8) == 0: break
        num = m[p + 2] | m[p + 3] << 8
        e = m.index(0, p + 4)
        toks = lex(m[p + 4:e], words)
        p = e + 1

        def hit(rule, addr, what):
            free = memtop is not None and memtop <= addr <= TSB_HI and rule in ("N1", "N2", "N3", "N5", "N6")
            hits.append({"line": num, "rule": "X" if free else rule, "addr": addr, "what": what})

        for i, (k, v) in enumerate(toks):
            if k != "kw": continue
            prev = toks[i - 1][1] if i and toks[i - 1][0] == "kw" else None
            nxt = toks[i + 1] if i + 1 < len(toks) else ("", None)
            if v in ("PEEK", "POKE", "WAIT", "SYS"):
                name = (prev + v) if prev in ("D!", "MEM") else v
                if prev == "MEM" and v == "POKE": name = "MEMPOKE"
                a = args_after(toks, i + 1)
                if name.endswith("PEEK") and a and a[0] and a[0][0] == ("ch", "("):
                    a = args_after(toks, i + 2)
                addr = lead(a[0]) if a else None
                if addr is None: continue
                if in_tsb(addr):
                    hit("N1", addr, f"{name} ${addr:04X}")
                if name.endswith("POKE") and len(a) > 1:
                    val = lead(a[1])
                    if val is None: continue
                    if name == "D!POKE" and addr in VECTORS and in_tsb(val):
                        hit("N4", val, f"D!POKE vector ${addr:04X},${val:04X}")
                    if name == "POKE" and addr - 1 in VECTORS and TSB_LO >> 8 <= val <= TSB_HI >> 8:
                        hit("N4", val << 8, f"POKE vector hi ${addr:04X},${val:02X}")
                    if name == "POKE" and addr == 0x0288 and TSB_LO >> 8 <= val <= TSB_HI >> 8:
                        hit("N5", val << 8, f"POKE $0288,${val:02X} (screen editor at ${val << 8:04X})")
                    if name == "POKE" and addr == 0xDD00 and val & 3 == 0:
                        hit("N5", 0xC000, f"POKE $DD00,${val:02X} (VIC bank 3)")
                    if name == "POKE" and addr == 56 and val <= TSB_HI >> 8:
                        memtop = val << 8 if memtop is None else min(memtop, val << 8)
                    if name == "D!POKE" and addr == 55 and val <= TSB_HI:
                        memtop = val if memtop is None else min(memtop, val)
            elif v == "LOAD":
                a = args_after(toks, i + 1)
                if len(a) >= 4:
                    addr = lead(a[3])
                    if addr is not None and in_tsb(addr):
                        hit("N2", addr, f"LOAD to ${addr:04X}")
                elif len(a) == 3 and lead(a[2]) == 1:
                    hits.append({"line": num, "rule": "i", "addr": None, "what": "LOAD ...,1 (target from file)"})
            elif v == "SCRLD" and nxt == ("kw", "DEF"):
                a = args_after(toks, i + 2)
                pg = lead(a[0]) if a else None
                if pg is not None and TSB_LO >> 8 <= pg <= TSB_HI >> 8:
                    hit("N3", pg << 8, f"SCRLD DEF page ${pg:02X}")
            elif v == "MEM" and nxt in (("kw", "CLR"), ("kw", "DEF")):
                a = args_after(toks, i + 2)
                idx = 0 if nxt[1] == "CLR" else 1
                addr = lead(a[idx]) if len(a) > idx else None
                if addr is None or not in_tsb(addr): continue
                area = next((n for lo, hi, n in REMAP if lo <= addr <= hi), None)
                if area:
                    hits.append({"line": num, "rule": "remap", "addr": addr, "what": f"MEM{nxt[1]} ${addr:04X} ({area})"})
                else:
                    hit("N6", addr, f"MEM{nxt[1]} ${addr:04X}")
    return hits


FLAG_RULES = ("N1", "N2", "N3", "N4", "N5", "N6")


def verdict(hits, rules=FLAG_RULES):
    return any(h["rule"] in rules for h in hits)


def programs(d64):
    d = open(d64, "rb").read()
    for name, ty, blocks, t, s in tsblist.directory(d):
        if ty != 2: continue
        f = tsblist.read_file(d, t, s)
        if len(f) > 2 and (f[0] | f[1] << 8) == 0x0801:
            yield name, f


def main(a):
    verbose = "-v" in a; as_json = "--json" in a
    a = [x for x in a if x not in ("-v", "--json")]
    check = None
    if "--check" in a:
        i = a.index("--check"); check = json.load(open(a[i + 1])); a = a[:i] + a[i + 2:]
    words = tsblist.tsb_words()
    if a[0].lower().endswith(".prg"):
        progs = [(os.path.basename(a[0]), open(a[0], "rb").read())]
    else:
        progs = list(programs(a[0]))
        if len(a) > 1:
            want = [x.lower() for x in a[1:]]
            progs = [(n, f) for n, f in progs if n.lower() in want]
    results = {}
    for name, f in progs:
        h = scan(f, words)
        results[name] = {"neo_only": verdict(h), "base": verdict(h, ("N1", "N2", "N3", "N4", "N6")),
                         "rules": sorted({x["rule"] for x in h}), "hits": h}
    if as_json:
        print(json.dumps(results, indent=1)); return 0
    bad = 0
    for name, r in results.items():
        mark = "NEO-ONLY" if r["neo_only"] else "ultra   "
        line = f"{mark} {name:18} {','.join(r['rules'])}"
        if check is not None:
            exp = check.get(name)
            if exp is None:
                line = "?? " + line + "  (no expectation)"; bad += 1
            elif exp["neo_only"] != r["neo_only"]:
                line = "FAIL " + line + f"  (expected {'NEO-ONLY' if exp['neo_only'] else 'ultra'})"; bad += 1
            else:
                line = "ok   " + line
        print(line)
        if verbose:
            for x in r["hits"]:
                print(f"       {x['line']:>5} {x['rule']:5} {x['what']}")
    if check is not None:
        missing = [n for n in check if n not in results and not n.startswith("_")]
        for n in missing:
            print(f"FAIL {n}: expected program not found"); bad += 1
        n_neo = sum(r["neo_only"] for r in results.values())
        print(f"{n_neo} flagged, {len(results) - n_neo} not flagged; {bad} mismatch(es)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
