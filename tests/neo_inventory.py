#!/usr/bin/env python3
"""Phase B1: the static inventory of TSB Neo that the Ultra-38 design rests on (tools/neoinventory.py) still holds.
A change to TSBneo/tsbneo.a or to the inventory tool that moves these numbers needs reports/B1-ultra38-design.md
checked again."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import neoinventory, neoprofile  # noqa: E402

inv = neoinventory.inventory(neoprofile.report())
s = inv["rom_call_summary"]
got = {
    "rom call sites": s["sites"],
    "distinct BASIC routines": s["distinct_basic"],
    "BASIC calls from $A000-$BFFF code": s["by_region_and_rom"].get("A000->basic", 0),
    "code-area write targets": inv["code_area_write_targets"],
    "pointer sites": len(inv["pointer_sites"]),
    "port writes": len(inv["port_writes"]),
}
want = {"rom call sites": 227, "distinct BASIC routines": 57, "BASIC calls from $A000-$BFFF code": 0,
        "code-area write targets": 18, "pointer sites": 218, "port writes": 10}
bad = [k for k in want if got[k] != want[k]]
for k in want:
    print(("ok   " if got[k] == want[k] else "FAIL ") + f"{k}: {got[k]} (expected {want[k]})")
print(("FAIL" if bad else "PASS") + " neo_inventory")
sys.exit(1 if bad else 0)
