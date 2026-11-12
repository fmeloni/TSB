#!/usr/bin/env python3
"""Count, on TSB Neo, the events the Ultra-38 design pays for (phase B1).

Usage: neoprofile.py [--crt build/TSBneo.crt] [--out results.json] [--stock] bench.bas ...

Each program is tokenized and RUN (as in the command suite). From RUN to the return to TSB's main loop
(IMAIN), VICE exec checkpoints that do not stop the CPU count:
  - entries from BASIC/KERNAL into TSB (the six BASIC vectors, IRQ, NMI, LOAD/SAVE vectors);
  - TSB command and function dispatches;
  - every TSB call site into the BASIC ROM and the KERNAL (static list from tools/neoinventory.py);
  - every JSR/JMP between TSB's regions $8000-$9FFF, $A000-$BFFF and $C000-$CFFF;
  - every pointer-indirect instruction in TSB code ((zp),y and (zp,x)), by zero-page pointer;
  - the bank switch helpers (basromein/basromaus/kerromein/kerromaus/charen0/charen1).
$A000-$BFFF checkpoints count only with $01 bit 0 clear (BASIC ROM out).
Elapsed time = IRQ count (frames) from RUN to the end, times the cycles per frame (PAL 19656, NTSC 17095).
--stock runs the same program on a stock C64 (no cartridge) for the time only.
Needs the ACME report of TSBneo/tsbneo.a; it is made in build/b1/ when missing.
"""
import collections, json, os, struct, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vicemon, demo_capture, neoinventory  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REP = os.path.join(ROOT, "build", "b1", "neo.rep")
FRAME = {"pal": 312 * 63, "ntsc": 263 * 65}


def report():
    if not os.path.exists(REP):
        os.makedirs(os.path.dirname(REP), exist_ok=True)
        subprocess.check_call([os.environ.get("ACME", "acme"), "-f", "plain", "-o", REP[:-4] + ".bin", "-r", REP,
                               "tsbneo.a"], cwd=os.path.join(ROOT, "TSBneo"))
    return REP


def sites(inv):
    """name -> list of (address, tag)."""
    lab = inv["labels"]
    s = collections.OrderedDict()
    s["entry"] = [(lab[n], n) for n in ("sloop", "tokenize", "slist", "sbasbef", "sgetari", "warmstart", "sirq",
                                        "snmi", "ssnmi", "sysload", "syssave") if n in lab]
    s["switch"] = [(lab[n], n) for n in ("basromein", "basromaus", "kerromein", "kerromaus", "charen0", "charen1",
                                         "pspeibe")]
    s["rom"] = [(int(c["at"], 16), "%s>%s:%s" % (c["region"], c["rom"], c["target"])) for c in inv["rom_calls"]]
    s["xreg"] = [(int(c["at"], 16), "%s %s>%s %s" % (c["kind"], c["src"], c["dst"], c["name"]))
                 for c in inv["sites"]["jsr_jmp_label"] if c["src"] != c["dst"]]
    s["zpcall"] = [(int(c["at"], 16), "%s %s>%s" % (c["kind"], c["src"], c["to"])) for c in inv["sites"]["zpcall"]]
    s["dispatch"] = [(int(a, 16), "command") for a in inv["sites"]["dispatch"]]
    s["ptr"] = [(int(p["at"], 16), "%s %s ($%s)%s" % (p["region"], "w" if p["write"] else "r", p["zp"],
                                                       "" if p["mn"] else "")) for p in inv["pointer_sites"]]
    return s


def cp_add(v, addr):
    b = v.cmd(0x12, struct.pack("<HHBBBB", addr, addr, 0, 1, 4, 0))  # exec, no stop
    cid = struct.unpack("<I", b[:4])[0]
    if 0xA000 <= addr < 0xC000:
        # TSB's $A000-$BFFF code runs only with the BASIC ROM switched out ($01 bit 0 clear); the same addresses
        # with bit 0 set are BASIC ROM code and must not count.
        c = b"(@cpu:$01 & $01) == $00"
        v.cmd(0x22, struct.pack("<IB", cid, len(c)) + c)
    return cid


def cp_hits(v, cid):
    b = v.cmd(0x11, struct.pack("<I", cid))
    return struct.unpack("<I", b[13:17])[0]


def run_one(bas, crt, inv, stock=False):
    video = vicemon.machine()[0]
    with vicemon.Vice(crt=None if stock else crt, timeout=1800) as v:
        demo_capture.inject_and_run(v, bas)
        imain = int.from_bytes(v.mem(0x0302, 0x0303, "cpu"), "little")
        ids = []
        if not stock:
            for kind, lst in sites(inv).items():
                for addr, tag in lst:
                    ids.append((kind, tag, addr, cp_add(v, addr)))
        stop = v.checkpoint(imain)
        irq = v.checkpoint(0xFF48)
        frames = 0
        while True:
            v.resume(); pc = v.wait_stopped()
            if pc == imain: break
            frames += 1
            if frames > 200000: raise RuntimeError("benchmark did not end")
        counts = collections.OrderedDict()
        per_site = {}
        for kind, tag, addr, cid in ids:
            n = cp_hits(v, cid)
            if n:
                counts.setdefault(kind, collections.Counter())[tag] += n
                per_site["%s %04x %s" % (kind, addr, tag)] = n
        v.delete_checkpoint(stop); v.delete_checkpoint(irq)
    return {"frames": frames, "cycles": frames * FRAME.get(video, FRAME["pal"]),
            "counts": {k: dict(c) for k, c in counts.items()}, "sites": per_site}


def main(a):
    crt, out, stock = os.path.join(ROOT, "build", "TSBneo.crt"), None, False
    progs = []
    i = 0
    while i < len(a):
        if a[i] == "--crt": crt = a[i + 1]; i += 2
        elif a[i] == "--out": out = a[i + 1]; i += 2
        elif a[i] == "--stock": stock = True; i += 1
        else: progs.append(a[i]); i += 1
    inv = neoinventory.inventory(report())
    res = {}
    for p in progs:
        r = run_one(p, crt, inv, stock)
        res[os.path.basename(p)] = r
        tot = {k: sum(c.values()) for k, c in r["counts"].items()}
        print("%-16s frames %6d  %s" % (os.path.basename(p), r["frames"], json.dumps(tot)), flush=True)
    if out: json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
