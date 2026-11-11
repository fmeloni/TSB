#!/usr/bin/env python3
"""tools/tsblist.crunch must tokenize every corpus line exactly as stored on disk.
One known exception: NEO-BLISTER line 4685 holds ELSE+OPEN bytes that TSB's own tokenizer cannot produce from
typed text (typing ELSEOPEN gives NO ERROR+"PEN"; verified in tests/golden/commands/tsb_editor/10_elseopen)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import tsblist  # noqa: E402
D64 = os.path.join(HERE, "..", "corpus", "tsbneo_260228.d64")
if not os.path.exists(D64): print("SKIP crunch_corpus: D64 missing"); sys.exit(0)
d = open(D64, "rb").read(); w = tsblist.tsb_words(); tab = tsblist._tsb_table(); n = 0; bad = []
for name, ty, b, t, s in tsblist.directory(d):
    f = tsblist.read_file(d, t, s)
    if ty != 2 or (f[0] | f[1] << 8) != 0x0801: continue
    m = f[2:]; p = 0; ls = tsblist.listing(f, w, lossless=True)[1]; k = 0
    while p + 4 <= len(m) and (m[p] | m[p + 1] << 8):
        e = m.index(0, p + 4); num = m[p + 2] | m[p + 3] << 8
        txt = ls[k].split(" ", 1)[1] if " " in ls[k] else ""; k += 1; n += 1
        if tsblist.crunch(txt, tab) != m[p + 4:e]: bad.append(f"{name} {num}")
        p = e + 1
known = {"NEOÂÌISTER 1.03 4685"}
unexpected = [b for b in bad if b not in known]
print(("PASS" if not unexpected else "FAIL") + f" crunch_corpus: {n - len(bad)}/{n} lines identical; known exception(s): {len(bad) - len(unexpected)}"
      + (f"; unexpected: {unexpected}" if unexpected else ""))
sys.exit(1 if unexpected else 0)
