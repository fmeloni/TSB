#!/usr/bin/env python3
"""Phase B2.1: cycle-exact benchmark timing on TSB Neo, the B2.1 speed spike and a stock C64.

Usage: u38bench.py [--crt FILE | --stock] [--video pal|ntsc] [--events LBL] [--out results.json] bench.bas ...

Each program is tokenized and poked to $0801 (as in the command suite). Before RUN, MEMSIZ is set to $6000 on every
system (the spike keeps its thunks at $6000-$7FFF), so all of them have the same string space and garbage-collection
work. Timing: CIA 2 timer A counts cycles, timer B counts timer A underflows (32-bit counter, no interrupts: CIA 2's
ICR mask stays clear); started when BASIC's RUN handler ($A871) is reached, read when BASIC's main loop (the IMAIN
vector target) is reached again. Cycles = elapsed - the few cycles of the start sequence (constant, cancels in
comparisons). With --events (the spike's ACME label file), non-stopping exec checkpoints count how often each
Ultra-38 stub runs (entries, exits, ROM calls, far calls, ...).
"""
import json, os, re, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vicemon, demo_capture, tsblist, neoprofile  # noqa: E402

# stub label -> event name (counted with non-stopping checkpoints in the spike)
EVENTS = {"u_igone": "entry IGONE", "u_ieval": "entry IEVAL", "u_cold": "entry cold (IERROR IMAIN ICRNCH IQPLOP BRK LOAD SAVE)",
          "u_irq": "IRQ", "u_nmi": "NMI", "rc_stub": "ROM call (RC, RT, RCS)", "rx_stub": "exit (RX)",
          "c_xcall": "far call (FC)", "c_xjump": "far jump (FJ)", "ev_ret": "return trampoline (ev_ret)",
          "rc_help": "ROM call via pspeibe"}


def labels(path):
    out = {}
    for ln in open(path):
        m = re.match(r"\s*([A-Za-z_][\w.]*)\s*=\s*\$([0-9a-fA-F]+)", ln)
        if m: out[m.group(1)] = int(m.group(2), 16)
    return out


def run(bas, crt, events=None):
    with vicemon.Vice(crt=crt, timeout=1800) as v:
        demo_capture.wait_stable(v, 60, 1200)
        lines = [l.rstrip("\n") for l in open(bas, encoding="utf-8") if l.strip() and not l.lstrip().startswith(";")]
        prg = tsblist.make_prg(lines)
        v.poke(0x0801, prg[2:], "ram")
        end = 0x0801 + len(prg) - 2
        for z in (0x2D, 0x2F, 0x31): v.poke(z, [end & 255, end >> 8], "ram")
        v.poke(0x37, [0x00, 0x60], "ram")          # MEMSIZ $6000 everywhere (RUN's CLR sets FRETOP from it)
        ids = {}
        if events:
            for lab, name in EVENTS.items():
                if lab in events: ids[lab] = neoprofile.cp_add(v, events[lab])
        v.type("run\r")
        v.frames(1, addr=0xA871)    # returns at the first hit of $A871 (RUN handler)
        imain = int.from_bytes(v.mem(0x0302, 0x0303, "cpu"), "little")
        # CIA 2: stop, latches $FFFF, timer B counts timer A underflows, force-load both, start
        v.poke(0xDD0E, [0x00], "io"); v.poke(0xDD0F, [0x00], "io")
        v.poke(0xDD04, [0xFF, 0xFF, 0xFF, 0xFF], "io")
        v.poke(0xDD0F, [0x51], "io")    # start, force load, count timer A underflows
        v.poke(0xDD0E, [0x11], "io")    # start, force load, continuous, count system cycles
        stop = v.checkpoint(imain)
        while True:
            v.resume(); pc = v.wait_stopped()
            if pc == imain: break
        t = v.mem(0xDD04, 0xDD07, "io")
        ta, tb = t[0] | t[1] << 8, t[2] | t[3] << 8
        cycles = (0xFFFF - tb) * 0x10000 + (0xFFFF - ta)
        counts = {EVENTS[l]: neoprofile.cp_hits(v, c) for l, c in ids.items()}
        st = demo_capture.grab(v).extras()
        return {"cycles": cycles, "events": counts, "screen": "\n".join(st.lines()), "vars": st.vars.decode()}


def main(a):
    crt, out, ev, progs = os.path.join(neoprofile.ROOT, "build", "TSBneo.crt"), None, None, []
    i = 0
    while i < len(a):
        if a[i] == "--crt": crt = a[i + 1]; i += 2
        elif a[i] == "--stock": crt = None; i += 1
        elif a[i] == "--out": out = a[i + 1]; i += 2
        elif a[i] == "--events": ev = labels(a[i + 1]); i += 2
        elif a[i] in ("--video", "--kernal", "--dos"): os.environ["C64_" + a[i][2:].upper()] = a[i + 1]; i += 2
        else: progs.append(a[i]); i += 1
    res = {}
    for p in progs:
        r = run(p, crt, ev)
        res[os.path.basename(p)] = r
        print("%-16s %10d cycles  %s" % (os.path.basename(p), r["cycles"], json.dumps(r["events"]) if r["events"] else ""),
              flush=True)
    if out: json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
