#!/usr/bin/env python3
"""Corrected corpus copies (plan task 1.5) differ from the originals only where intended.

tests/corpus/do-test-fixed.bas must tokenize to DO-TEST.DMO's exact bytes except the four FETCH ...,1,E lines,
which become FETCH ...,1,E$:E=VAL(E$). Skips when corpus/tsbneo_260228.d64 is missing."""
import os, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import tsblist, neodetect  # noqa: E402

D64 = os.path.join(ROOT, "corpus/tsbneo_260228.d64")
if not os.path.exists(D64):
    print("SKIP corpus_fixed: corpus/tsbneo_260228.d64 missing"); sys.exit(0)
orig = dict(neodetect.programs(D64))["DO-TEST.DMO"]
fixed = [l.rstrip("\n") for l in open(os.path.join(ROOT, "tests/corpus/do-test-fixed.bas"), encoding="utf-8")
         if l.strip() and not l.startswith(";")]
_, olines = tsblist.listing(orig, tsblist.tsb_words(), lossless=True)
olines = [str(x) for x in olines]
bad = []
if len(olines) != len(fixed): bad.append(f"{len(fixed)} lines, original has {len(olines)}")
changed = 0
for o, f in zip(olines, fixed):
    if o == f: continue
    if f == o + "$:E=VAL(E$)" and o.startswith(tuple("0123456789")) and " FETCH " in o and o.endswith(",1,E"):
        changed += 1
    else: bad.append(f"unexpected change: {o!r} -> {f!r}")
if changed != 4: bad.append(f"{changed} FETCH lines changed, expected 4")
# the untouched lines must also tokenize to the original's bytes
if tsblist.make_prg(olines) != orig: bad.append("original listing does not round-trip")
if bad:
    print("FAIL corpus_fixed: " + "; ".join(bad)); sys.exit(1)
print("PASS corpus_fixed (do-test-fixed.bas: 4 intended FETCH changes, rest byte-identical)")
