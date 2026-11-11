#!/usr/bin/env python3
"""Tokenizer checks (tools/tsblist.crunch):
1. Neo mirror: every corpus line tokenizes exactly as stored on disk. One known exception: NEO-BLISTER line 4685
   holds ELSE+OPEN bytes that TSB Neo's own tokenizer cannot produce from typed text (typing ELSEOPEN gives
   NO ERROR+"PEN"; tests/golden/commands/tsb_editor/10_elseopen).
2. Ultra rule (decision 11 Nov): every corpus line tokenizes exactly as stored on disk, NEO-BLISTER 4685 included.
3. Ultra == Neo on every line of the command suite (programs and typed lines), except the intended differences
   listed in INTENDED (the collision class of reports/1.5-tokenizer-collisions.md).
4. tests/tokenizer/neo_typed.tsv (lines typed into TSB Neo in VICE, with the bytes Neo stored): the Neo mirror
   gives the same bytes for every line; Ultra differs exactly on the lines marked 'fix'."""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import tsblist  # noqa: E402
tab = tsblist._tsb_table(); fails = []
INTENDED = {"100 ifathenprint1:elseopen3,3"}

# 4. typed lines (no corpus needed)
nt = 0; nfix = 0
for row in open(os.path.join(HERE, "tokenizer", "neo_typed.tsv"), encoding="utf-8"):
    if row.startswith("#") or not row.strip(): continue
    text, neo, mark = row.rstrip("\n").split("\t"); nt += 1
    if tsblist.crunch(text, tab).hex() != neo: fails.append(f"neo_typed: mirror differs from Neo on {text!r}")
    differs = tsblist.crunch(text, tab, ultra=True).hex() != neo
    if differs != (mark == "fix"): fails.append(f"neo_typed: Ultra {'differs' if differs else 'equals'} on {text!r} (marked {mark!r})")
    nfix += mark == "fix"

# 3. command suite
nc = 0
lines = []
for f in sorted(glob.glob(os.path.join(ROOT, "tests/commands/*.bas"))) + [os.path.join(ROOT, "tests/corpus/do-test-fixed.bas")]:
    lines += [l.strip() for l in open(f, encoding="utf-8") if l.strip() and not l.startswith(";")]
for sc in json.load(open(os.path.join(ROOT, "tests/commands.json")))["programs"]:
    for st in sc["steps"]:
        if "type" in st: lines += [l for l in st["type"].replace("\x93", "").split("\r") if l.strip()]
for l in lines:
    nc += 1
    num, _, body = l.partition(" ")
    if not num.isdigit(): body = l
    if (tsblist.crunch(body, tab) != tsblist.crunch(body, tab, ultra=True)) != (l in INTENDED):
        fails.append(f"commands: Ultra vs Neo unexpected on {l!r}")

# 1./2. corpus
D64 = os.path.join(ROOT, "corpus", "tsbneo_260228.d64")
msg = ""
if os.path.exists(D64):
    d = open(D64, "rb").read(); w = tsblist.tsb_words(); n = 0; bad = []; badu = []
    for name, ty, b, t, s in tsblist.directory(d):
        f = tsblist.read_file(d, t, s)
        if ty != 2 or (f[0] | f[1] << 8) != 0x0801: continue
        m = f[2:]; p = 0; ls = tsblist.listing(f, w, lossless=True)[1]; k = 0
        while p + 4 <= len(m) and (m[p] | m[p + 1] << 8):
            e = m.index(0, p + 4); num = m[p + 2] | m[p + 3] << 8
            txt = ls[k].split(" ", 1)[1] if " " in ls[k] else ""; k += 1; n += 1
            if tsblist.crunch(txt, tab) != m[p + 4:e]: bad.append(f"{name} {num}")
            if tsblist.crunch(txt, tab, ultra=True) != m[p + 4:e]: badu.append(f"{name} {num}")
            p = e + 1
    unexpected = [b for b in bad if b not in {"NEOÂÌISTER 1.03 4685"}]
    if unexpected: fails.append(f"corpus (Neo mirror): {unexpected}")
    if badu: fails.append(f"corpus (Ultra rule): {badu}")
    msg = f"corpus {n - len(bad)}/{n} Neo, {n - len(badu)}/{n} Ultra; "
else:
    msg = "corpus SKIP (D64 missing); "
for f in fails[:20]: print("FAIL " + f)
print(("FAIL" if fails else "PASS") + f" crunch_corpus: {msg}commands {nc} lines Ultra==Neo except {len(INTENDED)} intended; "
      f"typed-into-Neo {nt} lines, {nfix} Ultra fixes")
sys.exit(1 if fails else 0)
