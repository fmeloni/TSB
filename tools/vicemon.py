#!/usr/bin/env python3
"""Drive VICE x64sc through its binary monitor (works with the macOS SDL build and headless Linux builds).

Library use:
    with Vice(crt="build/TSBneo.crt", d64="corpus/tsbneo_260228.d64") as v:
        v.frames(400)            # run ~400 KERNAL IRQs (~400/60 s of C64 time)
        v.type('load"center.dmo",8\\rrun\\r')
        v.frames(900)
        snap = v.snapshot()      # dict: ram (64K), io ($D000-$DFFF), png (bytes)

CLI (what tools/run_crt.sh uses):
    vicemon.py run <crt|-> <dump.bin> <irqs> [--d64 X] [--type TEXT] [--png X]
                   [--video pal|ntsc|oldntsc] [--kernal stock|jiffy] [--dos stock|jiffy] [-- extra x64sc args]
    Writes a 2-byte-load-address + $0000-$07FF dump (same format as the old monitor 'save').

Env: X64SC, VICE_DATA (see run_crt.sh).
Machine (defaults = the configuration all goldens were captured on: PAL, stock KERNAL, stock 1541 ROM):
    C64_VIDEO  pal | ntsc        VICE -model c64 / -model ntsc (VIC-II, CIA and clock of that machine)
               | oldntsc         VICE -model oldntsc: early NTSC C64, VIC-II 6567R56A (64 cycles/line, 262 lines);
                                 optional, not in the default matrix
    C64_KERNAL stock | jiffy     jiffy: -kernal corpus/roms/JiffyDOS_C64/JiffyDOS_C64_6.01.bin
    C64_DOS    stock | jiffy     jiffy: -dos1541 corpus/roms/JiffyDOS_1541/JiffyDOS_1541-II_6.00.bin
                                 (drive type stays 1541 with true-drive emulation; the 16K image replaces
                                 the 1541 DOS ROM, as on a Pi1541 or a short-board 1541)
    JIFFY_KERNAL, JIFFY_DOS      other paths for the two JiffyDOS images (commercial; never committed)
    The CLI flags --video/--kernal/--dos of vicemon.py and demo_capture.py set these variables.
"""
import os, socket, struct, subprocess, sys, time, zlib, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JIFFY = {"kernal": os.path.join(ROOT, "corpus/roms/JiffyDOS_C64/JiffyDOS_C64_6.01.bin"),
         "dos": os.path.join(ROOT, "corpus/roms/JiffyDOS_1541/JiffyDOS_1541-II_6.00.bin")}
MACVICE = os.path.expanduser("~/Applications/VICE-3.10-SDL2-BluetoothFix")


def find_vice():
    x = os.environ.get("X64SC") or shutil.which("x64sc") or os.path.join(MACVICE, "bin/x64sc")
    d = os.environ.get("VICE_DATA")
    if not d:
        cand = os.path.join(os.path.dirname(x), "../share/vice")
        d = os.path.realpath(cand) if os.path.isdir(os.path.join(cand, "C64")) else os.path.expanduser("~/vicedata")
    return x, d


def machine():
    """(video, kernal, dos) from C64_VIDEO / C64_KERNAL / C64_DOS, checked."""
    m = (os.environ.get("C64_VIDEO", "pal").lower(), os.environ.get("C64_KERNAL", "stock").lower(),
         os.environ.get("C64_DOS", "stock").lower())
    if m[0] not in ("pal", "ntsc", "oldntsc") or m[1] not in ("stock", "jiffy") or m[2] not in ("stock", "jiffy"):
        raise SystemExit(f"bad machine {m}: C64_VIDEO pal|ntsc|oldntsc, C64_KERNAL stock|jiffy, C64_DOS stock|jiffy")
    return m


def machine_name():
    return "-".join(machine())


def jiffy_rom(kind):
    p = os.environ.get("JIFFY_KERNAL" if kind == "kernal" else "JIFFY_DOS") or JIFFY[kind]
    if not os.path.isfile(p): raise FileNotFoundError(f"JiffyDOS {kind} ROM not found: {p}")
    return os.path.abspath(p)


def machine_args():
    """x64sc arguments for the selected machine. Placed after -default; -model first, so its
    defaults (KERNAL revision, VIC-II) do not override the ROM choices that follow."""
    video, kernal, dos = machine()
    args = ["-model", {"pal": "c64", "ntsc": "ntsc", "oldntsc": "oldntsc"}[video]]
    if kernal == "jiffy": args += ["-kernal", jiffy_rom("kernal")]
    if dos == "jiffy": args += ["-dos1541", jiffy_rom("dos")]
    return args


def blank_d64(path, name="scratch", ident="01"):
    """Create an empty formatted D64 with VICE's c1541 (next to x64sc)."""
    c1541 = os.path.join(os.path.dirname(find_vice()[0]), "c1541")
    subprocess.run([c1541, "-format", f"{name},{ident}", "d64", path], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return path


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def petscii(text):
    """ASCII -> PETSCII for the keyboard buffer: lower case types as unshifted (upper on screen)."""
    out = bytearray()
    for c in text:
        o = ord(c)
        if c == "\n" or c == "\r": out.append(13)
        elif "a" <= c <= "z": out.append(o - 32)
        elif "A" <= c <= "Z": out.append(o + 128)  # shifted letters ($C1-$DA)
        else: out.append(o & 0xFF)
    return bytes(out)


class Vice:
    STX, API = 0x02, 0x02

    def __init__(self, crt=None, d64=None, extra=(), warp=True, truedrive=True, timeout=240, log=None, d64rw=False):
        x, data = find_vice()
        self.port = free_port()
        args = [x, "-default", "-directory", data, "-silent", "-sounddev", "dummy",
                "-binarymonitor", "-binarymonitoraddress", f"ip4://127.0.0.1:{self.port}"]
        # Power-on RAM: VICE's plain pattern, no random bit flips (default RAMInitRandomChance 10 flips ~2% of the
        # bytes with a time-based seed, so runs started in the same second agree and others don't: step 2.0
        # finding 6, e.g. the sprite 7 pointer at $07FF that CLS leaves alone). -seed fixes any other randomness.
        args += ["-raminitrandomchance", "0", "-seed", "1"]
        args += machine_args()
        if warp: args.append("-warp")
        if crt and crt != "-": args += ["-cartcrt", crt]
        if d64:
            # read-only by default: never modify the corpus; d64rw only for scratch copies.
            # No -busdevice8: it enables VICE's virtual IEC device, which then answers instead of the
            # emulated 1541 (status 73 reads "VIRTUAL DRIVE EMULATION" instead of "CBM DOS V2.6 1541").
            args += ["-drive8type", "1541", "-attach8rw" if d64rw else "-attach8ro", "-8", d64]
            args.append("-drive8truedrive" if truedrive else "+drive8truedrive")
        args += list(extra)
        self.log = open(log or os.devnull, "w")
        env = dict(os.environ)
        env.setdefault("SDL_VIDEODRIVER", "dummy")  # no window from the SDL build; display_png still works
        self.proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT, env=env)
        self.deadline = time.time() + timeout
        self.reqid = 0
        self.sock = None
        for _ in range(200):
            try:
                self.sock = socket.create_connection(("127.0.0.1", self.port), timeout=30); break
            except OSError:
                if self.proc.poll() is not None: raise RuntimeError("x64sc exited at startup")
                time.sleep(0.05)
        if not self.sock: raise RuntimeError("cannot connect to VICE binary monitor")
        self.buf = b""
        self.banks = dict(self.cmd(0x82)[1])

    # --- protocol -------------------------------------------------------------
    def _recv(self, n):
        while len(self.buf) < n:
            if time.time() > self.deadline: raise TimeoutError("VICE run exceeded timeout")
            chunk = self.sock.recv(65536)
            if not chunk: raise RuntimeError("VICE closed the connection")
            self.buf += chunk
        r, self.buf = self.buf[:n], self.buf[n:]
        return r

    def _read_msg(self):
        h = self._recv(12)
        assert h[0] == self.STX, h
        ln, rtype, err, rid = struct.unpack("<IBBI", h[2:12])
        return rtype, err, rid, self._recv(ln)

    def send(self, ctype, body=b""):
        self.reqid += 1
        self.sock.sendall(struct.pack("<BBIIB", self.STX, self.API, len(body), self.reqid, ctype) + body)
        return self.reqid

    def cmd(self, ctype, body=b""):
        rid = self.send(ctype, body)
        while True:
            rtype, err, r, b = self._read_msg()
            if r == rid and rtype != 0x62 and rtype != 0x63:
                if err: raise RuntimeError(f"VICE monitor error {err:#x} for command {ctype:#x}")
                return self._parse(ctype, b)
            self._event(rtype, b)

    def _parse(self, ctype, b):
        if ctype == 0x82:  # banks
            n = struct.unpack("<H", b[:2])[0]; p = 2; out = []
            for _ in range(n):
                sz, bid, nl = struct.unpack("<BHB", b[p:p + 4]); out.append((b[p + 4:p + 4 + nl].decode(), bid)); p += sz + 1
            return (n, out)
        if ctype == 0x01:
            return b[2:]
        return b

    def _event(self, rtype, b):
        self.last_event = (rtype, b)
        if rtype == 0x61: raise RuntimeError("CPU JAM at $%04X" % struct.unpack("<H", b[:2]))

    def wait_stopped(self):
        while True:
            rtype, err, rid, b = self._read_msg()
            self._event(rtype, b)
            if rtype == 0x62: return struct.unpack("<H", b[:2])[0]

    # --- high level ---------------------------------------------------------------
    def mem(self, start, end, bank="ram"):
        body = struct.pack("<BHHBH", 0, start, end, 0, self.banks[bank])
        return self.cmd(0x01, body)

    def poke(self, addr, data, bank="ram"):
        body = struct.pack("<BHHBH", 0, addr, addr + len(data) - 1, 0, self.banks[bank]) + bytes(data)
        self.cmd(0x02, body)

    def resume(self):
        self.cmd(0xAA)

    def reset(self, hard=False):
        """Reset the machine (cartridges see the reset line too) and keep it running."""
        self.cmd(0xCC, bytes([1 if hard else 0]))

    def set_register(self, rid, value):
        """Set one CPU register (VICE ids as in registers(): 0 A, 1 X, 2 Y, 3 PC, 4 SP, 5 flags)."""
        self.cmd(0x32, struct.pack("<BHBBH", 0, 1, 3, rid, value))

    def checkpoint(self, addr, op=4):
        b = self.cmd(0x12, struct.pack("<HHBBBB", addr, addr, 1, 1, op, 0))
        return struct.unpack("<I", b[:4])[0]

    def delete_checkpoint(self, cid):
        self.cmd(0x13, struct.pack("<I", cid))

    held_key = None  # C64 keyboard-matrix code (0-63) held down, or None
    watch = None     # {addr: hit_count}: exec addresses noted (not counted as frames) while frames() runs

    def frames(self, n, addr=0xFF48):
        """Run until the CPU has entered the KERNAL IRQ handler n times. Deterministic for a given input.
        While held_key is set, the matrix code is written to $CB/$C5 right after each KERNAL key scan
        ($EA7E, after JSR SCNKEY), so programs polling PEEK(197)/PEEK(203) see the key as held."""
        if n <= 0: return
        cid = self.checkpoint(addr)
        fid = self.checkpoint(0xFF48) if self.pending and addr != 0xFF48 else None
        kid = self.checkpoint(0xEA7E) if self.held_key is not None else None
        wids = [self.checkpoint(a) for a in (self.watch or {})]
        try:
            done = 0
            while done < n:
                self.resume(); pc = self.wait_stopped()
                if pc == 0xFF48: self._feed()
                if pc == 0xFF48 and addr != 0xFF48:
                    continue
                if pc == 0xEA7E and self.held_key is not None:
                    self.poke(0xC5, [self.held_key], "cpu"); self.poke(0xCB, [self.held_key], "cpu")
                elif self.watch and pc in self.watch and pc != addr:
                    self.watch[pc] += 1
                else:
                    done += 1
        finally:
            self.delete_checkpoint(cid)
            if fid is not None: self.delete_checkpoint(fid)
            if kid is not None: self.delete_checkpoint(kid)
            for w in wids: self.delete_checkpoint(w)

    def registers(self):
        """Register name id -> value (VICE ids: 0 A, 1 X, 2 Y, 3 PC, 4 SP, 5 flags)."""
        r = self.cmd(0x31, b"\0"); n = struct.unpack("<H", r[:2])[0]; out = {}
        for i in range(n):
            sz, rid, val = struct.unpack("<BBH", r[2 + i * 4:6 + i * 4]); out[rid] = val
        return out

    def irq_return_pc(self):
        """When stopped at the KERNAL IRQ entry ($FF48): the PC the IRQ interrupted."""
        sp = self.registers()[4] & 0xFF
        st = self.mem(0x0100 + ((sp + 2) & 0xFF), 0x0100 + ((sp + 3) & 0xFF), "cpu") if sp < 0xFE else b"\0\0"
        return st[0] | st[1] << 8

    def run_until(self, addr, limit_frames=3000):
        """Run until PC hits addr (exec). Returns True if hit within limit_frames IRQs."""
        cid = self.checkpoint(addr); irq = self.checkpoint(0xFF48)
        try:
            for _ in range(limit_frames):
                self.resume(); pc = self.wait_stopped()
                if pc == 0xFF48: self._feed()
                if pc == addr: return True
            return False
        finally:
            self.delete_checkpoint(cid); self.delete_checkpoint(irq)

    pending = b""   # typed PETSCII not yet in the KERNAL keyboard buffer

    def type(self, text):
        """Queue text for the KERNAL keyboard buffer. The harness writes it into $0277/$C6 itself, at KERNAL IRQ
        entries ($FF48) while frames()/run_until() run: whenever the buffer is empty ($C6 = 0) it is filled with
        up to XMAX ($0289, at most 10) queued keys. So a key arrives at a fixed IRQ count, whatever the host load
        (VICE's own keyboard-buffer feed, monitor command $72, is not used)."""
        data = text if isinstance(text, (bytes, bytearray)) else petscii(text)
        self.pending += bytes(data)

    def _feed(self):
        """At an IRQ entry: move queued keys into an empty KERNAL keyboard buffer. The main program is not inside
        GETIN's SEI section here (the IRQ was taken), and SCNKEY runs after this, so nothing is lost."""
        if not self.pending: return
        z = self.mem(0x00C6, 0x00C6, "ram")[0]
        if z: return
        n = min(len(self.pending), max(1, min(10, self.mem(0x0289, 0x0289, "ram")[0])))
        self.poke(0x0277, self.pending[:n], "ram"); self.poke(0x00C6, [n], "ram")
        self.pending = self.pending[n:]

    def joystick(self, port, value):
        """Set joystick bits (1 up,2 down,4 left,8 right,16 fire) on port 1 or 2; 0 releases."""
        self.cmd(0xA2, struct.pack("<HH", port, value))

    def display_png(self):
        b = self.cmd(0x84, bytes([1, 0]))  # VIC-II, 8-bit indexed
        fl, dw, dh, ox, oy, iw, ih, bpp, ln = struct.unpack("<IHHHHHHBI", b[:21])
        pix = b[4 + fl + 4:4 + fl + 4 + ln]   # [len][fl bytes of fields][buffer len][buffer]
        # crop to the usual visible PAL area: 384x272 around the 320x200 window
        x0, y0 = max(0, ox - 32), max(0, oy - 36); w, h = min(384, dw - x0), min(272, dh - y0)
        rows = [pix[(y0 + y) * dw + x0:(y0 + y) * dw + x0 + w] for y in range(h)]
        return png_indexed(w, h, rows, PEPTO)

    def snapshot(self):
        return {"ram": self.mem(0x0000, 0xFFFF, "ram"), "io": self.mem(0xD000, 0xDFFF, "io"),
                "png": self.display_png()}

    def close(self):
        try:
            if self.sock: self.send(0xBB); time.sleep(0.2)
        except OSError:
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill(); self.proc.wait()
        self.log.close()

    def __enter__(self): return self
    def __exit__(self, *a): self.close()


# Pepto PAL palette (VICE default "pepto-pal")
PEPTO = [0x000000, 0xFFFFFF, 0x68372B, 0x70A4B2, 0x6F3D86, 0x588D43, 0x352879, 0xB8C76F,
         0x6F4F25, 0x433900, 0x9A6759, 0x444444, 0x6C6C6C, 0x9AD284, 0x6C5EB5, 0x959595]


def png_indexed(w, h, rows, pal):
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    plte = b"".join(struct.pack(">I", c)[1:] for c in pal) + b"\0\0\0" * (256 - len(pal))
    raw = b"".join(b"\0" + bytes(x & 0x0F for x in r) for r in rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0)) +
            chunk(b"PLTE", plte) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main(argv):
    if len(argv) < 4 or argv[0] != "run":
        print(__doc__); return 2
    crt, out, irqs = argv[1], argv[2], int(argv[3])
    rest = argv[4:]; extra = []; d64 = typ = png = None
    if "--" in rest:
        i = rest.index("--"); extra = rest[i + 1:]; rest = rest[:i]
    while rest:
        k = rest.pop(0)
        if k == "--d64": d64 = rest.pop(0)
        elif k == "--type": typ = rest.pop(0)
        elif k == "--png": png = rest.pop(0)
        elif k in ("--video", "--kernal", "--dos"): os.environ["C64_" + k[2:].upper()] = rest.pop(0)
        else: raise SystemExit("unknown option " + k)
    with Vice(crt=crt, d64=d64, extra=extra, log=out + ".log") as v:
        if typ:
            v.frames(150)   # let the cartridge reach READY. first
            v.type(typ.encode("latin1").decode("unicode_escape"))
        v.frames(irqs)
        ram = v.mem(0x0000, 0x07FF, "cpu")
        with open(out, "wb") as f: f.write(b"\x00\x00" + ram)
        if png:
            with open(png, "wb") as f: f.write(v.display_png())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
