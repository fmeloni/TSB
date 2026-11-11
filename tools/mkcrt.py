#!/usr/bin/env python3
"""Write and read EasyFlash CRT files (hardware type 32), plan task 1.4.

  mkcrt.py easyflash <out.crt> <name> <roml-stream.bin> <romh-bank0.bin>
      ROML stream: plain binary assembled at $8000, split into 8K ROML chips for banks 0, 1, 2, ...
      ROMH bank 0: plain binary of exactly 8K assembled at $e000 (boot code with the reset vector).
  mkcrt.py dump <file.crt>      list the CHIP packets
CRT format: https://vice-emu.sourceforge.io/vice_17.html#SEC425 (header 64 bytes, then CHIP packets).
EasyFlash: EXROM inactive and GAME active in the header (it boots in Ultimax mode); ROMH chips carry load
address $a000 although the hardware shows them at $e000 in Ultimax mode."""
import struct, sys

BANK = 0x2000


def chip(bank, addr, data):
    data = bytes(data) + b"\xff" * (BANK - len(data))
    return b"CHIP" + struct.pack(">IHHHH", 16 + BANK, 2, bank, addr, BANK) + data


def easyflash(name, roml_banks, romh_banks):
    hdr = b"C64 CARTRIDGE   " + struct.pack(">IHHBB", 64, 0x0100, 32, 1, 0) + b"\0" * 6
    hdr += name.encode("ascii")[:32].ljust(32, b"\0")
    out = bytearray(hdr)
    for b in sorted(set(roml_banks) | set(romh_banks)):
        if b in roml_banks: out += chip(b, 0x8000, roml_banks[b])
        if b in romh_banks: out += chip(b, 0xA000, romh_banks[b])
    return bytes(out)


def read(crt):
    """-> (hw type, exrom, game, name, [(bank, load address, data)])"""
    assert crt[:16] == b"C64 CARTRIDGE   ", "not a CRT"
    hl, ver, hw, exrom, game = struct.unpack(">IHHBB", crt[16:26])
    name = crt[32:64].rstrip(b"\0").decode("latin1"); p = hl; chips = []
    while p < len(crt):
        assert crt[p:p + 4] == b"CHIP"
        ln, ty, bank, addr, size = struct.unpack(">IHHHH", crt[p + 4:p + 16])
        chips.append((bank, addr, crt[p + 16:p + 16 + size])); p += ln
    return hw, exrom, game, name, chips


def main(a):
    if a[0] == "easyflash":
        out, name, roml, romh = a[1:5]
        s = open(roml, "rb").read(); h = open(romh, "rb").read()
        assert len(h) == BANK, f"ROMH bank 0 must be 8K, is {len(h)}"
        banks = {i // BANK: s[i:i + BANK] for i in range(0, len(s), BANK)}
        open(out, "wb").write(easyflash(name, banks, {0: h}))
        print(f"{out}: EasyFlash, ROML banks 0-{max(banks)}, ROMH bank 0, {len(s)} bytes in ROML")
    elif a[0] == "dump":
        hw, ex, gm, name, chips = read(open(a[1], "rb").read())
        print(f"type {hw} EXROM={ex} GAME={gm} name={name!r}")
        for b, ad, d in chips: print(f"  bank {b:2} ${ad:04X} {len(d)} bytes")
    else:
        print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
