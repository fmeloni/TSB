#!/usr/bin/env python3
"""Phase B2.2: Ultra-38 flash spike (build/u38_spike.crt) tests on one machine.

  tests/u38_spike.py [--video pal|ntsc] [--kernal stock|jiffy] [--dos stock|jiffy] [--quick]

  1. start-up screen: border/background 6, text 15, rows 1 and 3 exactly as specified (12 Nov amendment), READY.
     on row 5; compared with tests/golden/u38_boot (screen, colour RAM, VIC registers); MEMSIZ $A000
  2. GO 64: stock C64 (38911 BYTES FREE, BASIC vectors stock); GO NEO: TSB Neo 2.60.228 (30719, "tuned", its code
     $8000-$BFFF byte-identical to build/tsbneo_ref.bin); GO TO in a program still a jump; GO 51: ?SYNTAX ERROR as V2
  3. subset scenarios tests/u38.json against TSB Neo's goldens (tests/golden/u38): dispatch, PRINT AT, DO/DONE/ELSE,
     PROC/EXEC, HIRES+PLOT/LINE/TEST, PLAY from TSB's IRQ (SID trace), interrupt stress
  4. memory scenarios tests/u38_mem.json (self-checking): array up to $9FFF, strings in $8000-$9FFF
  5. interrupt counts during the stress program: IRQs and NMIs taken in each state (non-stopping checkpoints)
--quick skips 3-5 (start-up screen and GO only)."""
import os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import vicemon, demo_capture, neoprofile  # noqa: E402

CRT = os.path.join(ROOT, "build/u38_spike.crt")
LBL = os.path.join(ROOT, "build/u38/fl/img.lbl")
ROW1 = "     *** COMMODORE 64 TSB ULTRA ***"
ROW3 = " 64K RAM SYSTEM 38911 BASIC BYTES FREE"


def labels(p):
    d = {}
    for ln in open(p):
        m = re.match(r"\s*([A-Za-z_][\w.]*)\s*=\s*\$([0-9a-fA-F]+)", ln)
        if m: d[m.group(1)] = int(m.group(2), 16)
    return d


def boot_screen(bad):
    gdir = os.path.join(ROOT, "tests/golden/u38_boot/01_final")
    with vicemon.Vice(crt=CRT, timeout=120) as v:
        ok, used, st = demo_capture.wait_stable(v, 60, 1200)
        lines = st.lines()
        if lines[1] != ROW1: bad.append(f"start-up row 1 {lines[1]!r}")
        if lines[3] != ROW3: bad.append(f"start-up row 3 {lines[3]!r}")
        if lines[5] != "READY.": bad.append(f"start-up row 5 {lines[5]!r}")
        if st.vic[7] != 6 or st.vic[8] != 6: bad.append(f"border/background {st.vic[7]}/{st.vic[8]}, want 6/6")
        if any(st.color[40 + i] != 15 for i in range(5, 35)): bad.append("row 1 not in colour 15")
        ram = v.mem(0x0000, 0xFFFF, "ram")
        if ram[0x37] | ram[0x38] << 8 != 0xA000: bad.append("MEMSIZ is not $A000")
        if ram[0x0286] != 15: bad.append(f"cursor colour {ram[0x0286]}, want 15")
        if os.path.isdir(gdir):
            for k in ("screen", "color", "vic"):
                want = open(os.path.join(gdir, k + ".bin"), "rb").read()
                got = getattr(st, k) if k != "screen" else demo_capture.machine_screen(st.screen)
                if want != got: bad.append(f"start-up screen: {k} differs from tests/golden/u38_boot")
        else:
            bad.append("tests/golden/u38_boot missing")
    print("  start-up screen checked")


def go_tests(bad):
    def run(typed, frames=600):
        with vicemon.Vice(crt=CRT, timeout=180) as v:
            demo_capture.wait_stable(v, 60, 1200)
            v.type(typed)
            v.frames(300)       # (GO NEO: the TSB Neo launcher copies 20K first; the screen is still for a while)
            ok, used, st = demo_capture.wait_stable(v, 60, frames)
            return st, v.mem(0x0000, 0xFFFF, "ram")
    st, ram = run("go 64\r")
    t = "\n".join(st.lines())
    if "38911 BASIC BYTES FREE" not in t or "BASIC V2" not in t: bad.append("GO 64: no stock start-up screen")
    vec = [ram[0x300 + 2 * i] | ram[0x301 + 2 * i] << 8 for i in range(6)]
    if any(0xDF00 <= x < 0xE000 for x in vec): bad.append("GO 64: BASIC vectors still point to the Ultra-38 stubs")
    if vicemon.machine()[1] == "stock" and ram[0x0300:0x030C] != bytes.fromhex("8be383a47ca51aa7e4a786ae"):
        bad.append("GO 64: BASIC vectors not stock")
    st, ram = run("go neo\r", 1200)
    t = "\n".join(st.lines()).lower()
    ref = open(os.path.join(ROOT, "build/tsbneo_ref.bin"), "rb").read()
    if "30719 basic bytes free" not in t or "tuned" not in t: bad.append("GO NEO: no TSB Neo start-up screen")
    if ram[0x8000:0xC000] != ref[0:0x4000]: bad.append("GO NEO: TSB Neo's code $8000-$BFFF differs from the released image")
    with vicemon.Vice(crt=CRT, timeout=180) as v:
        demo_capture.wait_stable(v, 60, 1200)
        v.type("new\r10 go to 30\r20 print \"wrong\"\r30 print \"goto ok\"\rrun\r")
        ok, used, st = demo_capture.wait_stable(v, 60, 1200)
        out = [l.strip() for l in st.lines()]
        if "GOTO OK" not in out or "WRONG" in out: bad.append("GO TO in a program")
    st, ram = run("go 51\r")
    if "?SYNTAX  ERROR" not in "\n".join(st.lines()): bad.append("GO 51 (not a mode): no ?SYNTAX ERROR")
    print("  GO 64 / GO NEO / GO TO / GO 51 checked")


def scenarios(bad, machine_args):
    for sc, gd in (("tests/u38.json", "tests/golden/u38"), ("tests/u38_mem.json", "tests/golden/u38_mem")):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/demo_capture.py"), "check", "--crt", CRT,
                            "--scenarios", os.path.join(ROOT, sc), "--golden", os.path.join(ROOT, gd), "-j", "4"]
                           + machine_args, capture_output=True, text=True)
        for l in r.stdout.splitlines()[1:]:
            print("  " + l)
            if not l.startswith(("PASS", "KNOWN")): bad.append("scenario: " + l.split()[1])


def interrupts(bad):
    """Counts during tests/u38/stress.bas. The program's NMI handler ($033C) counts NMIs in $0360/$0361 (TSB's own NMI
    handler would switch CIA 2's interrupts off after the first one)."""
    import struct
    L = labels(LBL)

    def cp(v, addr, cond):
        b = v.cmd(0x12, struct.pack("<HHBBBB", addr, addr, 0, 1, 4, 0)); cid = struct.unpack("<I", b[:4])[0]
        if cond: v.cmd(0x22, struct.pack("<IB", cid, len(cond)) + cond)
        return cid
    points = [("IRQs through TSB's handler (u_irq)", L["u_irq"], None),
              ("  of these: taken in BASIC state", L["u_irq"], b"(@cpu:$01 & $01) == $01"),
              ("IRQs taken with the KERNAL off (RAM $FFFE)", L["ram_irq"], b"(@cpu:$01 & $02) == $00"),
              ("NMIs taken with the KERNAL off (RAM $FFFA)", L["ram_nmi"], b"(@cpu:$01 & $02) == $00"),
              ]
    with vicemon.Vice(crt=CRT, timeout=1500) as v:
        demo_capture.inject_and_run(v, os.path.join(ROOT, "tests/u38/stress.bas"))
        ids = [(k, cp(v, a, c)) for k, a, c in points]
        ok, used, st = demo_capture.wait_stable(v, 30, 30000, until_end=True)
        n = {k: neoprofile.cp_hits(v, i) for k, i in ids}
        m = v.mem(0x0360, 0x0361, "ram"); n["NMIs counted by the program ($0360)"] = m[0] | m[1] << 8
    with vicemon.Vice(crt=CRT, timeout=300) as v:
        demo_capture.inject_and_run(v, os.path.join(ROOT, "tests/u38/nmi_once.bas"))
        c = cp(v, L["u_nmi"], None); c2 = cp(v, L["u_nmi"], b"(@cpu:$01 & $01) == $01")
        demo_capture.wait_stable(v, 30, 3000, until_end=True)
        n["NMIs through TSB Neo's handler (nmi_once.bas)"] = neoprofile.cp_hits(v, c)
        n["  of these: taken in BASIC state"] = neoprofile.cp_hits(v, c2)
    for k, x in n.items(): print(f"  {k:45} {x:7}")
    if n["NMIs through TSB Neo's handler (nmi_once.bas)"] < 20: bad.append("too few NMIs through TSB Neo's handler")
    if n["NMIs counted by the program ($0360)"] < 5000 or n["IRQs through TSB's handler (u_irq)"] < 2000:
        bad.append("stress: too few interrupts")
    if n["NMIs taken with the KERNAL off (RAM $FFFA)"] == 0: bad.append("stress: no NMI landed in a KERNAL-off helper")
    return n


def main(a):
    margs = []
    quick = "--quick" in a
    a = [x for x in a if x != "--quick"]
    while a:
        x = a.pop(0)
        if x in ("--video", "--kernal", "--dos"):
            v = a.pop(0); os.environ["C64_" + x[2:].upper()] = v; margs += [x, v]
    if not os.path.exists(CRT): print("SKIP u38_spike: build/u38_spike.crt missing"); return 0
    print(f"machine: {vicemon.machine_name()}")
    bad = []
    boot_screen(bad)
    go_tests(bad)
    if not quick:
        scenarios(bad, margs)
        interrupts(bad)
    for b in bad: print("  FAIL " + b)
    print(("PASS" if not bad else "FAIL") + f" u38_spike ({vicemon.machine_name()})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
