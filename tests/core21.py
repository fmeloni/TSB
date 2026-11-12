#!/usr/bin/env python3
"""Task 2.1: run the bank-switching core spike CRT (build/spike21.crt) and check its results.

  tests/core21.py [--video pal|ntsc|oldntsc] [--kernal stock|jiffy] [--dos stock|jiffy] [crt] [labels]

The spike (additions/ultra/spike21.a) runs its tests T1-T7 once after reset and loops at done_loop with
the results at res_* ($0340). This runs it in VICE until done_loop, then checks every error counter, the
stress counts and the cycle counts. Prints a table of the measured cycles."""
import os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import vicemon

ERRS = ["map (fill/verify $0800-$cfff)", "RAM under the cartridge via MODE_ALL", "flash visible in MODE_HOME",
        "page-crossing pointers", "RAM under I/O", "RAM under the KERNAL", "registers/flags",
        "far calls", "IRQ hook checks", "NMI hook checks", "$df00-$df0a guard", "slow-RAM counters = hook counts"]
CYC = [  # (label, expected cycles or None = measured only)
    ("empty (timer overhead)", None), ("lda (zp),y native", 5), ("FETCH $1000 (fast)", None),
    ("FETCH $c800 (fast)", None), ("FETCH $9000 (slow)", None), ("sta (zp),y native", 6),
    ("STORE $1000 (fast)", None), ("STORE $c800 (fast)", None), ("STORE $9000 (slow)", None),
    ("IOFETCH $d800", None), ("IOSTORE $d800", None), ("jsr+rts native", 12),
    ("far call to an rts in bank 1", None), ("FETCH $7f80+$c0 (slow, $7f page)", None)]


def labels(path):
    out = {}
    for line in open(path):
        m = re.match(r"\s*(\w+)\s*=\s*\$([0-9a-fA-F]+)", line)
        if m: out[m.group(1)] = int(m.group(2), 16)
    return out


def main(a):
    args = []
    while a:
        x = a.pop(0)
        if x in ("--video", "--kernal", "--dos"): os.environ["C64_" + x[2:].upper()] = a.pop(0)
        else: args.append(x)
    crt = args[0] if args else os.path.join(ROOT, "build/spike21.crt")
    lbl = labels(args[1] if len(args) > 1 else os.path.join(ROOT, "build/spike21.lbl"))
    if not os.path.exists(crt): print(f"SKIP core21: {crt} missing"); return 0
    name = vicemon.machine_name()
    with vicemon.Vice(crt=crt, timeout=int(os.environ.get("CORE21_TIMEOUT", "120"))) as v:
        cid = v.checkpoint(lbl["done_loop"])
        v.resume(); v.wait_stopped(); v.delete_checkpoint(cid)
        res = v.mem(lbl["RES"], lbl["RES"] + lbl["RES_LEN"] - 1, "ram")
    R = lambda name, n=1: int.from_bytes(res[lbl[name] - lbl["RES"]:lbl[name] - lbl["RES"] + n], "little")
    bad = []
    if res[0:3] != b"C21": bad.append(f"no start marker ({res[0:3]!r})")
    if R("res_state") != 1: bad.append("not finished")
    for i, what in enumerate(ERRS):
        n = int.from_bytes(res[4 + 2 * i:6 + 2 * i], "little")
        if n:
            first = int.from_bytes(res[100 + 2 * i:102 + 2 * i], "little")
            bad.append(f"{what}: {n} error(s), first at ${first:04X}")
    irqs, nmis, iters = R("res_irqs", 3), R("res_nmis", 3), R("res_iters")
    if iters != 16: bad.append(f"stress iterations {iters} != 16")
    if irqs < 10000 or nmis < 10000: bad.append(f"too few interrupts in the stress test: {irqs} IRQ, {nmis} NMI")
    raw = [int.from_bytes(res[36 + 2 * i:38 + 2 * i], "little") for i in range(len(CYC))]
    cyc = [0xFFFF - r for r in raw]; over = cyc[0]
    print(f"machine: {name}")
    print(f"stress: {iters} iterations, {irqs} IRQs, {nmis} NMIs (hooks used FETCH/STORE), last IRQ port ${R('res_port'):02X}")
    print("cycles (overhead removed):")
    for i, (what, want) in enumerate(CYC[1:], 1):
        c = cyc[i] - over
        print(f"  {what:34} {c:4}")
        if want is not None and c != want: bad.append(f"cycle check: {what} = {c}, expected {want}")
    for b in bad: print("  FAIL " + b)
    print(("PASS" if not bad else "FAIL") + f" core21 ({name})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
