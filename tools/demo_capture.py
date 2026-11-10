#!/usr/bin/env python3
"""Run programs from a D64 under a cartridge, reach checkpoints, capture or compare golden results.

    tools/demo_capture.py capture [ids...]   write tests/golden/<id>/<NN_label>/ for each scenario (default: all)
    tools/demo_capture.py check   [ids...]   compare against tests/golden/, print PASS/FAIL, exit 1 on any FAIL
    tools/demo_capture.py explore <name> [maxframes]   LOAD+RUN a program, print the first stable screen

Options: --crt FILE (default build/TSBneo.crt), --d64 FILE (default corpus/tsbneo_260228.d64),
         --scenarios FILE (default tests/demos.json), --golden DIR (default tests/golden), -j N (parallel VICEs)

Scenario (tests/demos.json, list "programs"):
    name      directory name of the program to LOAD+RUN       id      golden folder (default: slug of name)
    reu       REU size in KB (VICE -reusize)                   ignore  parts left out of stability and compare
                                                               ("rvs": the screen's reverse bit, for FLASH)
    compare   parts compared (default all: screen color bitmap charset vic sprites [sid])
    mask      [[row, col_from, col_to], ...] screen/colour cells blanked (timing-dependent text)
    reject    regexes that must not appear in any checkpoint's screen text (default: a BASIC error message)
    steps     list, run in order after RUN:
      {"stable": F, "max": M, "change": true}  run until the display has changed (unless change=false) and then
                                stays unchanged for F frames with no disk transfer; fails if not within M frames
      {"end": 1, "max": M}      same with F=60, and BASIC back in direct mode (program finished)
      {"frames": N}             run N frames (KERNAL IRQs, 1/60 s each)
      {"type": "text"}          feed the keyboard buffer ("\\r" = RETURN, lower case = unshifted)
      {"hold": "space", "frames": N}  hold a key in the matrix for N frames (for PEEK(197) polling)
      {"run": "NAME"}           LOAD+RUN another program in the same session (keeps REU contents)
      {"sid": N}                record SID registers every frame for N frames (distinct states -> sid.bin)
    Any step may carry "cap": "label" to capture a checkpoint after it, and "expect": [regex,...] checked
    against that checkpoint's screen text. The state after the last step is always captured as "final".

A checkpoint stores: screen.txt (decoded, for people), screen.bin (1000 bytes of the visible matrix),
color.bin (colour RAM nybbles), bitmap.bin (8000 bytes, bitmap mode only), charset.bin (2K, RAM charsets
only), vic.bin (mode/colour registers), sprites.bin (positions, pointers, data, if any are on), shot.png.
"""
import hashlib, json, os, re, sys, tempfile, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vicemon, tsblist

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PARTS = ["screen", "color", "bitmap", "charset", "vic", "sprites"]
DEFAULT_REJECT = [r"\?[a-z0-9 ]+error"]
KEYS = {"del": 0, "return": 1, "crsrright": 2, "f7": 3, "f1": 4, "f3": 5, "f5": 6, "crsrdown": 7,
        "space": 60, "stop": 63, "q": 62, "1": 56, "2": 59, "ctrl": 58, "c=": 61, "lshift": 15}
for _i, _row in enumerate(["3wa4zse", "5rd6cft", "7yg8bhu", "9ij0mko", "+pl-.:@", "", "", ""]):
    for _j, _c in enumerate(_row): KEYS.setdefault(_c, 8 + _i * 8 + _j)
KEYS.update({"x": 23, "v": 31, "n": 39, ",": 47, "*": 49, ";": 50, "=": 53, "/": 55})


def slug(name):
    s = "".join(c.lower() if c.isalnum() else "_" for c in name)
    return "_".join(p for p in s.split("_") if p)


class State:
    """Decoded VIC-II view of a snapshot (64K RAM + $D000-$DFFF I/O)."""

    def __init__(self, ram, io, mask=()):
        self.ram, self.io = ram, io
        r = lambda a: io[a - 0xD000]
        self.d011, self.d016, self.d018 = r(0xD011), r(0xD016), r(0xD018)
        self.bank = (3 - (r(0xDD00) & 3)) * 0x4000
        self.screen_addr = self.bank + (self.d018 >> 4) * 0x400
        self.bitmap_on = bool(self.d011 & 0x20)
        self.bitmap_addr = self.bank + ((self.d018 >> 3) & 1) * 0x2000
        self.char_addr = self.bank + ((self.d018 >> 1) & 7) * 0x800
        self.rom_chars = (self.bank in (0x0000, 0x8000)) and (self.char_addr & 0x3000) == 0x1000
        screen = bytearray(ram[self.screen_addr:self.screen_addr + 1000])
        color = bytearray(b & 0x0F for b in io[0x800:0x800 + 1000])
        # undo the KERNAL cursor blink: BLNSW $CC=0 (blinking), BLNON $CF=1 (inverted phase),
        # GDBLN $CE = char under cursor, GDCOL $0287 = its colour, PNT $D1/$D2 + PNTR $D3 = position
        pnt = ram[0xD1] | ram[0xD2] << 8
        if ram[0xCC] == 0 and ram[0xCF] and pnt >= self.screen_addr:
            pos = pnt - self.screen_addr + ram[0xD3]
            if 0 <= pos < 1000: screen[pos] = ram[0xCE]; color[pos] = ram[0x0287] & 0x0F
        for row, c0, c1 in mask:
            for c in range(c0, c1 + 1): screen[row * 40 + c] = 0x20; color[row * 40 + c] = 0
        self.screen, self.color = bytes(screen), bytes(color)
        self.bitmap = ram[self.bitmap_addr:self.bitmap_addr + 8000] if self.bitmap_on else b""
        self.charset = b"" if (self.rom_chars or self.bitmap_on) else ram[self.char_addr:self.char_addr + 0x800]
        en = r(0xD015)
        self.vic = bytes([self.d011 & 0x7F, en, self.d016, r(0xD017), self.d018, r(0xD01B), r(0xD01C)]) + \
            bytes(b & 0x0F for b in io[0x20:0x2F])
        self.sprites = b""
        if en:
            ptrs = ram[self.screen_addr + 0x3F8:self.screen_addr + 0x400]
            self.sprites = io[0x00:0x11] + ptrs + b"".join(
                ram[self.bank + p * 64:self.bank + p * 64 + 63] for i, p in enumerate(ptrs) if en >> i & 1)

    def parts(self):
        return {k: getattr(self, k) for k in PARTS}

    def digest(self, ignore=()):
        h = hashlib.sha1()
        for k, v in self.parts().items():
            if k == "screen" and "rvs" in ignore: v = bytes(b & 0x7F for b in v)
            if k not in ignore: h.update(k.encode() + v)
        return h.hexdigest()

    def lines(self):
        lower = (self.d018 & 0x02) != 0 and self.rom_chars
        return ["".join(scr_char(c, lower) for c in self.screen[r * 40:r * 40 + 40]).rstrip() for r in range(25)]

    def text(self):
        mode = ("bitmap" if self.bitmap_on else "text") + (" multicolour" if self.d016 & 0x10 else "") + \
               (" ECM" if self.d011 & 0x40 else "")
        lower = (self.d018 & 0x02) != 0
        hdr = (f"; screen ${self.screen_addr:04X}  {mode}  "
               + (f"bitmap ${self.bitmap_addr:04X}  " if self.bitmap_on else "")
               + (("charset ROM " + ("lower" if lower else "upper")) if self.rom_chars else f"charset RAM ${self.char_addr:04X}")
               + f"  border {self.vic[7]} bg {self.vic[8]}  sprites ${self.vic[1]:02X}")
        return hdr + "\n" + "\n".join(f"{i:2}|{l}" for i, l in enumerate(self.lines())) + "\n"


def scr_char(c, lower):
    c &= 0x7F
    if c == 0: return "@"
    if 1 <= c <= 26: return chr(96 + c) if lower else chr(64 + c)
    if 32 <= c <= 63: return chr(c)
    if lower and 65 <= c <= 90: return chr(c)
    if c in (27, 29): return "[" if c == 27 else "]"
    return "."


def grab(v, mask=()):
    return State(v.mem(0x0000, 0xFFFF, "ram"), v.mem(0xD000, 0xDFFF, "io"), mask)


def busy(v):
    """True if the last IRQ interrupted the KERNAL serial-bus code ($ED00-$EEFF): a disk transfer is running."""
    return 0xED00 <= v.irq_return_pc() <= 0xEEFF


def direct_mode(v, st):
    """The program has ended: BASIC's main loop (the IMAIN vector target, watched since RUN) has run,
    and the keyboard buffer is empty."""
    return bool(v.watch) and any(v.watch.values()) and st.ram[0xC6] == 0


def wait_stable(v, frames, maxf, ignore=(), mask=(), step=10, until_end=False, change=False):
    """Run until the display digest is unchanged for `frames` frames with no disk transfer (and, with until_end,
    BASIC back in direct mode; with change, only after the digest first differs from the start).
    Returns (ok, frames_used, state)."""
    start = grab(v, mask).digest(ignore) if change else None
    changed = not change
    last, same, used = None, 0, 0
    st = None
    while used < maxf:
        v.frames(step); used += step
        st = grab(v, mask); d = st.digest(ignore)
        if d != start: changed = True
        if not changed or busy(v) or (until_end and not direct_mode(v, st)): d = None
        if d is not None and d == last:
            same += step
            if same >= frames: return True, used, st
        else:
            last, same = d, 0
    return False, used, st


def raw_names(d64):
    d = open(d64, "rb").read(); out = {}
    t, s = 18, 1
    while t:
        sec = d[tsblist.off(t, s):tsblist.off(t, s) + 256]
        for i in range(8):
            e = sec[i * 32:i * 32 + 32]
            if e[2]:
                rawn = e[5:21].split(b"\xa0")[0]
                out[rawn.decode("latin1")] = rawn
        t, s = sec[0], sec[1]
    return out


def load_and_run(v, raw_name, first=True):
    """(Wait for READY. at boot,) LOAD the program and RUN it; returns once BASIC's RUN handler ($A871) runs."""
    if first: wait_stable(v, 60, 1200)
    v.watch = None
    v.type(b'LOAD"' + raw_name + b'",8\rRUN\r')
    if not v.run_until(0xA871, 6000): raise RuntimeError("program did not start (RUN not reached)")
    imain = int.from_bytes(v.mem(0x0302, 0x0303, "cpu"), "little")
    v.watch = {imain: 0}


def run_scenario(sc, crt, d64, outdir=None):
    """Run one scenario. Returns {"checkpoints": [(label, State, png, expect)], "log": [...], ...}."""
    log, cps, err = [], [], None
    extra = ["-reu", "-reusize", str(sc["reu"])] if sc.get("reu") else []
    names = raw_names(d64)
    ignore, mask = sc.get("ignore", []), [tuple(m) for m in sc.get("mask", [])]
    sid = None; frames = 0
    with vicemon.Vice(crt=crt, d64=d64, extra=extra, timeout=sc.get("timeout", 900),
                      log=os.path.join(tempfile.gettempdir(), f"vice_{sc.get('id', slug(sc['name']))}.log")) as v:
        load_and_run(v, names[sc["name"]])
        for s in sc["steps"]:
            if "stable" in s or "end" in s:
                f = s.get("stable", 60)
                ok, used, _ = wait_stable(v, f, s.get("max", 3000), ignore, mask, until_end="end" in s,
                                          change=s.get("change", "stable" in s))
                frames += used
                log.append(f"{'end' if 'end' in s else 'stable %d' % f}: {'ok' if ok else 'NOT REACHED'} after {used} frames")
                if not ok and not err: err = f"step {len(log)}: {log[-1]}"
            elif "hold" in s:
                v.held_key = KEYS[s["hold"]] if isinstance(s["hold"], str) else s["hold"]
                v.frames(s.get("frames", 10)); v.held_key = None; frames += s.get("frames", 10)
                log.append(f"hold {s['hold']} {s.get('frames', 10)} frames")
            elif "frames" in s:
                v.frames(s["frames"]); frames += s["frames"]; log.append(f"frames {s['frames']}")
            elif "type" in s:
                v.type(s["type"]); log.append(f"type {s['type']!r}")
            elif "run" in s:
                load_and_run(v, names[s["run"]], first=False); log.append(f"run {s['run']}")
            elif "sid" in s:
                trace = bytearray(); prev = None
                for _ in range(s["sid"]):
                    v.frames(1); regs = v.mem(0xD400, 0xD418, "io")
                    if regs != prev: trace += regs; prev = regs
                sid = bytes(trace); frames += s["sid"]
                log.append(f"sid {s['sid']} frames: {len(trace) // 25} distinct states")
            if "cap" in s:
                cps.append((s["cap"], grab(v, mask), v.display_png(), s.get("expect", [])))
                log.append(f"  -> checkpoint {len(cps):02d}_{s['cap']}")
        last = sc["steps"][-1] if sc["steps"] else {}
        cps.append(("final", grab(v, mask), v.display_png(),
                    sc.get("expect", []) + ([] if "cap" in last else last.get("expect", []))))
    res = {"checkpoints": cps, "log": log, "frames": frames, "error": err, "sid": sid}
    if outdir: write_golden(outdir, sc, res)
    return res


def cp_dir(i, label): return f"{i + 1:02d}_{label}"


def write_golden(d, sc, res):
    os.makedirs(d, exist_ok=True)
    for root, dirs, files in os.walk(d, topdown=False):
        for f in files:
            os.remove(os.path.join(root, f))
        for x in dirs: os.rmdir(os.path.join(root, x))
    for i, (label, st, png, _) in enumerate(res["checkpoints"]):
        c = os.path.join(d, cp_dir(i, label)); os.makedirs(c)
        open(os.path.join(c, "screen.txt"), "w").write(st.text())
        for k, val in st.parts().items():
            if val: open(os.path.join(c, k + ".bin"), "wb").write(val)
        open(os.path.join(c, "shot.png"), "wb").write(png)
    if res["sid"]: open(os.path.join(d, "sid.bin"), "wb").write(res["sid"])
    open(os.path.join(d, "run.log"), "w").write("\n".join(res["log"]) + f"\ntotal {res['frames']} frames\n")


def text_problems(sc, res):
    bad = []
    rej = sc.get("reject", DEFAULT_REJECT)
    for i, (label, st, _, expect) in enumerate(res["checkpoints"]):
        txt = "\n".join(st.lines()).lower()
        bad += [f"{cp_dir(i, label)}: unexpected /{r}/" for r in rej if re.search(r, txt)]
        bad += [f"{cp_dir(i, label)}: missing /{r}/" for r in expect if not re.search(r, txt, re.I)]
    return bad


def compare(sc, res, gdir):
    bad = [res["error"]] if res["error"] else []
    bad += text_problems(sc, res)
    want = sorted(x for x in os.listdir(gdir) if os.path.isdir(os.path.join(gdir, x))) if os.path.isdir(gdir) else []
    got = [cp_dir(i, c[0]) for i, c in enumerate(res["checkpoints"])]
    if want != got: return bad + [f"checkpoints {got} != golden {want}"]
    parts = [p for p in sc.get("compare", PARTS) if p not in sc.get("ignore", [])]
    for i, (label, st, _, _) in enumerate(res["checkpoints"]):
        for k in parts:
            f = os.path.join(gdir, got[i], k + ".bin")
            want, got_ = (open(f, "rb").read() if os.path.exists(f) else b""), getattr(st, k)
            if k == "screen" and "rvs" in sc.get("ignore", []):
                want, got_ = bytes(b & 0x7F for b in want), bytes(b & 0x7F for b in got_)
            if want != got_:
                bad.append(f"{got[i]}/{k} differs")
    f = os.path.join(gdir, "sid.bin")
    if "sid" in sc.get("compare", PARTS + ["sid"]) and os.path.exists(f) and open(f, "rb").read() != (res["sid"] or b""):
        bad.append("sid trace differs")
    return bad


def main(a):
    opts = {"--crt": os.path.join(ROOT, "build/TSBneo.crt"), "--d64": os.path.join(ROOT, "corpus/tsbneo_260228.d64"),
            "--scenarios": os.path.join(ROOT, "tests/demos.json"), "--golden": os.path.join(ROOT, "tests/golden"), "-j": "4"}
    args = []
    while a:
        x = a.pop(0)
        if x in opts: opts[x] = a.pop(0)
        else: args.append(x)
    if not args: print(__doc__); return 2
    mode, names = args[0], args[1:]
    crt, d64 = opts["--crt"], opts["--d64"]
    if mode == "explore":
        maxf = int(names[1]) if len(names) > 1 else 3000
        with vicemon.Vice(crt=crt, d64=d64) as v:
            load_and_run(v, raw_names(d64)[names[0]])
            ok, used, st = wait_stable(v, 120, maxf)
            print(f"--- after {used} frames, stable={ok}"); print(st.text())
        return 0
    scen = json.load(open(opts["--scenarios"]))["programs"]
    for s in scen: s.setdefault("id", slug(s["name"]))
    todo = [s for s in scen if s.get("steps") is not None and (not names or s["id"] in names or s["name"] in names)]

    def one(sc):
        g = os.path.join(opts["--golden"], sc["id"])
        try:
            if mode == "capture":
                r = run_scenario(sc, crt, d64, g)
                probs = ([r["error"]] if r["error"] else []) + text_problems(sc, r)
                return sc, ("WARN " + "; ".join(probs)) if probs else "captured", r
            r = run_scenario(sc, crt, d64)
            bad = compare(sc, r, g)
            return sc, ("FAIL " + "; ".join(bad)) if bad else "PASS", r
        except Exception as e:
            return sc, f"ERROR {type(e).__name__}: {e}", {}

    fails = 0
    with cf.ThreadPoolExecutor(int(opts["-j"])) as ex:
        for sc, status, r in ex.map(one, todo):
            word = status.split()[0]
            print(f"{word:8} {sc['id']:24} {status[len(word):].strip()}  [{r.get('frames', '?')} frames, "
                  f"{len(r.get('checkpoints', []))} checkpoints]", flush=True)
            fails += word not in ("PASS", "captured")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
