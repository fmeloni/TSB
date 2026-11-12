# TSB Ultra tools

- `setup-linux.sh` builds ACME, xa65, flex and a headless VICE `x64sc` on Linux (about 5 minutes).
- `run_crt.sh` boots a cartridge headless, dumps `$0000-$07FF` and prints the screen plus BASIC pointers.
- `vicemon.py` drives x64sc through its binary monitor (frames, keys, held keys, memory, screenshots).
- `demo_capture.py` runs the scenarios in `tests/demos.json` (demos) and `tests/commands.json` (command suite)
  and captures/checks `tests/golden/` and `tests/golden/commands/`.
- `tsblist.py` lists TSB/Simons' BASIC programs from a D64 using TSB's own keyword table; `crunch()`/`make_prg()`
  tokenize text exactly like TSB Neo (its tokenizer, then V2 CRUNCH); `ultra=True` applies Ultra's fix
  (reports/1.5-tokenizer-collisions.md).
- `neodetect.py` is the Neo-only detector (rules N1-N6, `--load` for the LOAD,8,1 check, reports/1.3-detector.md).
- `mkcrt.py` writes and dumps EasyFlash CRTs (reports/1.4-easyflash-crt.md).
- `cmd_coverage.py` counts which TSB and V2 keywords the command suite exercises.
- `scr.py` turns a dump into text.

Machine options (all VICE-based tools): `--video pal|ntsc`, `--kernal stock|jiffy`, `--dos stock|jiffy` on
`vicemon.py run` and `demo_capture.py`, or the env variables `C64_VIDEO`, `C64_KERNAL`, `C64_DOS` (also for
`run_crt.sh`). Default pal/stock/stock, the machine all goldens were captured on. `jiffy` uses
`corpus/roms/JiffyDOS_C64/JiffyDOS_C64_6.01.bin` (VICE `-kernal`) and `corpus/roms/JiffyDOS_1541/JiffyDOS_1541-II_6.00.bin`
(VICE `-dos1541`, drive type stays 1541 with true-drive emulation); override with `JIFFY_KERNAL` / `JIFFY_DOS`.
`tests/matrix.sh change|gate|disk|oldntsc [crt]` runs the 8 machines (reports/2.0-machine-matrix.md).

Determinism: `vicemon.Vice` starts VICE with `-raminitrandomchance 0 -seed 1` (no random bits in power-on RAM), and
`Vice.type()` writes keys into the KERNAL buffer ($0277/$C6) itself at KERNAL IRQ entries instead of using VICE's
keyboard feed, so runs give the same result under any host load (`tests/stress_typing.sh`). `demo_capture.py
--repeat N` runs each selected scenario N times. (`run_demo.sh` is a manual tool and still uses VICE's `-keybuf`.)

Phase B1 (Ultra-38 design, reports/B1-ultra38-design.md): `neoinventory.py <acme report>` lists what TSB Neo's code
does that a flash layout must handle (ROM calls, $01 writes, writes into its own code, pointer accesses, cross-region
calls); `neoprofile.py bench.bas ...` counts those events on Neo while a program runs (VICE checkpoints that don't
stop the CPU; $A000-$BFFF ones only count with the BASIC ROM switched out); `ultra38model.py` turns the counts into a
slowdown prediction for the two layouts. `make bench` runs all three on tests/bench/. `neodetect.py --target ultra38`
applies the Ultra-38 detector rules.

Phase B2 (Ultra-38 spikes, reports/B2-spike.md): `u38gen.py b21|flash <dir>` rewrites TSB Neo's source so every
crossing goes through the Ultra-38 stubs of `additions/ultra38/core38.a` (`b21`: TSB Neo stays in RAM at its own
addresses, the B2.1 speed spike; `flash`: six ROMH banks plus the $C000 RAM part, the B2.2 flash spike); `u38crt.py`
packs the flash spike CRT; `u38bench.py` times programs cycle-exactly (CIA 2 as a 32-bit counter) and counts stub
events; `u38demotime.py` times corpus demos until their golden appears; `u38compare.py` prints the report tables;
`u38stubcost.py` measures single stub paths; `trace38.py` / `trace38f.py` single-step a spike and show where it went
wrong. `make bench38` runs the timings; `make test-u38` and `tests/matrix.sh spike38` the flash spike tests.

C64 ROMs are not in this repo. Set `VICE_DATA` to a folder with `C64/` and `DRIVES/`
holding the ROM files from a VICE install (for example `share/vice` of VICE 3.10).

    tools/setup-linux.sh && export PATH=$HOME/tsbtools/bin:$PATH
    cp /path/to/TSBneo.crt build/ && make test
