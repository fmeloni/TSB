#!/usr/bin/env python3
"""Debug aid for the Ultra-38 flash spike: run a program, stop at a label, single-step and print the last N
instructions with CPU port and flash bank (core_bank, $DF0B).

Usage: trace38f.py <crt> <img.lbl> <prog.bas> <start label|$addr> [steps] [stop addrs,...] [history]"""
import collections, re, struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vicemon, demo_capture  # noqa: E402


def labels(p):
    d = {}
    for ln in open(p):
        m = re.match(r"\s*([A-Za-z_][\w.]*)\s*=\s*\$([0-9a-fA-F]+)", ln)
        if m: d[m.group(1)] = int(m.group(2), 16)
    return d


def main(a):
    crt, lbl, bas, start = a[:4]
    steps = int(a[4]) if len(a) > 4 else 3000
    stops = {int(x.lstrip("$"), 16) for x in a[5].split(",")} if len(a) > 5 and a[5] else set()
    hist = int(a[6]) if len(a) > 6 else 60
    L = labels(lbl); inv = {}
    for k, v in L.items(): inv.setdefault(v, k)
    with vicemon.Vice(crt=crt, timeout=3600) as v:
        demo_capture.inject_and_run(v, bas)
        addr = L[start] if start in L else int(start.lstrip("$"), 16)
        c = v.checkpoint(addr); v.resume(); v.wait_stopped(); v.delete_checkpoint(c)
        h = collections.deque(maxlen=hist)
        why = "steps done"
        for n in range(steps):
            r = v.registers(); pc = r[3]
            port = v.mem(1, 1, "cpu")[0]; bank = v.mem(0xDF0B, 0xDF0B, "cpu")[0]
            h.append((pc, port, bank, r[0], r[1], r[2], r[4]))
            if pc in stops: why = "stop address"; break
            if v.mem(pc, pc, "cpu")[0] == 0: why = "BRK"; break
            v.cmd(0x71, struct.pack("<BH", 0, 1)); v.wait_stopped()
        print(why, "after", n, "steps")
        for pc, p, b, A, X, Y, S in h:
            print(f"{pc:04X} {inv.get(pc, ''):16} port {p:02X} bank {b} A {A:02X} X {X:02X} Y {Y:02X} SP {S:02X}")


if __name__ == "__main__":
    main(sys.argv[1:])
