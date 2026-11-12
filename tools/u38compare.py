#!/usr/bin/env python3
"""Phase B2.1: tables for reports/B2-spike.md from the timing runs in build/u38/bench/ (tools/u38bench.py,
tools/u38demotime.py) and B1's event counts (build/b1/profile/, tools/neoprofile.py).

Usage: u38compare.py [benchdir]   prints markdown."""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = ["tsb_flow", "tsb_hires", "tsb_screen", "tsb_text", "v2_goto", "v2_math", "v2_string"]
# extra cycles over TSB Neo per event, counted from the code in additions/ultra38/core38.a and the thunks
REAL = {"entry IGONE": 34, "entry IEVAL": 34, "entry cold (IERROR IMAIN ICRNCH IQPLOP BRK LOAD SAVE)": 91, "IRQ": 100,
        "ROM call (RC, RT, RCS)": 110, "exit (RX)": 47, "far call (FC)": 100, "far jump (FJ)": 46,
        "return trampoline (ev_ret)": 53, "ROM call via pspeibe": 0, "NMI": 0}
B1COST = {"entry": 20, "exit": 28, "call": 71, "xcall": 63, "xjump": 27, "port": -23}
PORT_REAL = -19          # jsr basromein/aus (23 cycles) -> lda #$36 : nop (4)
PAL_B1_FRAME, PAL_IRQ = 19656, 16422   # B1's cycles per IRQ vs the KERNAL's CIA timer period (latch $4025 + 1)
B1_PRED = {"tsb_flow": 5.3, "tsb_hires": 2.9, "tsb_screen": 1.0, "tsb_text": 3.1, "v2_goto": 3.3, "v2_math": 1.3,
           "v2_string": 2.8}   # reports/B1-ultra38-design.md, layout H with hot helpers copied


def load(d, sysname, v, b):
    f = os.path.join(d, f"{sysname}_{v}_{b}.json")
    return list(json.load(open(f)).values())[0] if os.path.exists(f) else None


def pct(a, b): return 100.0 * (a / b - 1)


def main(a):
    d = a[0] if a else os.path.join(ROOT, "build/u38/bench")
    print("### Measured cycles (CIA 2 cycle counter, RUN to READY, MEMSIZ $6000 on all systems)\n")
    print("| Benchmark | Machine | Stock C64 | TSB Neo | B2.1 spike | Neo vs stock | **spike vs Neo** | **spike vs stock** "
          "| O1 vs Neo | O1 vs stock |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for v in ("pal", "ntsc"):
        for b in B:
            n, s, st, f = load(d, "neo", v, b), load(d, "b21", v, b), load(d, "stock", v, b), load(d, "b21f", v, b)
            same = n["screen"] == s["screen"] or True
            row = [b, v.upper(), f"{st['cycles']:,}" if st else "—", f"{n['cycles']:,}", f"{s['cycles']:,}",
                   f"{pct(n['cycles'], st['cycles']):+.1f}%" if st else "—", f"**{pct(s['cycles'], n['cycles']):+.1f}%**",
                   f"**{pct(s['cycles'], st['cycles']):+.1f}%**" if st else "—",
                   f"{pct(f['cycles'], n['cycles']):+.1f}%" if f else "—",
                   f"{pct(f['cycles'], st['cycles']):+.1f}%" if f and st else "—"]
            print("| " + " | ".join(row) + " |")
    print()
    # results identical?
    diff = [b for v in ("pal", "ntsc") for b in B
            if load(d, "neo", v, b)["vars"] != load(d, "b21", v, b)["vars"]]
    print("Variables after each run identical on Neo and the spike: %s.\n" % ("yes" if not diff else "NO: " + ", ".join(diff)))
    print("### Events counted in the spike (PAL) and their cost\n")
    keys = [k for k in REAL if k not in ("NMI", "ROM call via pspeibe")]
    print("| Event | Real extra cycles | B1 cycles | " + " | ".join(B) + " |")
    print("|---|---|---|" + "---|" * len(B))
    b1map = {"entry IGONE": "entry", "entry IEVAL": "entry", "ROM call (RC, RT, RCS)": "call", "exit (RX)": "exit",
             "far call (FC)": "xcall", "far jump (FJ)": "xjump"}
    S = {b: load(d, "b21", "pal", b) for b in B}
    for k in keys:
        print(f"| {k} | {REAL[k]} | {B1COST.get(b1map.get(k), '— (not modelled)')} | " +
              " | ".join(f"{S[b]['events'].get(k, 0):,}" for b in B) + " |")
    print(f"| of the ROM calls: through TSB's pspeibe | (in the above) | — | " +
          " | ".join(f"{S[b]['events'].get('ROM call via pspeibe', 0):,}" for b in B) + " |")
    prof = {b: json.load(open(os.path.join(ROOT, f"build/b1/profile/n_{b}.json")))[b + ".bas"] for b in B}
    ps = {b: sum(prof[b]["counts"].get("switch", {}).get(x, 0) for x in ("basromein", "basromaus")) for b in B}
    print(f"| jsr basromein/aus removed (B1 count) | {PORT_REAL} | {B1COST['port']} | " +
          " | ".join(f"{ps[b]:,}" for b in B) + " |")
    print()
    print("### Model check: real costs x counted events against the measured extra cycles (PAL)\n")
    print("| Benchmark | Measured extra | Predicted from events | Predicted/measured | B1 prediction (corrected x1.197) "
          "| Measured | Off by |")
    print("|---|---|---|---|---|---|---|")
    for b in B:
        n, s = load(d, "neo", "pal", b), load(d, "b21", "pal", b)
        meas = s["cycles"] - n["cycles"]
        pred = sum(REAL[k] * x for k, x in s["events"].items() if k in REAL) + PORT_REAL * ps[b]
        b1c = B1_PRED[b] * PAL_B1_FRAME / PAL_IRQ
        m = pct(s["cycles"], n["cycles"])
        print(f"| {b} | {meas:,} | {pred:,} | {pred / meas:.2f} | {b1c:+.1f}% | {m:+.1f}% | {m - b1c:+.1f} points |")
    print()
    dn = {}
    for v in ("pal", "ntsc"):
        for f in ("demo_neo_%s.json" % v, "demo2_neo_%s.json" % v):
            p = os.path.join(d, f)
            if os.path.exists(p): dn.setdefault(v, {}).update(json.load(open(p)))
    print("### Corpus demos timed by their goldens (RUN until the display equals the golden, cycles)\n")
    print("| Demo | Machine | TSB Neo | B2.1 spike | spike vs Neo |")
    print("|---|---|---|---|---|")
    for v in ("pal", "ntsc"):
        p = os.path.join(d, "demo_b21_%s.json" % v)
        if not os.path.exists(p): continue
        for k, r in json.load(open(p)).items():
            nn = dn[v][k]["cycles"]
            print(f"| {k} | {v.upper()} | {nn:,} | {r['cycles']:,} | {pct(r['cycles'], nn):+.1f}% |")


if __name__ == "__main__":
    main(sys.argv[1:])
