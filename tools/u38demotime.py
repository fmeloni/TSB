#!/usr/bin/env python3
"""Phase B2.1: time corpus demos by their goldens. From RUN until the display first equals the scenario's golden
checkpoint (all compared parts), counted in CPU cycles (CIA 2 timers A+B as in tools/u38bench.py) and in frames.

Usage: u38demotime.py [--crt FILE] [--video pal|ntsc] [--out results.json] scenario-id ...
Only for scenarios whose golden has one checkpoint and whose steps need no typing."""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vicemon, demo_capture  # noqa: E402

ROOT = demo_capture.ROOT


def golden_parts(gdir):
    cp = sorted(x for x in os.listdir(gdir) if os.path.isdir(os.path.join(gdir, x)))[-1]
    out = {}
    for k in demo_capture.PARTS:
        f = os.path.join(gdir, cp, k + ".bin")
        out[k] = open(f, "rb").read() if os.path.exists(f) else b""
    return out


def run(sc, crt, d64):
    want = golden_parts(os.path.join(ROOT, "tests/golden", sc["id"]))
    rom = os.path.join(ROOT, "tests/golden", sc["id"])
    names = demo_capture.raw_names(d64)
    with vicemon.Vice(crt=crt, d64=d64, timeout=1800) as v:
        demo_capture.wait_stable(v, 60, 1200)
        v.type(b'LOAD"' + names[sc["name"]] + b'",8\r')
        demo_capture.wait_stable(v, 30, 3000)          # loaded, READY.
        v.type("run\r")
        v.frames(1, addr=0xA871)
        v.poke(0xDD0E, [0x00], "io"); v.poke(0xDD0F, [0x00], "io")
        v.poke(0xDD04, [0xFF, 0xFF, 0xFF, 0xFF], "io")
        v.poke(0xDD0F, [0x51], "io"); v.poke(0xDD0E, [0x11], "io")
        frames = 0
        while frames < 20000:
            v.frames(1); frames += 1
            st = demo_capture.grab(v)
            if all(getattr(st, k) == want[k] or (k == "charset" and not want[k]) for k in demo_capture.PARTS
                   if k not in sc.get("ignore", [])) and demo_capture.machine_screen(st.screen) == want["screen"]:
                t = v.mem(0xDD04, 0xDD07, "io")
                cyc = (0xFFFF - (t[2] | t[3] << 8)) * 0x10000 + (0xFFFF - (t[0] | t[1] << 8))
                return {"frames": frames, "cycles": cyc}
        return {"frames": None, "cycles": None}


def main(a):
    crt, out, ids = os.path.join(ROOT, "build/TSBneo.crt"), None, []
    i = 0
    while i < len(a):
        if a[i] == "--crt": crt = a[i + 1]; i += 2
        elif a[i] == "--out": out = a[i + 1]; i += 2
        elif a[i] in ("--video",): os.environ["C64_VIDEO"] = a[i + 1]; i += 2
        else: ids.append(a[i]); i += 1
    scen = json.load(open(os.path.join(ROOT, "tests/demos.json")))["programs"]
    for s in scen: s.setdefault("id", demo_capture.slug(s.get("name") or ""))
    res = {}
    for s in [s for s in scen if s["id"] in ids]:
        r = run(s, crt, os.path.join(ROOT, "corpus/tsbneo_260228.d64"))
        res[s["id"]] = r
        print(f"{s['id']:20} {r}", flush=True)
    if out: json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
