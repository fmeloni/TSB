#!/usr/bin/env python3
"""Run programs from a D64 under a cartridge, reach checkpoints, capture or compare golden results.

    tools/demo_capture.py capture [ids...]   write tests/golden/<id>/<NN_label>/ for each scenario (default: all)
    tools/demo_capture.py check   [ids...]   compare against tests/golden/, print PASS/FAIL, exit 1 on any FAIL
    tools/demo_capture.py explore <name> [maxframes]   LOAD+RUN a program, print the first stable screen

Options: --crt FILE (default build/TSBneo.crt), --d64 FILE (default corpus/tsbneo_260228.d64),
         --scenarios FILE (default tests/demos.json), --golden DIR (default tests/golden), -j N (parallel VICEs)
         --video pal|ntsc, --kernal stock|jiffy, --dos stock|jiffy: the machine (default pal/stock/stock, the
         configuration of all goldens; same as the env variables C64_VIDEO/C64_KERNAL/C64_DOS, see vicemon.py)

Scenario (tests/demos.json, list "programs"):
    name      directory name of the program to LOAD+RUN       id      golden folder (default: slug of name)
    reu       REU size in KB (VICE -reusize)                   ignore  parts left out of stability and compare
                                                               ("rvs": the screen's reverse bit, for FLASH)
    compare   parts compared (default all: screen color bitmap charset vic sprites [sid])
    mask      [[row, col_from, col_to], ...] screen/colour cells blanked (timing-dependent text)
    reject    regexes that must not appear in any checkpoint's screen text (default: a BASIC error message)
    bas       (instead of name) a text program, tokenized like TSB does and RUN directly (command suite)
    disk      "scratch": attach a fresh writable D64 instead of the corpus disk
    printer   true: emulate printer 4 (raw) and compare everything it received (printer.bin);
              "no-dots": graphic dot bytes (>= $80) are only checked to be graphic bytes
    steps     list, run in order after RUN:
      {"stable": F, "max": M, "change": true}  run until the display has changed (unless change=false) and then
                                stays unchanged for F frames with no disk transfer; fails if not within M frames;
                                "until": regex also requires screen.txt (header line included) to match
      {"end": 1, "max": M}      same with F=60, and BASIC back in direct mode (program finished)
      {"frames": N}             run N frames (KERNAL IRQs, 1/60 s each)
      {"type": "text"}          feed the keyboard buffer ("\\r" = RETURN, lower case = unshifted)
      {"hold": "space", "frames": N}  hold a key in the matrix for N frames (for PEEK(197) polling)
      {"run": "NAME"}           LOAD+RUN another program in the same session (keeps REU contents)
      {"sid": N}                record SID registers every frame for N frames (states lasting >= 2 frames, repeats
                                collapsed -> sid.bin)
    Any step may carry "cap": "label" to capture a checkpoint after it, and "expect": [regex,...] checked
    against that checkpoint's screen text. The state after the last step is always captured as "final".

A checkpoint stores: screen.txt (decoded, for people), screen.bin (1000 bytes of the visible matrix),
color.bin (colour RAM nybbles), bitmap.bin (8000 bytes, bitmap mode only), charset.bin (2K, RAM charsets
only), vic.bin (mode/colour registers), sprites.bin (positions, pointers, data, if any are on), shot.png.
"""
import hashlib, json, os, re, shutil, struct, sys, tempfile, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vicemon, tsblist
JIFFY_KERNAL = False   # set in main() from the machine (C64_KERNAL / --kernal)

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PARTS = ["screen", "color", "bitmap", "charset", "vic", "sprites"]
DEFAULT_REJECT = [r"\?[a-z0-9 ]+error"]

# Machine identity text that differs between configurations but is not program behaviour. All goldens are
# captured on PAL with the stock KERNAL and 1541 ROM; on other machines these screen-code strings are mapped
# back to the stock text before comparing. The JiffyDOS KERNAL banner stays on screen when a program
# does not clear it, and the JiffyDOS 1541 ROM answers "73,JIFFYDOS 5.0 1541" after a reset.
def _sc(t):
    return bytes(ord(c) - 96 if "a" <= c <= "z" else ord(c) for c in t)
MACHINE_TEXT = {
    "kernal": [(_sc("       jiffydos v6.01 (c)1989 cmd".ljust(40)), _sc("    **** commodore 64 basic v2 ****".ljust(40)), 40),
               (_sc(" c-64 basic v2   "), _sc(" 64k ram system  "), 0)],
    "dos": [(_sc("jiffydos 5.0 1541"), _sc("cbm dos v2.6 1541"), 0)],
}


def machine_screen(screen):
    """Screen bytes with the current machine's identity text replaced by the stock text (see MACHINE_TEXT).
    The match ignores the reverse bit; an entry with align 40 only matches a whole screen row."""
    video, kernal, dos = vicemon.machine()
    subs = (MACHINE_TEXT["kernal"] if kernal == "jiffy" else []) + (MACHINE_TEXT["dos"] if dos == "jiffy" else [])
    if not subs: return screen
    out, plain = bytearray(screen), bytes(b & 0x7F for b in screen)
    for old, new, align in subs:
        i = plain.find(old)
        while i >= 0:
            if not align or i % align == 0:
                out[i:i + len(new)] = bytes((o & 0x80) | n for o, n in zip(out[i:i + len(new)], new))
            i = plain.find(old, i + 1)
    return bytes(out)


def known_issue(sc):
    """The reason text if this scenario has a known, accepted difference on the current machine
    (scenario field "known": [{"kernal": "jiffy", "why": "..."}, ...]; keys video/kernal/dos)."""
    m = dict(zip(("video", "kernal", "dos"), vicemon.machine()))
    for k in sc.get("known", []):
        if all(m[x] == k[x] for x in ("video", "kernal", "dos") if x in k): return k["why"]
    return None
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

        self.vars = b""; self.sidregs = b""

    def extras(self, sidregs=None):
        """Add the parts used by the command suite: decoded BASIC variables and the last SID register writes."""
        self.vars = basic_vars(self.ram).encode()
        if sidregs is not None: self.sidregs = sidregs
        return self

    def parts(self):
        d = {k: getattr(self, k) for k in PARTS}
        if self.vars or self.sidregs: d.update(vars=self.vars, sidregs=self.sidregs)
        return d

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


def mflpt(b):
    """5-byte Commodore float -> Python float."""
    if b[0] == 0: return 0.0
    m = ((b[1] | 0x80) << 24 | b[2] << 16 | b[3] << 8 | b[4]) / 2.0 ** 32
    return (-1 if b[1] & 0x80 else 1) * m * 2.0 ** (b[0] - 128)


def _fmt_float(b):
    return f"{mflpt(b):.10g} [{b.hex()}]"


def basic_vars(ram):
    """Decode BASIC's simple variables ($2D..$2F) and arrays ($2F..$31) into stable text: values, not
    addresses, so a different memory layout (Ultra) gives the same text."""
    w = lambda a: ram[a] | ram[a + 1] << 8
    vt, at, se = w(0x2D), w(0x2F), w(0x31); out = []

    def name(b0, b1):
        n = chr(b0 & 0x7F) + (chr(b1 & 0x7F) if b1 & 0x7F else "")
        k = (b0 >> 7, b1 >> 7)
        return ("FN " if k == (1, 0) else "") + n + {(0, 0): "", (1, 1): "%", (0, 1): "$", (1, 0): ""}[k], k

    def val(kind, b):
        if kind == (1, 1): return str(struct.unpack(">h", bytes(b[:2]))[0])
        if kind == (0, 1):
            n, p = b[0], b[1] | b[2] << 8
            return '"' + "".join(chr(c) if 0x20 <= c < 0x7F and c != 0x22 else "{$%02X}" % c for c in ram[p:p + n]) + '"'
        return _fmt_float(b)

    a = vt
    while a + 7 <= at and a < 0xD000:
        nm, kind = name(ram[a], ram[a + 1]); b = ram[a + 2:a + 7]
        out.append(f"{nm} = " + ("(fn)" if kind == (1, 0) else val(kind, b))); a += 7
    a = at
    while a + 5 <= se and a < 0xD000:
        nm, kind = name(ram[a], ram[a + 1]); size = w(a + 2); nd = ram[a + 4]
        dims = [ram[a + 5 + 2 * i] << 8 | ram[a + 6 + 2 * i] for i in range(nd)][::-1]
        es = {(1, 1): 2, (0, 1): 3}.get(kind, 5); e = a + 5 + 2 * nd
        n = 1
        for d in dims: n *= d
        vals = [val(kind, ram[e + i * es:e + i * es + es]) for i in range(min(n, 400))]
        out.append(f"{nm}({','.join(str(d - 1) for d in dims)}) = " + ", ".join(vals))
        if size == 0: break
        a += size
    return "\n".join(out) + "\n"


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
    """True if the last IRQ interrupted the KERNAL serial-bus code ($ED00-$EEFF): a disk transfer is running.
    With the JiffyDOS KERNAL also its own serial code, which replaces the tape routines at $F72C-$FCCF.
    (JiffyDOS LOAD itself runs with IRQs off, so no IRQ lands inside it.)"""
    pc = v.irq_return_pc()
    return 0xED00 <= pc <= 0xEEFF or (JIFFY_KERNAL and 0xF72C <= pc <= 0xFCCF)


def direct_mode(v, st):
    """The program has ended: BASIC's main loop (the IMAIN vector target, watched since RUN) has run,
    and the keyboard buffer is empty."""
    return bool(v.watch) and any(v.watch.values()) and st.ram[0xC6] == 0


def wait_stable(v, frames, maxf, ignore=(), mask=(), step=10, until_end=False, change=False, until=None):
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
        if not changed or busy(v) or (until_end and not direct_mode(v, st)) or \
                (until and not re.search(until, st.text(), re.I)): d = None
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


def inject_and_run(v, path):
    """Wait for READY., tokenize a text program (tools/tsblist.crunch = TSB's tokenizer), poke it to $0801,
    set the end-of-program pointer and RUN it."""
    wait_stable(v, 60, 1200)
    lines = [l.rstrip("\n") for l in open(path, encoding="utf-8") if l.strip() and not l.lstrip().startswith(";")]
    prg = tsblist.make_prg(lines)
    v.poke(0x0801, prg[2:], "ram")
    end = 0x0801 + len(prg) - 2
    for z in (0x2D, 0x2F, 0x31): v.poke(z, [end & 255, end >> 8], "ram")
    v.watch = None
    v.type("run\r")
    if not v.run_until(0xA871, 6000): raise RuntimeError("program did not start (RUN not reached)")
    imain = int.from_bytes(v.mem(0x0302, 0x0303, "cpu"), "little")
    v.watch = {imain: 0}


def run_scenario(sc, crt, d64, outdir=None):
    """Run one scenario. Returns {"checkpoints": [(label, State, png, expect)], "log": [...], ...}."""
    log, cps, err = [], [], None
    extra = ["-reu", "-reusize", str(sc["reu"])] if sc.get("reu") else []
    ignore, mask = sc.get("ignore", []), [tuple(m) for m in sc.get("mask", [])]
    sid = None; frames = 0; tmp = None; rw = False
    if sc.get("disk") == "scratch":   # a fresh writable disk per run (SAVE, OPEN, SCRSV, DISK ...)
        tmp = tempfile.mkdtemp(prefix="tsbcmd_"); d64 = vicemon.blank_d64(os.path.join(tmp, "scratch.d64")); rw = True
    prn = None
    if sc.get("printer"):  # device 4, raw driver: every byte sent to the printer lands in a file
        tmp = tmp or tempfile.mkdtemp(prefix="tsbcmd_"); prn = os.path.join(tmp, "printer.bin")
        extra = extra + ["-devicebackend4", "1", "-busdevice4", "-pr4drv", "raw", "-pr4output", "text", "-pr4txtdev", "0", "-prtxtdev1", prn]
    names = raw_names(d64) if "name" in sc else {}
    bas = sc.get("bas")
    vx = lambda st: st.extras(v.mem(0xD400, 0xD418, "io")) if bas else st
    with vicemon.Vice(crt=crt, d64=d64, extra=extra, timeout=sc.get("timeout", 900), d64rw=rw,
                      log=os.path.join(tempfile.gettempdir(), f"vice_{sc.get('id', slug(sc.get('name', '')))}.log")) as v:
        if bas: inject_and_run(v, os.path.join(ROOT, bas))
        else: load_and_run(v, names[sc["name"]])
        for s in sc["steps"]:
            if "stable" in s or "end" in s:
                f = s.get("stable", 60)
                ok, used, _ = wait_stable(v, f, s.get("max", 3000), ignore, mask, until_end="end" in s,
                                          change=s.get("change", "stable" in s), until=s.get("until"))
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
                # one sample per frame; keep states that last >= 2 frames (a state seen for a single frame is
                # BASIC caught half-way through setting several registers, which depends on timing), collapse repeats
                samples = []
                for _ in range(s["sid"]):
                    v.frames(1); samples.append(v.mem(0xD400, 0xD418, "io"))
                trace = bytearray(); prev = None
                for i, regs in enumerate(samples):
                    if regs != prev and (i + 1 < len(samples) and samples[i + 1] == regs):
                        trace += regs; prev = regs
                sid = bytes(trace); frames += s["sid"]
                log.append(f"sid {s['sid']} frames: {len(trace) // 25} distinct states")
            if "cap" in s:
                cps.append((s["cap"], vx(grab(v, mask)), v.display_png(), s.get("expect", [])))
                log.append(f"  -> checkpoint {len(cps):02d}_{s['cap']}")
        last = sc["steps"][-1] if sc["steps"] else {}
        cps.append(("final", vx(grab(v, mask)), v.display_png(),
                    sc.get("expect", []) + ([] if "cap" in last else last.get("expect", []))))
    printed = open(prn, "rb").read() if prn and os.path.exists(prn) else (b"" if prn else None)
    if tmp: shutil.rmtree(tmp, ignore_errors=True)
    res = {"checkpoints": cps, "log": log, "frames": frames, "error": err, "sid": sid, "printer": printed}
    if outdir: write_golden(outdir, sc, res)
    return res


def cp_dir(i, label): return f"{i + 1:02d}_{label}"


_CHARGEN = None


def chargen():
    """The C64 character ROM from the VICE data folder (never stored in this repo)."""
    global _CHARGEN
    if _CHARGEN is None:
        import glob
        d = vicemon.find_vice()[1]
        f = sorted(glob.glob(os.path.join(d, "C64", "chargen*")))
        _CHARGEN = open(f[0], "rb").read() if f else b""
    return _CHARGEN


def rom_charset_text(cs):
    """If a RAM charset is (nearly) a copy of one 2K half of the character ROM, return the text that is stored
    instead of the bytes (CLAUDE.md: no Commodore ROM images in git): ROM half, SHA-1 of the 2048 bytes and the
    differing bytes. Otherwise None."""
    rom = chargen()
    best = max(((sum(a == b for a, b in zip(cs, rom[h:h + 2048])), h) for h in range(0, len(rom), 2048)), default=(0, 0))
    if not rom or best[0] < 1536: return None
    h = best[1]; diff = [(i, rom[h + i], c) for i, c in enumerate(cs) if rom[h + i] != c]
    return (f"charset = character ROM ${h:04X}-${h + 2047:04X} with {len(diff)} byte(s) changed\n"
            f"sha1 {hashlib.sha1(cs).hexdigest()}\n" + "".join(f"{i:04X} = {c:02X}\n" for i, a, c in diff))


def write_golden(d, sc, res):
    os.makedirs(d, exist_ok=True)
    for root, dirs, files in os.walk(d, topdown=False):
        for f in files:
            os.remove(os.path.join(root, f))
        for x in dirs: os.rmdir(os.path.join(root, x))
    for i, (label, st, png, _) in enumerate(res["checkpoints"]):
        c = os.path.join(d, cp_dir(i, label)); os.makedirs(c)
        open(os.path.join(c, "screen.txt"), "w").write(st.text())
        if st.vars: open(os.path.join(c, "vars.txt"), "wb").write(st.vars)
        for k, val in st.parts().items():
            if not val or k == "vars": continue
            t = rom_charset_text(val) if k == "charset" else None
            if t: open(os.path.join(c, "charset.rom.txt"), "w").write(t)
            else: open(os.path.join(c, k + ".bin"), "wb").write(val)
        open(os.path.join(c, "shot.png"), "wb").write(png)
    if res["sid"]: open(os.path.join(d, "sid.bin"), "wb").write(res["sid"])
    if res.get("printer") is not None: open(os.path.join(d, "printer.bin"), "wb").write(res["printer"])
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
    deflt = PARTS + (["vars", "sidregs"] if sc.get("bas") else [])
    parts = [p for p in sc.get("compare", deflt) if p not in sc.get("ignore", [])]
    for i, (label, st, _, _) in enumerate(res["checkpoints"]):
        for k in parts:
            f = os.path.join(gdir, got[i], "vars.txt" if k == "vars" else k + ".bin")
            want, got_ = (open(f, "rb").read() if os.path.exists(f) else b""), getattr(st, k)
            r = os.path.join(gdir, got[i], "charset.rom.txt")
            if k == "charset" and os.path.exists(r):   # ROM-derived charset: compare by hash
                want = open(r).read().split("\n")[1].split()[1]; got_ = hashlib.sha1(got_).hexdigest()
            if k == "screen": got_ = machine_screen(got_)
            if k == "screen" and "rvs" in sc.get("ignore", []):
                want, got_ = bytes(b & 0x7F for b in want), bytes(b & 0x7F for b in got_)
            if want != got_:
                bad.append(f"{got[i]}/{k} differs")
    f = os.path.join(gdir, "printer.bin")
    if res.get("printer") is not None:
        want = open(f, "rb").read() if os.path.exists(f) else None
        got_ = res["printer"]
        if sc.get("printer") == "no-dots" and want is not None:   # graphic dot bytes (>= $80) vary run to run
            want, got_ = bytes(min(b, 0x80) for b in want), bytes(min(b, 0x80) for b in got_)
        if want != got_: bad.append("printer output differs")
    f = os.path.join(gdir, "sid.bin")
    if "sid" in sc.get("compare", PARTS + ["sid"]) and os.path.exists(f) and open(f, "rb").read() != (res["sid"] or b""):
        bad.append("sid trace differs")
    return bad


def main(a):
    opts = {"--crt": os.path.join(ROOT, "build/TSBneo.crt"), "--d64": os.path.join(ROOT, "corpus/tsbneo_260228.d64"),
            "--scenarios": os.path.join(ROOT, "tests/demos.json"), "--golden": os.path.join(ROOT, "tests/golden"), "-j": "4"}
    args, explicit = [], set()
    while a:
        x = a.pop(0)
        if x in opts: opts[x] = a.pop(0); explicit.add(x)
        elif x in ("--video", "--kernal", "--dos"): os.environ["C64_" + x[2:].upper()] = a.pop(0)
        else: args.append(x)
    global JIFFY_KERNAL
    JIFFY_KERNAL = vicemon.machine()[1] == "jiffy"
    if not args: print(__doc__); return 2
    mode, names = args[0], args[1:]
    if mode == "capture" and vicemon.machine_name() != "pal-stock-stock" and "--golden" not in explicit:
        print("capture on a non-default machine needs an explicit --golden DIR (goldens are pal-stock-stock)"); return 2
    crt, d64 = opts["--crt"], opts["--d64"]
    if mode == "explore":
        maxf = int(names[1]) if len(names) > 1 else 3000
        with vicemon.Vice(crt=crt, d64=d64) as v:
            load_and_run(v, raw_names(d64)[names[0]])
            ok, used, st = wait_stable(v, 120, maxf)
            print(f"--- after {used} frames, stable={ok}"); print(st.text())
        return 0
    scen = json.load(open(opts["--scenarios"]))["programs"]
    for s in scen: s.setdefault("id", slug(s.get("name") or os.path.splitext(os.path.basename(s["bas"]))[0]))
    todo = [s for s in scen if s.get("steps") is not None and (not names or s["id"] in names or s.get("name") in names)]

    def one(sc):
        g = os.path.join(opts["--golden"], sc["id"])
        try:
            if mode == "capture":
                r = run_scenario(sc, crt, d64, g)
                probs = ([r["error"]] if r["error"] else []) + text_problems(sc, r)
                return sc, ("WARN " + "; ".join(probs)) if probs else "captured", r
            r = run_scenario(sc, crt, d64)
            bad = compare(sc, r, g)
        except Exception as e:
            r, bad = {}, [f"ERROR {type(e).__name__}: {e}"]
        if bad and known_issue(sc): return sc, f"KNOWN {known_issue(sc)} ({'; '.join(bad)})", r
        if bad and bad[0].startswith("ERROR "): return sc, bad[0], r
        return sc, ("FAIL " + "; ".join(bad)) if bad else "PASS", r

    fails = 0
    print(f"machine: {vicemon.machine_name()}", flush=True)
    with cf.ThreadPoolExecutor(int(opts["-j"])) as ex:
        for sc, status, r in ex.map(one, todo):
            word = status.split()[0]
            print(f"{word:8} {sc['id']:24} {status[len(word):].strip()}  [{r.get('frames', '?')} frames, "
                  f"{len(r.get('checkpoints', []))} checkpoints]", flush=True)
            fails += word not in ("PASS", "captured", "KNOWN")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
