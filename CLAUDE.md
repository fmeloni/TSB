# TSB Ultra — project notes for Claude

Goal: Tuned Simons' BASIC (TSBneo 2.60.228) on a C64 cartridge with 54–60K BASIC bytes free,
while old Simons' BASIC programs keep working. Owner: Fafa. Branch: `tsb-ultra`.

Plan and decisions: "TSB Ultra — Alternatives Analysis & Project Plan"
https://claude.ai/artifact/VhxLiJE5gbeRPxeFnX2dJK (phases 0–7, gates G0–G7, task tracker).
Recommended: Alternative 3, a dual-personality EasyFlash cartridge (Classic TSB Neo + Ultra engine).
Decided D1 (10 Nov): TSB Neo 2.60.228 is the reference. "100% compatible" = behaves exactly like
TSB Neo, and every program on corpus/tsbneo_260228.d64 runs flawlessly. No original Simons' BASIC
is used; the Classic Simons slot is dropped.
Open decisions: D2 one mode or two, D3 public vs personal release, D4 acceptable Ultra slowdown.

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
  $6000, $7000, $7400, $7800, $C000, $CA00, $CB00, $CC00, $E000). Ultra must keep those
  addresses and TSB's $C000-$CFFF layout and entry points.

## Running tests on this Mac
- VICE: ~/Applications/VICE-3.10-SDL2-BluetoothFix/bin/x64sc (ROMs in ../share/vice).
  tools/run_crt.sh finds it automatically; override with X64SC=... and VICE_DATA=...
- `make test` needs the released CRT copied to build/TSBneo.crt (source: corpus/simons/TSBneo_md_260228_disklike.crt).
- Demo run: SCRFLAGS=-l tools/run_demo.sh build/TSBneo.crt corpus/tsbneo_260228.d64 center.dmo /tmp/x.bin
  (program names in lower case; -l decodes the lower/upper case charset).
- The macOS harness path is untested so far: verify it first in a native session.
- ACME is needed for `make build` (`brew install acme`, or tools/setup-linux.sh on Linux).

## Rules
- Never commit Simons' BASIC or other Commodore ROM images: corpus/simons/ is git-ignored.
- Every change keeps `make test` green; new tests go in tests/.
- Fafa wants calibrated claims: label conclusions [Certain]/[Likely]/[Guessing].
