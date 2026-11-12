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
   reports/1.3-detector.md, tools/neodetect.py. The same warning also fires at `LOAD"x",8,1` when the file's
   header load address is in $8000–$CFFF (decision 11 Nov, task 5.3); everything else is checked at RUN.
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
## Decisions (Fafa, 11 Nov)
1. **SWITCHSCREEN is Neo-only.** Target: **20 Neo-only / 19 Ultra** of the 39 demos (the 19 in
   reports/1.3-demo-baseline.md plus SWITCHSCREEN, flagged by the U2+ rule N5). tests/detector/expected.json
   enforces it (`_target`). Gate wording from now on: G1 "detector rules flag the 20 Neo-only programs and none of
   the other 19"; G4 "the 19 Ultra-compatible demos match their goldens in Ultra"; G5 "no warning on the 19
   Ultra-compatible demos". (The plan's gate table still says 19/20 until it is updated from the chat.)
2. **LOAD-time warning:** `LOAD"x",8,1` with a header load address in $8000–$CFFF gives the Neo-only warning
   (task 5.3). Everything else is checked at RUN. On the demo disk 8 files would warn (`neodetect.py --load`,
   list in expected.json `_load_warn`); none of the 19 Ultra demos loads one.
3. **SECURE in Ultra gives an error instead of hanging** (task 4.1). Neo is untouched (it still hangs).
4. **DISPLAY with MEM on returns the real new screen address in Ultra** (task 4.3), i.e. where Ultra keeps the
   MEM screen, not Neo's $CC00.
5. **Task 1.5:** the test corpus gets a corrected copy of DO-TEST.DMO (FETCH into a string variable); the original
   disk stays untouched. OLD-AT stays as it is. IMG VIEWER always runs with an REU.
6. **Tokenizer:** Neo keeps the ELSEOPEN bug; Ultra fixes it. The whole class (a TSB keyword whose stored index
   byte plus the following text reads as a V2 keyword) is listed in reports/1.5-tokenizer-collisions.md. Ultra must
   produce Neo's exact bytes for every line Neo tokenizes correctly (all 1966 corpus lines and all command
   scenarios); the fixed cases are marked as intended differences.

## Test machines (Fafa, 11 Nov)
- Fafa's drives: real 1541, Pi1541, SD2IEC. VICE true-drive 1541 emulation stands in for the first two. The SD2IEC
  cannot be emulated: real hardware only (task 2.5). Never use VICE's virtual/filesystem drive as a stand-in.
- Matrix: PAL/NTSC x KERNAL (stock | JiffyDOS 6.01) x 1541 DOS ROM (stock | JiffyDOS) = 8 machines, `tests/matrix.sh`.
  Every change: full demo + command suites on pal-stock-stock and ntsc-stock-stock, disk-heavy subset on all 8
  (`tests/matrix.sh change`). Before each gate: full suites on all 8 (`tests/matrix.sh gate`). Step 2.0 includes the
  Neo baseline on all 8 for the released CRT and the v0.1 EasyFlash CRT (reports/2.0-machine-matrix.md).
- JiffyDOS ROMs are commercial: corpus/roms/ is git-ignored, never commit them.
- Neo switches off the JiffyDOS function keys at boot (`stx $9b`, TSBneo/tsbneo.a line 336). Ultra must do the same.
- **D-2.0a (decided):** MERGE under the JiffyDOS KERNAL: Neo keeps the bug (`MERGE "x"` without device loads absolute,
  SA $6F); Ultra fixes it (secondary address 0 before MERGE's LOAD, so it always appends). Ultra gets a test for it
  on kernal=jiffy.
- **D-2.0b (pending Fafa; recommended):** TSB.HSG split screen on NTSC: Neo unchanged; Ultra adjusts the delay loop
  from $02A6. Add a picture-based check of the split screen on PAL and NTSC (memory goldens can't see it).
- Optional machine `oldntsc` (VICE `-model oldntsc`, VIC-II 6567R56A, 64 cycles/line): in tests/matrix.sh on request
  only, not in the default runs until Fafa says whether his NTSC C64 has that chip.

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
  and IMG VIEWER without REU misbehave on Neo (handled by decision 5 of 11 Nov).
- TSB's tokenizer: TSB keywords first (table order), then V2 CRUNCH; index bytes that V2 crunches into operator tokens
  are stored EOR $8F (X!, CLS, MAP). Bug: typed ELSEOPEN becomes NO ERROR+"PEN". tools/tsblist.crunch mirrors it
  (1966/1967 corpus lines byte-identical; the odd one cannot be typed).
- The released CRT holds the **disk** build of TSB Neo (`cartridge = 0`: SECURE is keyword 64, overlays load from disk),
  not the `cartridge = 1` variant (MONITOR as keyword 64, LOCAL/GLOBAL = BAD MODE), which was never released.
  build/tsbneo_ref.bin = disk build with the key-table padding $C657-$C74F as $00 = the released image, byte for byte.
- TSB Ultra v0.1 (task 1.4) = build/TSBUltra.crt, EasyFlash: boot code in ROMH bank 0, the released launcher + TSB image
  in ROML banks 0-2 (2 bytes differ: cart off via $DE02=$04). Same 64K RAM at READY as the released CRT. Commodore key
  held at reset = GO 64 path (stock C64). reports/1.4-easyflash-crt.md.
- EasyFlash RAM at $DF00-$DFFF overlaps the REU registers: with both in VICE, reads of $DF00 return EasyFlash RAM; DMA
  still works. TSB Neo writes $DF01-$DF08 at boot. Ultra's $DF00 code (task 2.1) must avoid $DF00-$DF0A.
- SHOW DRIVES is timing-fragile (ST=-128 test; device 16 sometimes -125), on the released CRT too.
- Tokenizer collision class (decision 6): 18 keywords whose number byte is a letter, 68 combinations,
  reports/1.5-tokenizer-collisions.md. Ultra rule: tools/tsblist.crunch(ultra=True); 12,905 lines typed into Neo are in
  tests/tokenizer/neo_typed.tsv. DO's number byte is `"`: the rest of a DO line is plain text by design (DONE, DO NULL).
- JiffyDOS (VICE): the KERNAL banner reads `JIFFYDOS V6.01 (C)1989 CMD` / `C-64 BASIC V2`; the 1541 ROM answers
  `73,JIFFYDOS 5.0 1541`. JiffyDOS LOAD runs with IRQs off (20K in < 1 s). TSB Neo `MERGE "x"` without a device number
  fails under the JiffyDOS KERNAL (its default-device routine leaves SA $6F, so the LOAD is absolute and overwrites the
  program); `MERGE "x",8` works. reports/2.0-machine-matrix.md.
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
- Demo baseline: `make test-demos` (44 scenarios: the 43 + do_test_fixed in tests/demos.json vs tests/golden/, ~6 min); see
  reports/1.3-demo-baseline.md. tools/tsblist.py lists TSB programs from the D64.
- Command suite: `make test-commands` (22 scenarios in tests/commands.json, programs in tests/commands/*.bas,
  goldens in tests/golden/commands/, ~1 min); see reports/1.2-command-suite.md.
- Neo-only detector: tools/neodetect.py (`--load` for the LOAD,8,1 check); `make test` runs tests/detector.sh and
  tests/crunch_corpus.py.
- EasyFlash CRT: `make build` makes build/TSBUltra.crt; `make test` runs tests/ef_tsbultra.py. Baselines on it:
  tests/demos_tsbneo.sh build/TSBUltra.crt, tests/commands_tsbneo.sh build/TSBUltra.crt.
- Machines: `--video pal|ntsc --kernal stock|jiffy --dos stock|jiffy` on tools/demo_capture.py and tools/vicemon.py
  (or env C64_VIDEO/C64_KERNAL/C64_DOS). VICE 3.10 options used: `-model c64|ntsc`, `-kernal <file>`, `-dos1541 <file>`.
  Goldens are pal-stock-stock only; JiffyDOS identity text (banner, drive ID) is mapped back before comparing;
  accepted machine-specific differences are a scenario's `known` list (status KNOWN; optional `"crt"` regex for
  Neo-only differences). `tests/matrix.sh change|gate|disk|oldntsc`. The music SID traces start at the first note
  (`"from": "gate"`). VICE runs with `-raminitrandomchance 0 -seed 1` (random power-on RAM made parallel runs flaky), and typed keys are
  written into $0277/$C6 by the harness at KERNAL IRQ entries, not by VICE's keybuf (`tests/stress_typing.sh`).
- ACME is needed for `make build` (`brew install acme`, or tools/setup-linux.sh on Linux).

## Rules
- Never commit Simons' BASIC or other Commodore ROM images: corpus/simons/ is git-ignored.
- Every change keeps `make test` green; new tests go in tests/.
- Fafa wants calibrated claims: label conclusions [Certain]/[Likely]/[Guessing].
