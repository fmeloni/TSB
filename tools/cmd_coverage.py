#!/usr/bin/env python3
"""Keyword coverage of the command suite: which TSB and BASIC V2 keywords appear (tokenized exactly as TSB
does it) in the programs of tests/commands.json and in the direct-mode lines the harness types.

    tools/cmd_coverage.py [tests/commands.json]     prints covered / missing keywords
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tsblist  # noqa: E402

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def tokens(body, words):
    out, p = set(), 0
    while p < len(body):
        c = body[p]
        if c == 0x22:
            q = body.find(b'"', p + 1); p = len(body) if q < 0 else q + 1; continue
        if c == 0x64 and p + 1 < len(body):
            t = body[p + 1]; t = t ^ 0x8F if t >= 0x80 else t
            if 0 < t <= len(words): out.add(("TSB", words[t - 1]))
            p += 2; continue
        if c >= 0x80 and c - 0x80 < len(tsblist.V2):
            out.add(("V2", tsblist.V2[c - 0x80]))
            if c == 0x8F: break
        p += 1
    return out


def main(a):
    spec = a[0] if a else os.path.join(ROOT, "tests/commands.json")
    words = tsblist.tsb_words(); tab = tsblist._tsb_table(); seen = set()
    for sc in json.load(open(spec))["programs"]:
        lines = [l.rstrip("\n") for l in open(os.path.join(ROOT, sc["bas"])) if l.strip() and not l.startswith(";")]
        for st in sc.get("steps", []):
            for t in st.get("type", "").split("\r"):
                t = t.replace("\u0093", "").strip()
                if t: lines.append(t if re.match(r"\d", t) else "0 " + t)
        for l in lines:
            num, _, text = l.partition(" ")
            seen |= tokens(tsblist.crunch(text, tab), words)
    tsb = [w for w in words if not w.startswith(">")]
    miss_t = [w for w in tsb if ("TSB", w) not in seen]
    miss_v = [w for w in tsblist.V2 if ("V2", w) not in seen]
    print(f"TSB keywords: {len(tsb) - len(miss_t)}/{len(tsb)} covered; missing: {' '.join(miss_t) or '-'}")
    print(f"BASIC V2 tokens: {len(tsblist.V2) - len(miss_v)}/{len(tsblist.V2)} covered; missing: {' '.join(miss_v) or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
