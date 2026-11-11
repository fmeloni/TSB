#!/usr/bin/env python3
"""CLAUDE.md rule: no Commodore ROM images in git. Fails if any file under tests/golden holds a 2 KB block that is
75% or more identical to a 2 KB block of the C64 character, BASIC or KERNAL ROM (read from the VICE data folder).
ROM-derived charsets are stored as charset.rom.txt (hash + changed bytes) instead."""
import glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import vicemon  # noqa: E402
d = os.path.join(vicemon.find_vice()[1], "C64")
roms = [open(f, "rb").read() for p in ("chargen*", "basic*", "kernal*") for f in sorted(glob.glob(os.path.join(d, p)))[:1]]
if not roms: print("SKIP no_rom_in_goldens: no ROMs found in", d); sys.exit(0)
blocks = {r[i:i + 2048] for r in roms for i in range(0, len(r) - 2047, 2048)}
bad = []
for f in glob.glob(os.path.join(HERE, "golden", "**", "*.bin"), recursive=True):
    b = open(f, "rb").read()
    for o in range(0, max(1, len(b) - 2047), 256):
        w = b[o:o + 2048]
        if len(w) == 2048 and w.count(w[0]) < 1900 and any(sum(x == y for x, y in zip(w, r)) >= 1536 for r in blocks):
            bad.append(os.path.relpath(f, HERE)); break
print(("FAIL" if bad else "PASS") + f" no_rom_in_goldens" + (": " + ", ".join(bad) if bad else ""))
sys.exit(1 if bad else 0)
