# TSB Ultra tools

- `setup-linux.sh` builds ACME, xa65, flex and a headless VICE `x64sc` on Linux (about 5 minutes).
- `run_crt.sh` boots a cartridge headless, dumps `$0000-$07FF` and prints the screen plus BASIC pointers.
- `vicemon.py` drives x64sc through its binary monitor (frames, keys, held keys, memory, screenshots).
- `demo_capture.py` runs the scenarios in `tests/demos.json` and captures/checks `tests/golden/`.
- `tsblist.py` lists TSB/Simons' BASIC programs from a D64 using TSB's own keyword table.
- `scr.py` turns a dump into text.

C64 ROMs are not in this repo. Set `VICE_DATA` to a folder with `C64/` and `DRIVES/`
holding the ROM files from a VICE install (for example `share/vice` of VICE 3.10).

    tools/setup-linux.sh && export PATH=$HOME/tsbtools/bin:$PATH
    cp /path/to/TSBneo.crt build/ && make test
