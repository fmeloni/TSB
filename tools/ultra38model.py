#!/usr/bin/env python3
"""Slowdown prediction for Ultra-38 (phase B1) from the TSB Neo event counts of tools/neoprofile.py.

Usage: ultra38model.py <profile.json> ... [--md]

Two layouts are modelled (reports/B1-ultra38-design.md, "Two layouts"):
  N  Neo's addresses kept: core in ROML $8000, commands in ROMH $A000 (EasyFlash 16K mode, $01=$37), so BASIC RAM
     $8000-$9FFF is hidden while TSB code runs.
  H  TSB code only in 8K ROMH windows at $A000 ($01=$36): BASIC RAM $0000-$9FFF stays visible; Neo's core
     ($8000-$9FFF) and its commands ($A000-$BFFF) end up in different flash banks.
Each event costs the extra cycles below over what Neo spends on it (stub sketches and counts in the report).
"""
import collections, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import neoinventory, neoprofile  # noqa: E402

COST = {
    # Extra cycles over Neo per event. Counted from the stub sketches in reports/B1-ultra38-design.md.
    "entry_N": 9,         # vector -> RAM stub: lda #$07 / sta $DE02 / jmp target
    "entry_H": 20,        # + lda #bank / sta $DE00 and lda #$36 / sta $01
    "exit_N": 23,         # TSB jmp into the BASIC ROM: php pha lda #4 sta $DE02 pla plp jmp
    "exit_H": 28,         # + lda #$37 / sta $01
    "call_N": 61,         # TSB jsr into the BASIC ROM: flash thunk (19) + RAM stub, cartridge off and on again
    "call_H": 71,         # + $01 to $37 and back to $36
    "port_switch": -23,   # Neo's basromein/basromaus calls disappear (each was jsr+lda+ora+bne+sta+rts)
    # layout N only
    "chrget_N": 20,       # TSB's CHRGET/CHRGOT calls must see RAM at $8000-$9FFF: cartridge off around them
    "ptr_N": 10,          # every TSB (zp),y access: page check (fast path); the slow path is extra, not counted
    # layout H only
    "xcall_H": 63,        # JSR between core bank and command bank: flash thunk (18) + RAM far-call stub
    "xjump_H": 27,        # JMP between them (no return)
}


def events(r, inv):
    c = r["counts"]
    kind = {int(x["at"], 16): x["kind"] for x in inv["rom_calls"]}
    ev = collections.Counter()
    ev["entries"] = sum(n for k, n in c.get("entry", {}).items() if k not in ("sloop", "warmstart"))
    for key, n in r["sites"].items():
        cat, addr, tag = key.split(" ", 2)
        addr = int(addr, 16)
        if cat == "rom" and ">basic" in tag:
            ev["rom_jsr" if kind[addr] == "jsr" else "rom_jmp"] += n
        if cat == "xreg":
            k, path, name = tag.split(" ")
            if {"8000", "A000"} == set(path.split(">")) or "C000" in path:
                ev["x_" + k] += n
                ev["xname:" + name] += n
                ev["x%s:%s" % (k, name)] += n
    sw = c.get("switch", {})
    ev["port_switch"] = sw.get("basromein", 0) + sw.get("basromaus", 0)
    zp = c.get("zpcall", {})
    ev["chrget"] = sum(n for k, n in zp.items() if k.endswith(("0073", "0079")))
    ev["ptr"] = sum(c.get("ptr", {}).values())
    ev["ptr_screen"] = sum(n for k, n in c.get("ptr", {}).items() if "($20)" in k or "($23)" in k)
    return ev


def predict(ev, dup=()):
    sw = ev["port_switch"] * COST["port_switch"]
    n = sw + ev["rom_jsr"] * COST["call_N"] + ev["rom_jmp"] * COST["exit_N"] + ev["entries"] * COST["entry_N"] \
        + ev["chrget"] * COST["chrget_N"] + ev["ptr"] * COST["ptr_N"]
    both = sw + ev["rom_jsr"] * COST["call_H"] + ev["rom_jmp"] * COST["exit_H"]
    h_all = both + ev["entries"] * COST["entry_H"] + ev["x_jsr"] * COST["xcall_H"] + ev["x_jmp"] * COST["xjump_H"]
    # with the hot helpers copied into every bank, calls to them stay in the bank
    dj = sum(ev.get("xjsr:" + d, 0) for d in dup)
    dm = sum(ev.get("xjmp:" + d, 0) for d in dup)
    h_dup = h_all - dj * COST["xcall_H"] - dm * COST["xjump_H"]
    return n, h_all, h_dup


def main(a):
    md = "--md" in a
    files = [x for x in a if not x.startswith("--")]
    inv = neoinventory.inventory(neoprofile.report())
    res = {}
    for f in files: res.update(json.load(open(f)))
    # hot helpers: callees covering 90% of all cross-region calls over all benchmarks
    tot = collections.Counter()
    evs = {b: events(r, inv) for b, r in res.items()}
    for ev in evs.values():
        for k, n in ev.items():
            if k.startswith("xname:"): tot[k[6:]] += n
    dup, cum, T = [], 0, sum(tot.values()) or 1
    for name, n in tot.most_common():
        if cum / T >= 0.90: break
        dup.append(name); cum += n
    rows = []
    for b in sorted(res):
        cyc = res[b]["cycles"]; ev = evs[b]
        n, h_all, h_dup = predict(ev, dup)
        rows.append((b, res[b]["frames"], cyc, ev, n / cyc, h_all / cyc, h_dup / cyc))
    if md:
        print("| Benchmark | Neo frames | Entries | ROM jsr | ROM jmp | Neo $01 calls | CHRGET | (zp) accesses | "
              "core-command jsr/jmp | N | H, no copies | H, hot helpers copied |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for b, fr, cyc, ev, pn, ph, phd in rows:
            print(f"| {b[:-4]} | {fr} | {ev['entries']:,} | {ev['rom_jsr']:,} | {ev['rom_jmp']:,} | "
                  f"{ev['port_switch']:,} | {ev['chrget']:,} | {ev['ptr']:,} | {ev['x_jsr']:,}/{ev['x_jmp']:,} | "
                  f"{pn:+.1%} | {ph:+.1%} | {phd:+.1%} |")
        print()
        print("Hot helpers copied into every bank (%d, %.0f%% of cross calls): %s" % (len(dup), 100 * cum / T,
                                                                                  ", ".join(dup)))
    else:
        for b, fr, cyc, ev, pn, ph, phd in rows:
            print(f"{b:16s} frames {fr:5d}  N {pn:+6.1%}  H {ph:+6.1%}  H+copies {phd:+6.1%}")
        print("copied:", dup)


if __name__ == "__main__":
    main(sys.argv[1:])
