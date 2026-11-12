#!/usr/bin/env python3
"""Phase B2.2: pack the Ultra-38 flash spike CRT from the flash build (tools/u38gen.py flash + ACME).

Usage: u38crt.py <builddir> <out.crt>
Bank map (EasyFlash, 8K chips):
  ROMH 0      Ultimax boot (additions/ultra38/ef_boot38.a)
  ROML 0-2    TSB Neo 2.60.228 launcher + image (as the v0.1 CRT): GO NEO
  ROMH 1-4    TSB parts A-D (each at $A000 + its thunks, data copies; common block at COMMON_AT)
  ROML 3      Ultra-38 launcher (CBM80) with the $C000-$CFFF RAM image and the RAM core
"""
import os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcrt, u38gen  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCH_BANK = 3


def labels(p):
    d = {}
    for ln in open(p):
        m = re.match(r"\s*([A-Za-z_][\w.]*)\s*=\s*\$([0-9a-fA-F]+)", ln)
        if m: d[m.group(1)] = int(m.group(2), 16)
    return d


def main(a):
    bd, out = a[0], a[1]
    L = labels(os.path.join(bd, "img.lbl"))
    import json
    u38gen.PARTS = [tuple(x) for x in json.load(open(os.path.join(bd, "parts.json")))]
    img = open(os.path.join(bd, "img.bin"), "rb").read()
    base = 0x0400                       # lowest real address in the plain output (common block)
    R = lambda real, n: img[real - base:real - base + n]
    common = R(0x0400, L["common_end"] - L["common_start"])
    romh = {}
    for k, s, e, b in u38gen.PARTS:
        if not b: continue
        bank = bytearray(b"\xff" * 0x2000)
        # part: real addresses as in TSB Neo (size-preserving rewrite), at $A000 in the bank
        ps = s if k != "C" else s
        part = R(s, e - s)
        bank[0:len(part)] = part
        xs, xe = L["%s_x_start" % k], L["%s_x_end" % k]
        assert xs == 0xA000 + len(part), (k, hex(xs), len(part))
        bank[xs - 0xA000:xe - 0xA000] = R(0x1000 * b, xe - xs)
        bank[u38gen.COMMON_AT - 0xA000:u38gen.COMMON_AT - 0xA000 + len(common)] = common
        romh[b] = bytes(bank)
    open(os.path.join(bd, "ram_c000.bin"), "wb").write(R(0xC000, 0x1000))
    df = R(0x0C00, L["u38_df_end"] - L["u38_df_image"]); ff = R(L["u38_ff_image"], L["u38_ff_end"] - L["u38_ff_image"])
    open(os.path.join(bd, "df.bin"), "wb").write(df); open(os.path.join(bd, "ff.bin"), "wb").write(ff)
    acme = os.environ.get("ACME", "acme")
    ad = os.path.join(ROOT, "additions/ultra38")
    subprocess.check_call([acme, "-f", "plain", "-DU38_BEFCOLD=%d" % L["befcold"], "-DU38_DF_LEN=%d" % len(df),
                           "-DU38_FF_LEN=%d" % len(ff), "-o", os.path.abspath(os.path.join(bd, "launcher.bin")),
                           "u38_launcher.a"], cwd=ad)
    subprocess.check_call([acme, "-f", "plain", "-DU38_LAUNCH_BANK=%d" % LAUNCH_BANK, "-o",
                           os.path.abspath(os.path.join(bd, "boot.bin")), "ef_boot38.a"], cwd=ad)
    roml_neo = open(os.path.join(ROOT, "build/ef_roml.bin"), "rb").read()
    roml = {i // 0x2000: roml_neo[i:i + 0x2000] for i in range(0, len(roml_neo), 0x2000)}
    assert max(roml) < LAUNCH_BANK
    roml[LAUNCH_BANK] = open(os.path.join(bd, "launcher.bin"), "rb").read()
    romh[0] = open(os.path.join(bd, "boot.bin"), "rb").read()
    roml = {k: v + b"\xff" * (0x2000 - len(v)) for k, v in roml.items()}
    assert all(len(v) == 0x2000 for v in list(roml.values()) + list(romh.values())), [(k, len(v)) for k, v in romh.items()]
    open(out, "wb").write(mkcrt.easyflash("TSB ULTRA-38 SPIKE B2.2", roml, romh))
    print(f"{out}: ROML banks {sorted(roml)}, ROMH banks {sorted(romh)}; common block {len(common)} bytes at "
          f"${u38gen.COMMON_AT:04X}; RAM core {len(df)}+{len(ff)} bytes")


if __name__ == "__main__":
    main(sys.argv[1:])
