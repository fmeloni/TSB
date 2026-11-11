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

C64 ROMs are not in this repo. Set `VICE_DATA` to a folder with `C64/` and `DRIVES/`
holding the ROM files from a VICE install (for example `share/vice` of VICE 3.10).

    tools/setup-linux.sh && export PATH=$HOME/tsbtools/bin:$PATH
    cp /path/to/TSBneo.crt build/ && make test
