# TSB Ultra — project notes for Claude

Goal: Tuned Simons' BASIC (TSBneo 2.60.228) on a C64 cartridge with 54–60K BASIC bytes free,
while old Simons' BASIC programs keep working. Owner: Fafa. Branch: `tsb-ultra`.

Plan and decisions: "TSB Ultra — Alternatives Analysis & Project Plan"
https://claude.ai/artifact/VhxLiJE5gbeRPxeFnX2dJK (phases 0–7, gates G0–G7, task tracker).
Decided D1 (10 Nov): TSB Neo 2.60.228 is the reference. "100% compatible" = behaves exactly like
TSB Neo, and every program on corpus/tsbneo_260228.d64 runs flawlessly. No original Simons' BASIC
is used; the Classic Simons slot is dropped.

## Decided design (10 Nov) — what we are building
1. At power-on the cartridge runs **TSB Ultra in U2+ mode**, no menu. BASIC workspace $0801–$CFFF =
   **51,199 bytes free**. Hi-res colour data and the MEM screen live in the RAM under the I/O chips
   ($D000–$DFFF), so the figure holds with HIRES, MULTI or MEM on. TSB's code runs from flash.
2. **GO 64**: switches the cartridge off, restarts as a stock C64 (38911 BASIC BYTES FREE).
3. **GO NEO**: restarts in classic TSB Neo 2.60.228 (30719 BASIC BYTES FREE), byte-for-byte unchanged.
   GO is a V2 keyword (GO TO is legal), so the new GO acts only when followed by 64 or NEO; GO TO 100 still works.
   Neo has no GO ULTRA (decided): the reset button returns to Ultra (the cartridge reactivates on reset).
4. At **RUN**, a program that looks Neo-only gets
   `THIS PROGRAM SEEMS TO BE WRITTEN TO RUN ONLY IN TSB NEO. START TSB NEO? (Y/N)`.
   Y: switch to Neo keeping the program in memory (only if it fits: ≤ 30,719 bytes, ending below $8000;
   variables cleared as after RUN), then RUN it. N: run it in Ultra anyway.
   The detector reads literal addresses only ("seems to"); rules and their check against the demo disk:
   reports/1.3-detector.md, tools/neodetect.py.
5. Delivered as an **EasyFlash CRT** (hardware type 32, up to 1 MB), flashable with EasyProg on EasyFlash /
   EasyFlash 3, loadable on Kung Fu Flash and Ultimate 64 / 1541 Ultimate.
6. At the end: **memory maps** of stock C64, TSB Neo and TSB Ultra side by side in the pagetable.com style,
   built with the generator of Michael Steil's c64ref (BSD-2), three switchable columns (task 7.1).
7. **TSB Ultra start-up screen**: border and background blue (colour 6, $D020/$D021), text light grey
   (colour 15, $0286). Two lines of text, then READY.:
   ```
        *** COMMODORE 64 TSB ULTRA ***
    64K RAM SYSTEM 51199 BASIC BYTES FREE
   ```
   (first line 5 leading spaces, centred; second line 1 leading space). The byte count is calculated at
   boot like a stock C64 (MEMSIZ − TXTTAB: $D000 − $0801 = 51199), never a typed-in constant. Gate G6 gets a pixel-exact
   golden of this screen.
Ultra also publishes a compatibility address map (jiffy counter, hooks, entry points, settings) so
Neo-only programs can be ported by changing addresses.
Open decisions: D3 public vs personal release (interpreter base, licensing), D4 acceptable Ultra
slowdown (plan default 25%). G2 is the go/no-go: if 51,199 bytes with graphics at acceptable speed fails,
the cartridge ships as TSB Neo + GO 64 only.

## Working split
- This Claude Code session (on the Mac) does the build and test work in this repo.
- The plan doc is maintained from the claude.ai chat. Put results the plan needs in reports/
  (one markdown file per task, e.g. reports/1.3-demo-baseline.md) so they can be picked up there.

## Facts established (verified, don't re-derive)
- The released CRT is Magic Desk (type 19, 8 x 8K). A launcher copies TSB to RAM $8000-$CFFF and
  switches the cartridge off. Boot shows 30719 BASIC BYTES FREE, MEMSIZ $8000.
- `make build` reproduces the CRT's TSB image byte for byte except the key table at $C657-$C74F.
- TSB calls 57 BASIC ROM routines and 44 KERNAL routines, with about 213 pointer-indirect accesses.
- TSB is not 100% Simons-compatible: about 25 Simons commands were rewritten (C64-Wiki TSB page).
- Hard requirement from Fafa: every program on corpus/tsbneo_260228.d64 must run flawlessly.
  Those demos load data and extensions to fixed addresses ($033C, $0400, $2000, $3800, $4000,
  $6000, $7000, $7400, $7800, $C000, $CA00, $CB00, $CC00, $E000). In the decided design they are met
  two ways: programs that reach into TSB ($8000-$CFFF) run in TSB Neo after the RUN warning; the rest
  must run unchanged in Ultra (addresses below $8000 and $E000 stay as they are).
- The demo baseline (plan task 1.1, file reports/1.3-demo-baseline.md) found that the demos also PEEK/POKE/SYS into TSB code at $8000-$BFFF (patch points, tables,
  hook vectors); see the table in reports/1.3-demo-baseline.md. IMG VIEWER and WRITEIMAGES2REU need an REU.
- The harness must not pass -busdevice8: it makes VICE's virtual IEC device answer instead of the emulated 1541
  (status "73,VIRTUAL DRIVE EMULATION V3.5"). With the real 1541 emulation SHOW DRIVES works; only DO-TEST, OLD-AT
  and IMG VIEWER without REU misbehave on Neo.
- TSB's tokenizer: TSB keywords first (table order), then V2 CRUNCH; index bytes that V2 crunches into operator tokens
  are stored EOR $8F (X!, CLS, MAP). Bug: typed ELSEOPEN becomes NO ERROR+"PEN". tools/tsblist.crunch mirrors it
  (1966/1967 corpus lines byte-identical; the odd one cannot be typed).
- A LOAD inside a program restarts it from the first line with variables kept, also TSB's LOAD name,dev,0,addr
  (hence the corpus idiom IF A=0 THEN A=1:LOAD ...). SECURE (ON/OFF/0) hangs TSB Neo.

## Running tests on this Mac
- VICE: ~/Applications/VICE-3.10-SDL2-BluetoothFix/bin/x64sc (ROMs in ../share/vice).
  tools/run_crt.sh finds it automatically; override with X64SC=... and VICE_DATA=...
- `make test` needs the released CRT copied to build/TSBneo.crt (source: corpus/simons/TSBneo_md_260228_disklike.crt).
- Demo run: SCRFLAGS=-l tools/run_demo.sh build/TSBneo.crt corpus/tsbneo_260228.d64 center.dmo /tmp/x.bin
  (program names in lower case; -l decodes the lower/upper case charset).
- macOS harness verified (10 Nov): `make test` passes in ~9 s. VICE is driven through its binary monitor
  (tools/vicemon.py), with no window (SDL_VIDEODRIVER=dummy). The old -moncommands approach hung: SDL VICE ignores `quit`.
- Demo baseline: `make test-demos` (43 scenarios in tests/demos.json vs tests/golden/, ~6 min); see
  reports/1.3-demo-baseline.md. tools/tsblist.py lists TSB programs from the D64.
- Command suite: `make test-commands` (21 scenarios in tests/commands.json, programs in tests/commands/*.bas,
  goldens in tests/golden/commands/, ~1 min); see reports/1.2-command-suite.md.
- Neo-only detector: tools/neodetect.py; `make test` runs tests/detector.sh and tests/crunch_corpus.py.
- ACME is needed for `make build` (`brew install acme`, or tools/setup-linux.sh on Linux).

## Rules
- Never commit Simons' BASIC or other Commodore ROM images: corpus/simons/ is git-ignored.
- Every change keeps `make test` green; new tests go in tests/.
- Fafa wants calibrated claims: label conclusions [Certain]/[Likely]/[Guessing].
