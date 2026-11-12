#!/usr/bin/env python3
"""Phase B2.1: measure the cycles of each Ultra-38 stub path in the B2.1 spike: CIA 2 (timer A+B as a 32-bit cycle
counter) read at two exec checkpoints (the emulator stops between instructions, so stopping adds no cycles).
Usage: u38stubcost.py [crt] [img.lbl] [bench.bas]"""
import os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vicemon, demo_capture, u38bench  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cia(v):
    t = v.mem(0xDD04, 0xDD07, "io")
    return (0xFFFF - (t[2] | t[3] << 8)) * 0x10000 + (0xFFFF - (t[0] | t[1] << 8))


def span(v, a, b, n=5):
    """cycles from executing a (first instruction) until b is about to execute, n samples (median)."""
    out = []
    for _ in range(n):
        c = v.checkpoint(a); v.resume(); v.wait_stopped(); v.delete_checkpoint(c); t0 = cia(v)
        if callable(b): b = b(v)
        c = v.checkpoint(b); v.resume(); v.wait_stopped(); v.delete_checkpoint(c); t1 = cia(v)
        out.append(t1 - t0)
    out.sort(); return out[len(out) // 2]


def main(a):
    crt = a[0] if a else os.path.join(ROOT, "build/u38_b21.crt")
    L = u38bench.labels(a[1] if len(a) > 1 else os.path.join(ROOT, "build/u38/b21/img.lbl"))
    bas = a[2] if len(a) > 2 else os.path.join(ROOT, "tests/bench/tsb_flow.bas")
    with vicemon.Vice(crt=crt, timeout=600) as v:
        demo_capture.inject_and_run(v, bas)
        v.poke(0xDD0E, [0], "io"); v.poke(0xDD0F, [0], "io"); v.poke(0xDD04, [0xFF] * 4, "io")
        v.poke(0xDD0F, [0x51], "io"); v.poke(0xDD0E, [0x11], "io")
        ret = lambda v: (lambda s: (v.mem(0x101 + s, 0x102 + s, "cpu")[0] | v.mem(0x101 + s, 0x102 + s, "cpu")[1] << 8) + 1)(v.registers()[4] & 0xFF)
        res = {}
        res["entry IGONE: u_igone .. TSB's handler"] = span(v, L["u_igone"], L["sbasbef"]) + 3   # + Neo's own vector jmp is the same: +0
        res["entry IEVAL: u_ieval .. TSB's handler"] = span(v, L["u_ieval"], L["sgetari"])
        res["exit RX: thunk .. BASIC ROM target ($A7E7)"] = span(v, L["rx_a7e7"], 0xA7E7)
        rcs = [k for k in L if re.match(r"rc_[0-9a-f]{4}$", k)]
        best = None
        for k in ("rc_ad8a", "rc_b7f7", "rc_aefd", "rc_b79e") :
            if k in L: best = k; break
        res[f"ROM call RC ({best}): thunk .. back at the caller"] = span(v, L[best], ret) if best else None
        res["IRQ: u_irq .. KERNAL $EA31 (minus TSB's own handler)"] = span(v, L["u_irq"], 0xEA31) - span(v, L["sirq"], L["c_irq"] + 0)
        for k, x in res.items(): print(f"{k:60} {x}")


if __name__ == "__main__":
    main(sys.argv[1:])
