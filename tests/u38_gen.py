#!/usr/bin/env python3
"""Phase B2: static checks of the Ultra-38 builds (make build has made them).

  - B2.1 speed spike (build/u38/b21): every TSB Neo label at the same address as in TSB Neo (the rewrite keeps sizes),
    the thunk area below $8000, the RAM core within $DF0B-$DFFD;
  - B2.2 flash spike (build/u38/fl): RAM core within $DF0B-$DFFD, every bank's part + extras below the common block
    (ACME also stops on this).
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def labels(p):
    d = {}
    for ln in open(p):
        m = re.match(r"\s*([A-Za-z_][\w.]*)\s*=\s*\$([0-9a-fA-F]+)", ln)
        if m: d[m.group(1)] = int(m.group(2), 16)
    return d


def main():
    bad = []
    b21, neo = os.path.join(ROOT, "build/u38/b21/img.lbl"), os.path.join(ROOT, "build/b1/neo.lbl")
    if not os.path.exists(b21) or not os.path.exists(neo):
        print("SKIP u38_gen: build/u38 missing (make build)"); return 0
    a, b = labels(neo), labels(b21)
    moved = [k for k in a if k in b and a[k] != b[k]]
    if moved: bad.append(f"B2.1: {len(moved)} TSB Neo labels moved, e.g. {moved[:5]}")
    if b["u38_area_end"] > 0x8000: bad.append("B2.1: thunk area overflows into $8000")
    df = b["u38_df_end"] - b["u38_df_image"]
    if df > 0xDFFE - 0xDF0B: bad.append(f"B2.1: RAM core {df} bytes > 243")
    f = labels(os.path.join(ROOT, "build/u38/fl/img.lbl"))
    parts = json.load(open(os.path.join(ROOT, "build/u38/fl/parts.json")))
    dff = f["u38_df_end"] - f["u38_df_image"]
    if dff > 0xDFFE - 0xDF0B: bad.append(f"B2.2: RAM core {dff} bytes > 243")
    for k, s, e, bank in parts:
        if bank and f["%s_x_end" % k] > f["common_start"]: bad.append(f"B2.2: bank {bank} overflows")
    used = max(f["%s_x_end" % k] for k, s, e, bank in parts if bank)
    print(f"B2.1: {len(a)} TSB Neo labels unchanged, thunk area ${b['u38_area_end'] - 0x6000:04X} bytes, RAM core {df} bytes")
    print(f"B2.2: {sum(1 for p in parts if p[3])} TSB banks, highest part+extras end ${used:04X}, common block "
          f"${f['common_start']:04X}-${f['common_end'] - 1:04X}, RAM core {dff} bytes (243 available)")
    for x in bad: print("  FAIL " + x)
    print(("PASS" if not bad else "FAIL") + " u38_gen")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
