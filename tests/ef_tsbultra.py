#!/usr/bin/env python3
"""TSB Ultra v0.1 EasyFlash CRT (plan task 1.4). Checks, in order:
  1. build/tsbneo_ref.bin is the TSB Neo image inside the released CRT (if build/TSBneo.crt is present).
  2. ROML banks 0-2 equal the released CRT's banks 0-2 except the two cart-off bytes (lda #$04 : sta $de02).
  3. Power-on starts TSB Neo: 30719 BASIC BYTES FREE, MEMSIZ $8000.
  4. Same 64K RAM at READY as the released CRT, except two or three stack-page bytes (if build/TSBneo.crt is present).
  5. GO 64 path: reset with the Commodore key held (the key read is forced through the monitor, VICE's binary
     monitor cannot press matrix keys) gives a stock C64: 38911 BASIC BYTES FREE, MEMSIZ $A000, while
     TSB Neo is still in RAM at $8000.
  6. A plain reset afterwards starts TSB Neo again.
usage: tests/ef_tsbultra.py [build/TSBUltra.crt]"""
import os, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import vicemon, mkcrt  # noqa: E402

CRT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build/TSBUltra.crt")
MD = os.path.join(ROOT, "build/TSBneo.crt")
fails = []
def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what); ok or fails.append(what)


def screen(v):
    m = v.mem(0x0400, 0x07E7, "ram")
    return [bytes((c & 0x7F) + 0x40 if (c & 0x7F) < 0x20 else c & 0x7F for c in m[i:i + 40]).decode("latin1")
            for i in range(0, 1000, 40)]


def ptr(v, a): m = v.mem(a, a + 1, "ram"); return m[0] | m[1] << 8


def label(lbl, name):
    for l in open(lbl):
        p = l.split()
        if p and p[0] == name: return int(l.split("$")[1].split()[0], 16)
    raise KeyError(name)


def to_ready(v, frames=3000):
    return v.run_until(0xA480, frames)   # BASIC main loop: READY. printed, waiting for input


hw, exrom, game, name, chips = mkcrt.read(open(CRT, "rb").read())
check(hw == 32 and exrom == 1 and game == 0, f"CRT header: type {hw} (EasyFlash), EXROM={exrom} GAME={game} (Ultimax at boot)")
roml = b"".join(d for b, a, d in sorted(chips) if a == 0x8000)
ref = open(os.path.join(ROOT, "build/tsbneo_ref.bin"), "rb").read()
if os.path.exists(MD):
    md = b"".join(d for b, a, d in mkcrt.read(open(MD, "rb").read())[4])
    check(md[190:190 + len(ref)] == ref, "build/tsbneo_ref.bin == TSB Neo image in the released CRT ($8000-$CFFF)")
    diff = [0x8000 + i for i in range(190 + len(ref)) if md[i] != roml[i]]
    check(diff == [0x80B4, 0x80B6], "ROML banks 0-2 == released CRT except the cart-off bytes: " + ",".join(f"${a:04X}" for a in diff))
else:
    print("SKIP released-CRT comparisons: build/TSBneo.crt missing")
    check(roml[190:190 + len(ref)] == ref, "TSB Neo image in ROML banks 0-2")

X = ["-raminitrandomchance", "0"]
with vicemon.Vice(crt=CRT, extra=X) as v:
    check(to_ready(v), "power-on reaches READY")
    s = screen(v); mem = ptr(v, 0x37)
    check(any("30719 BASIC BYTES FREE" in l for l in s) and mem == 0x8000, f"power-on: TSB Neo, 30719 bytes free, MEMSIZ ${mem:04X}")
    ram_ef = v.mem(0, 0xFFFF, "ram")
    check(bytes(v.mem(0x8004, 0x8008, "ram")) == b"CBM80", "TSB Neo's marker at $8004 is lower-case PETSCII (not a KERNAL CBM80)")
    # GO 64 path: reset, stop at the Commodore-key test, pretend the key is down
    cid = v.checkpoint(label(os.path.join(ROOT, "build/ef_romh0.lbl"), "keytest"))
    v.reset(); pc = v.wait_stopped()
    check(pc == label(os.path.join(ROOT, "build/ef_romh0.lbl"), "keytest"), f"reset enters the EasyFlash boot code (stopped at ${pc:04X})")
    v.set_register(0, 0xDF); v.delete_checkpoint(cid); v.resume()
    check(to_ready(v), "GO 64 path reaches READY")
    s = screen(v); mem = ptr(v, 0x37)
    check(any("COMMODORE 64 BASIC V2" in l for l in s) and any("38911 BASIC BYTES FREE" in l for l in s) and mem == 0xA000,
          f"GO 64 path: stock C64, 38911 bytes free, MEMSIZ ${mem:04X}")
    check(not any("TUNED" in l for l in s), "GO 64 path: TSB not restarted from RAM")
    v.reset()
    check(to_ready(v), "plain reset reaches READY")
    s = screen(v); mem = ptr(v, 0x37)
    check(any("30719 BASIC BYTES FREE" in l for l in s) and mem == 0x8000, f"plain reset: TSB Neo again, MEMSIZ ${mem:04X}")

if os.path.exists(MD):
    with vicemon.Vice(crt=MD, extra=X) as v:
        to_ready(v); ram_md = v.mem(0, 0xFFFF, "ram")
    diff = [i for i in range(0x10000) if ram_md[i] != ram_ef[i]]
    # $0132/$0134: the patched cart-off bytes left by the copy routine at $0100; $01E9: a stack leftover
    # whose value depends on boot timing (the EasyFlash boot code runs a few hundred cycles first)
    check({0x0132, 0x0134} <= set(diff) <= {0x0132, 0x0134, 0x01E9}, "64K RAM at READY == released CRT except stack page: " + ",".join(f"${a:04X}" for a in diff))

print(("FAIL" if fails else "PASS") + f" ef_tsbultra ({len(fails)} failure(s))")
sys.exit(1 if fails else 0)
