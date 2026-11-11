#!/usr/bin/env python3
"""Unit cases for tools/neodetect.py: programs are tokenized with tools/tsblist.crunch (TSB's tokenizer
mirrored; validated byte for byte against 1966 of 1967 corpus lines)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import neodetect, tsblist  # noqa: E402

words = tsblist.tsb_words(); tab = tsblist._tsb_table(); bad = 0
for c in json.load(open(os.path.join(HERE, "cases.json")))["cases"]:
    hits = neodetect.scan(tsblist.make_prg(c["prg"], table=tab), words)
    got = sorted({h["rule"] for h in hits})
    ok = got == sorted(c["rules"]); bad += not ok
    print(("ok   " if ok else "FAIL ") + f"{c['id']:24} got {got} expected {sorted(c['rules'])}")
print(f"{bad} failing case(s)")
sys.exit(1 if bad else 0)
