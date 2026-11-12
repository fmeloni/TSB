# Phase B1 — Ultra-38 design

Date: 2026-11-12. Phase B1 after the direction change of 12 Nov: build **Ultra-38** first, with BASIC keeping the C64's own
layout ($0801–$9FFF, 38,911 bytes free, the C64's BASIC ROM unmodified) and TSB running from flash, switched in only
while TSB code runs. Neo's $C000–$CFFF layout stays. B1 covers benchmarks, inventory, design, slowdown prediction,
detector re-derivation and a revised task list. B2 is the go/no-go. Labels: [Certain] = run or read here;
[Likely] = strong inference; [Guessing] = plausible, unchecked.

## Result

- **Recommended layout (H): all TSB code runs from 8K ROMH windows at $A000, with $01 = $36 and EasyFlash in 16K mode.**
  In that state the C64 sees RAM at $0000–$9FFF, TSB at $A000–$BFFF, RAM at $C000–$CFFF, I/O and the KERNAL. That is the
  same picture as Neo's own "BASIC ROM out" state ($36), except that $8000–$9FFF is BASIC RAM instead of TSB code.
  So BASIC's program, variables and strings stay directly visible to TSB code, with no slow path on any pointer access.
  Calls into the BASIC ROM go through a RAM stub that switches the cartridge off. [Certain that the mapping works in
  VICE: checked here, see "Two layouts". Likely on real hardware: it's the standard 16K-cartridge PLA mode; task 2.5.]
- **Predicted slowdown over TSB Neo: +1% to +5% on all 7 benchmarks**, once the 17 hottest little helpers are copied into
  every code bank. Without the copies, hi-res graphics would cost +32%. [Likely < 10%; the exact figures are a model
  (event counts measured on Neo × stub cycles counted by hand) and are Guessing to ±3 points. B2 measures them.]
- **The other layout (N, Neo's addresses kept, core in ROML at $8000) predicts up to +30%** (screen block commands). It
  hides BASIC RAM $8000–$9FFF while TSB runs, so every TSB pointer access needs a page check. Rejected.
- **Neo itself is already slower than a stock C64 on plain V2 code**: GOSUB/GOTO +22%, strings +10%, arithmetic +3%
  (TSB's hooks on every statement and every operand). [Certain, measured]. This matters for D4: "25% slowdown" against
  Neo or against a stock C64? Against the stock C64, Ultra-38 is predicted at about +26% on the GOSUB/GOTO benchmark,
  Neo is already at +22%. **Decision needed (D4 reference).**
- **Inventory** (tools/neoinventory.py, from the assembler listing): 227 ROM call sites (80 + 25 into the BASIC ROM, the
  rest KERNAL), 57 distinct BASIC routines, **no BASIC ROM call from Neo's $A000–$BFFF code** (Neo already keeps those
  calls in $8000–$9FFF and $C000–$CFFF), 18 variables/operands written inside the code area (31 sites), 10 direct
  $01 writes plus 62 call sites of the port helpers, 218 pointer-indirect instructions. [Certain]
- **Detector re-derived for Ultra-38** (`tools/neodetect.py --target ultra38`, `tests/detector/expected_ultra38.json`,
  marked *proposed*): **12 of the 39 demos stay Neo-only, 27 run in Ultra-38.** The 8 that move over use only Neo's
  $C000–$CFFF areas, which Ultra-38 keeps. None of the 19 Ultra demos is flagged. The LOAD,8,1 warning drops from 8 files
  to 1 (TSB.NEO itself). [Certain for what the rules flag; Likely that the 8 run, provided Ultra-38 keeps $C000–$CFFF exactly
  as Neo has it, including the live jiffy counter at $C516.]
- Ultra-51 stays a later goal: the 2.1 core still builds and passes (`make test`), and the section "Path to Ultra-51"
  lists what carries over and what stays open.

## Ultra-38 memory map

| Range | Stock C64 | TSB Neo | Ultra-38 |
|---|---|---|---|
| $0801–$7FFF | BASIC | BASIC (MEMSIZ $8000) | BASIC |
| $8000–$9FFF | BASIC | TSB code (core) | **BASIC** (MEMSIZ $A000, 38,911 bytes) |
| $A000–$BFFF | BASIC ROM (RAM under it free) | TSB code (commands) in RAM; BASIC ROM switched in for ROM calls | BASIC ROM; ROMH (TSB code) while TSB runs; RAM under it **free**, as on a stock C64 |
| $C000–$CFFF | free RAM | TSB data, tables, some code, extension areas, MEM screen | **same as Neo** (data at the same addresses; Neo's code bytes left in place but not executed) |
| $D000–$DFFF | I/O | I/O | I/O; EasyFlash RAM $DF0B–$DFFD = stubs ($DF00–$DF0A untouched) |
| $E000–$FF3F | KERNAL (RAM under it) | hi-res bitmap under the KERNAL | same as Neo |
| $FF40–$FFFF | KERNAL | KERNAL; RAM $FFFA NMI vector set by Neo | KERNAL; RAM under it: helpers for KERNAL-off code and the RAM CPU vectors (from the 2.1 core) |

## Benchmarks

Seven programs in `tests/bench/`, run from RUN to the return to the main loop, on TSB Neo (released CRT) and, for the
V2-only ones, on a stock C64. PAL, frames = IRQs from RUN to the end (19,656 cycles each). `make bench` reruns them.

| Benchmark | What it does | Stock C64 | TSB Neo | Neo vs stock |
|---|---|---|---|---|
| v2_math | FOR loop, + * SQR INT / | 1291 | 1331 | +3.1% |
| v2_string | string array, STR$ MID$ LEFT$ +, garbage collection | 573 | 633 | +10.5% |
| v2_goto | GOSUB/RETURN, ON GOTO, IF | 981 | 1198 | +22.1% |
| tsb_text | PRINT AT, DUP, PLACE, CENTER, USE | — | 577 | — |
| tsb_screen | FILL, INV, MOVE, UPB, FCOL (whole screen) | — | 564 | — |
| tsb_hires | HIRES, LINE ×50, CIRCLE ×10, PLOT+TEST ×301, BLOCK | — | 591 | — |
| tsb_flow | REPEAT/UNTIL with DIV MOD FRAC, LOOP/EXIT IF, EXEC/PROC | — | 1357 | — |

[Certain] for the frame counts: they're deterministic, identical in two runs, and non-stopping checkpoints don't change them.

## Inventory of TSB Neo

From `tools/neoinventory.py` (ACME report of TSBneo/tsbneo.a). `tests/neo_inventory.py` in `make test` pins the key numbers.

| Item | Count | What Ultra-38 does with it |
|---|---|---|
| Code bytes per region | $8000–$9FFF 6,769 (+1,423 data); $A000–$BFFF 8,155; $C000–$CFFF 1,764 in $C000–$C070, $C750–$C9CE, $CC00–$CFFA | all moves to ROMH banks at $A000 (reassembled) |
| ROM call sites | 227: BASIC 80 from $8000 code, 25 from $C000 code, **0 from $A000 code**; KERNAL 63 / 39 / 20 | BASIC: through the ROM-call stub; KERNAL: direct (visible with $36) |
| Distinct ROM routines | 57 BASIC, 48 KERNAL | one flash thunk per BASIC target and bank |
| CHRGET/CHRGOT calls | 64 sites | direct (RAM at $0073, text in visible RAM) |
| Neo's own ROM-call helper (pspeibe, via the JMP at $54) | 1 site, 35-entry table | becomes the ROM-call stub |
| $01 writes | 10 direct (MEMPEEK $30, MEMLOAD/SAVE DMA $30/$35, SCRSV/SCRLD $34, port save/restore) + 62 JSR/JMP sites calling basromein/basromaus/kerromein/kerromaus/charen0/charen1 | BASIC in/out: gone (stubs). KERNAL/I/O off: small RAM helpers (the code that runs with HIRAM=0 can't be in ROMH) |
| Writes into the code area $8000–$BFFF | 31 sites, 18 targets: vecrenum/vecplace ($89xx vectors), getpktf, toul3, pdot/pstack ($B52D/$B52E), the SCRSV/SCRLD self-modified operands ($A568–$A5DF), patchan (memhook → $95A2) | move to RAM variables (flash can't be written) |
| Reads of ROM data | $A326/$A327 (BASIC error-address table), JMP ($A002) (BASIC warm start), $E3AB, $FF00 | the two BASIC ones need the ROM visible: constants or a read through the stub |
| Pointer-indirect instructions | 218 sites ($8000 70, $A000 95, $C000 53) | unchanged in layout H |
| Vectors TSB installs | $0300–$030B (all six: IERROR IMAIN ICRNCH IQPLOP IGONE IEVAL), $0314 IRQ, $0316 BRK, $0318 NMI, $0330/$0332 LOAD/SAVE, RAM $FFFA NMI | point to RAM entry stubs |
| Cross-region JSR/JMP | $A000→$8000: 267 JSR + 87 JMP; $8000→$A000: 20 + 9; $C000→$8000: 84 + 15 | in layout H: far calls between banks, except the hot helpers copied into each bank |

[Certain] for the counts. The 57 BASIC routines agree with the earlier count in CLAUDE.md. The KERNAL figure is 48 here
against 44 there; I haven't reconciled the two, and it doesn't matter for layout H, where KERNAL calls stay direct.

## Two layouts

TSB's 17 KB of code needs a home that is visible together with BASIC RAM up to $9FFF. EasyFlash can show flash at
$8000 (ROML) and $A000 (ROMH). Measured in VICE (`build/TSBUltra.crt`, registers set from the monitor) [Certain in VICE]:

| $DE02 | $01 | $8000 | $A000 | $E000 |
|---|---|---|---|---|
| $04 (off) | $37 | RAM | BASIC ROM | KERNAL |
| $07 (16K) | $37 | ROML | ROMH | KERNAL |
| $07 (16K) | **$36** | **RAM** | **ROMH** | **KERNAL** |
| $07 (16K) | $35 | RAM | RAM | RAM |
| $07 (16K) | $34 | RAM | RAM | RAM (no I/O) |
| $06 (8K) | $37 | ROML | BASIC ROM | KERNAL |

- **Layout N, Neo's addresses**: core in ROML at $8000, commands in ROMH at $A000, $01 = $37. Neo's code needs almost no
  changes (`basromein` becomes 8K mode, `basromaus` 16K mode). But while TSB runs, BASIC RAM $8000–$9FFF is hidden. Strings
  always live there (they grow down from $A000), and so do long programs. So every TSB pointer access needs a page
  check, every CHRGET from TSB needs the cartridge off, and every BASIC ROM call too.
- **Layout H, $A000 windows**: every piece of TSB code runs from ROMH with $01 = $36. All of $0000–$9FFF is plain RAM to
  TSB. Neo's split helps: its $A000 code never calls the BASIC ROM, and its $8000 code is mostly small helpers. The cost
  is that Neo's core ($8000 code) and its commands ($A000 code) end up in different banks, so calls between them switch
  banks unless the callee is copied into the caller's bank.

Layout H wins on the measured counts (next section) and has no correctness exposure to where BASIC puts its data.
**Recommendation: H.**

## Design (layout H)

### Banks

TSB code is reassembled from TSBneo/tsbneo.a into 8K ROMH images at $A000 (ACME `!pseudopc`). Proposed allocation,
leaving room for Ultra-51 [Guessing on the sizes, ±1 bank]:

| Bank | ROML ($8000, data only in layout H) | ROMH ($A000, code) |
|---|---|---|
| 0 | Neo launcher + image part 1 (as v0.1) | boot code (Ultimax start), mode table, `GO` |
| 1 | Neo image part 2 | **core**: Neo's $8000–$9FFF code (interpreter hook, dispatch, helpers), ROM-call thunks |
| 2 | Neo image part 3 | **commands A**: Neo's $A000–$BFFF code except graphics, plus hot-helper copies |
| 3 | overlays (MEM, EXT, HSG, MON) | **commands B**: graphics, plus hot-helper copies |
| 4 | overlays | Neo's $C000–$CFFF code, cold code moved out of the core (COLD, start-up, RENUMBER …) |
| 5–7 | spare | spare (Ultra-38 growth) |
| 8–15 | spare | spare |
| 16–47 | **reserved for Ultra-51** | **reserved for Ultra-51** |
| 48–63 | spare | spare |

The core bank is full today (Neo's $8000–$9FFF is exactly 8 KB). The ROM-call thunks (44 BASIC targets called from Neo's $8000 code × 19 bytes ≈ 0.85 KB; the 19 from its $C000 code go with that code into bank 4)
need about 1 KB of cold code moved out to bank 4. [Guessing]

### RAM used by Ultra-38

- EasyFlash RAM $DF0B–$DFFD (243 bytes, visible whenever I/O is on, cartridge off or not): entry stubs, ROM-call stub,
  far-call stub, exit stub, the bank/state byte. $DF00–$DF0A stay untouched (REU registers, step 1.4). [Likely to fit:
  ~11 entry stubs × ~12 bytes + ~90 bytes of shared stubs.]
- RAM $FF40–$FFFF under the KERNAL: the RAM CPU vectors and the NMI path from the 2.1 core, plus the read helpers for code
  that runs with the KERNAL switched off. Neo's bitmap ends at $FF3F.
- $C000–$CFFF: exactly Neo's data layout. Neo's code bytes there stay as a dead copy, so programs that PEEK them (version
  checks) see the same values. The 18 code-area variables move into Neo's free bytes or into $DFxx. [Guessing which.]
- $A000–$BFFF RAM (under the BASIC ROM) stays **free for programs**, as on a stock C64.

### Stubs (sketches, cycle counts by hand)

Entry from BASIC or the KERNAL (one per vector, in $DFxx):

```
u_igone  lda #BANK_CORE  ; 2
         sta $de00       ; 4   select the bank
         lda #$07        ; 2
         sta $de02       ; 4   16K mode
         lda #$36        ; 2
         sta $01         ; 3   BASIC ROM out: $8000 RAM, $A000 ROMH
         jmp sbasbef     ; 3   = 20 cycles over Neo's direct jump
```

Exit into the BASIC ROM, no return (`jmp $a7ae`, `jmp $bcf3` …): `php pha lda #$37 sta $01 lda #$04 sta $de02 pla plp
jmp target` = 28 cycles. A ROM call with return (`jsr frmnum`): a flash thunk per target stores the target in the JMP at
$54/$55/$56 (Neo already uses that JMP for its ROM calls) and jumps to the RAM stub, which switches to $37 + cartridge off,
calls, and switches back. Total 83 against 12 for a plain JSR/RTS (+71). A far call between banks: flash thunk + RAM stub
that pushes the caller's bank, ~75 against 12 (+63); a far jump +27.

Interrupts: the KERNAL stays visible in every state TSB code runs in ($36), so IRQ and NMI go through the KERNAL as usual.
$0314/$0318 point to entry stubs that save $DE00/$DE02/$01, switch to the TSB bank, run Neo's handler and restore. While a
helper runs with the KERNAL off (sei, as Neo already does), an NMI goes through the RAM vector at $FFFA to the 2.1 core's
`ram_nmi`. [Likely; the same mechanism passed 10,000+ NMIs in the 2.1 stress test.]

Code that switches the KERNAL or I/O off (MEMPEEK, SCRSV/SCRLD, MEMLOAD/SAVE DMA, the hi-res pixel read-modify-write after
`kerromaus`, the charset copy after `charen0`) cannot run in ROMH, because $A000 turns into RAM. It becomes a short helper
in $FF40+ or $DFxx that does only the access. Neo pays about the same for its own `jsr kerromaus` / `jsr kerromein`, so
this costs nothing extra in the model. [Likely]

Optimisation left for later: IEVAL (every operand) and IGONE (every statement) are the most frequent entries. A RAM fast
path for the common case ("not $, %, or a TSB token" for IEVAL) would remove most of their entry/exit cost. Not counted
in the prediction.

### Boot, start-up screen, modes

- Boot as v0.1 (Ultimax start in ROMH bank 0), then: KERNAL init, `MEMSIZ = $A000` set explicitly (the RAM test would stop at a
  cartridge), Neo's COLD sequence (vectors, `stx $9b` for the JiffyDOS keys), then the start-up screen of the 12 Nov
  amendment: border/background 6, text 15, row 1 `     *** COMMODORE 64 TSB ULTRA ***`, row 3
  ` 64K RAM SYSTEM 38911 BASIC BYTES FREE` (one space after SYSTEM). The number is MEMSIZ − TXTTAB computed and printed at boot.
- Mode switch, generic: `GO` followed by an argument looked up in a mode table in bank 0 (argument → entry routine). Today
  `64` (cartridge off, reset into a stock C64, 38911) and `NEO` (reset into TSB Neo 2.60.228 byte-identical, 30719). Any
  other argument, `TO` included, goes to V2's normal GO handling, so `GO TO` is untouched. A later Ultra-51 entry is one more
  table row. Checked with tools/tsblist.crunch: `GO NEO`, `GO 64`, `GO 51`, `GO ULTRA`, `GO U51` all leave the argument as
  plain characters after the GO token under both Neo's and Ultra's tokenizer rules. So none of those names collides today;
  the final name still gets the decision-6 check when it is chosen. [Certain for these strings]
- The Neo-only warning's Y still switches to Neo with the program kept and RUNs it. The program must fit Neo
  (≤ 30,719 bytes, ending below $8000).

## Slowdown prediction

Method: `tools/neoprofile.py` runs each benchmark on TSB Neo with VICE exec checkpoints that count without stopping.
Checkpoints sit on every entry vector target, the command dispatch, every ROM call site, every CHRGET site, every cross-region
JSR/JMP and every pointer instruction. Checkpoints in $A000–$BFFF count only while $01 bit 0 is clear: TSB's code there runs
only with the BASIC ROM out, and the same addresses with the ROM in are BASIC code. `tools/ultra38model.py` multiplies the
counts by the extra cycles of each stub and divides by Neo's measured time.

| Benchmark | Neo frames | Entries | ROM jsr | ROM jmp | Neo $01 calls | CHRGET | (zp) accesses | core↔command jsr/jmp | N | H, no copies | **H, hot helpers copied** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tsb_flow | 1357 | 16,173 | 10,406 | 17,817 | 10,009 | 23,225 | 10,536 | 3,531/1,803 | +5.7% | +6.0% | **+5.3%** |
| tsb_hires | 591 | 4,695 | 1,204 | 4,105 | 12,684 | 5,735 | 54,553 | 38,814/45,553 | +5.0% | +31.7% | **+2.9%** |
| tsb_screen | 564 | 2,409 | 0 | 1,846 | 2,923 | 1,888 | 331,686 | 9,600/80 | +30.2% | +5.8% | **+1.0%** |
| tsb_text | 577 | 4,932 | 2,246 | 4,056 | 5,253 | 7,208 | 12,280 | 1,350/750 | +3.7% | +3.1% | **+3.1%** |
| v2_goto | 1198 | 14,800 | 3,202 | 13,603 | 5,598 | 19,203 | 13,604 | 2,397/2,397 | +4.4% | +4.2% | **+3.3%** |
| v2_math | 1331 | 5,237 | 1,802 | 3,907 | 1 | 5,109 | 2,406 | 0/0 | +1.4% | +1.3% | **+1.3%** |
| v2_string | 633 | 5,895 | 1,236 | 5,263 | 1 | 6,513 | 2,502 | 0/0 | +3.3% | +2.8% | **+2.8%** |

Hot helpers copied into every command bank: the callees covering 90% of all core↔command calls over the benchmarks. There are 17, all a few bytes each: vglae, kerromaus, inca6a7, mkline, endsmb, l20pl40, l23pl40, incbasbz, bef0, sfrmevl,
sgetbytc, sgetadr, cgoto1, sgoto1, basromaus, cgoto0, a8a9bogm.

Extra cycles per event (`COST` in tools/ultra38model.py):

| Event | N | H |
|---|---|---|
| Entry from a vector | 9 | 20 |
| Jump into the BASIC ROM | 23 | 28 |
| Call into the BASIC ROM | 61 | 71 |
| Neo's basromein/basromaus call (no longer needed) | −23 | −23 |
| TSB CHRGET/CHRGOT | 20 | 0 |
| TSB pointer access (fast path only) | 10 | 0 |
| Core↔command JSR / JMP | 0 | 63 / 27 |

Against the stock C64 (the D4 question), layout H predicts v2_math +4.4%, v2_string +13.6%, v2_goto +26%. Neo is at
+3.1%, +10.5% and +22.1%.

Limits of the prediction:
- Stub cycles are hand counts of sketches, not measured code. In 2.1 the hand counts matched VICE exactly, but these
  stubs aren't written yet. [Guessing ±3 points per benchmark]
- The fast path for layout N leaves out its slow path (strings ≥ $8000), so N's figures are a lower bound. That only
  strengthens the choice of H.
- Synthetic benchmarks, PAL only. The corpus demos aren't profiled: they're interactive and timed by the jiffy clock, so
  their speed shows mostly in how smooth they look. B2 checks a few by eye and with the existing goldens.
- Disk I/O isn't modelled (it's dominated by the drive).

## Detector for Ultra-38

`tools/neodetect.py --target ultra38` (default target stays `ultra51`, so the decided Ultra-51 expectations still pass
unchanged). The rules follow from the memory map:

- N1–N4, N6 fire for literal addresses in **$8000–$BFFF**: Neo's code there is gone. $8000–$9FFF is BASIC RAM and
  $A000–$BFFF is RAM under the BASIC ROM, so `POKE $B34B` patches nothing and `SYS $A3EC` runs garbage.
- In $C000–$CFFF the data stays where Neo has it, so PEEK/POKE/WAIT there are fine. Only `SYS` into Neo's code ($C750–$C9CE,
  $CC00–$CFFF) and `POKE`/`D!POKE` into $C750–$C9CE (patching code that no longer runs there) flag. `SYS $C000` doesn't flag:
  Neo's memhook there is called only by its disk loader, and the demos SYS their own extension, LOADed to $C000.
- No N5 and no remap: the colour data and the MEM screen stay at $C000/$CC00.
- X (`POKE 56,hi`) exempts addresses from that page up to $9FFF only.
- LOAD,8,1 warning: header load address in $8000–$BFFF.

Result on the demo disk [Certain for the verdicts; `tests/detector.sh` checks them against
`tests/detector/expected_ultra38.json`, marked *proposed*]:

| | Ultra-51 (decided) | Ultra-38 (proposed) |
|---|---|---|
| Neo-only demos | 20 | **12**: TSBDEMO, TEXT-IN-GFX, GRAFIKFONTS, MAYHEM, 4FACHZOOM, SCREENS, MAP, MULTIMAP, BLOCKCOPY, NEO-BLISTER 1.03, SMON, OLD-AT |
| Ultra demos | 19 | **27**: the 19, plus FONTDEMO2, IMG VIEWER, (B)FLASH, SWITCHSCREEN, DIRSELECT, WRITEIMAGES2REU, SOUND2, EXTINSTALLER |
| LOAD,8,1 warnings | 8 files | 1 (TSB.NEO) |

The 8 newcomers run only if Ultra-38 keeps these exactly as Neo has them [Likely]:
- the jiffy counter $C516, updated by the IRQ ((B)FLASH, FONTDEMO2, SOUND2);
- $C5C7 ((B)FLASH);
- the colour data at $C000 and its use as a directory-text buffer (IMG VIEWER, WRITEIMAGES2REU: PEEK $C02C);
- the MEM screen at $CC00 (SWITCHSCREEN);
- free $C000 for loaded extensions (DIRSELECT, EXTINSTALLER).

IMG VIEWER and WRITEIMAGES2REU also need the REU next to the EasyFlash RAM at $DF00 (step 1.4 risk). The disk loader `TSB`
stays flagged (POKE $8082).

The rule tables are per target (`TARGETS` in tools/neodetect.py), so the ROM detector (task B4.4) can carry both and use the
one for the active mode. The synthetic cases in `tests/detector/cases.json` now include 9 for ultra38.

## Revised task list (proposal; the plan doc is updated from the chat)

| ID | Task | Replaces | Size |
|---|---|---|---|
| B1 | This report: benchmarks, inventory, layout, prediction, detector, tasks | — | done |
| B2.1 | **Speed spike without the port**: Neo, still in RAM at $8000, with every ROM call, entry, exit and core↔command call routed through the real Ultra-38 stubs (layout-H costs, same addresses). Measures the real stub cost on the 7 benchmarks and some demos. | 2.4 | M |
| B2.2 | Ultra-38 core: entry/exit/ROM-call/far-call stubs in $DFxx, KERNAL-off helpers and RAM vectors at $FF40+ (reuse the 2.1 core), IRQ/NMI/BRK; spike CRT + test like core21, PAL/NTSC stock + gate machines | 2.1 (extends) | M |
| B2.3 | **Gate G-B2 (go/no-go)**: measured slowdown vs D4 (reference to be decided: Neo or stock), 1-hour IRQ/NMI/RESTORE soak, flash the spike to real hardware (Fafa) | G2, 2.4, 2.5 | S |
| B3.1 | Build: tsbneo.a assembled into the banks above, thunks and hot-helper copies generated, CRT layout with free/reserved banks | 3.2, 4.1 | L |
| B3.2 | Remove the 18 code-area variables / self-modified operands; port-switch sections into helpers; ROM data reads ($A326 table, JMP ($A002)) | 4.1 | M |
| B3.3 | Vectors, KERNAL bridge, LOAD/SAVE, $C000–$CFFF kept as Neo (data + dead code copy); compatibility address map (now mostly "same as Neo") | 3.3, 4.2 | M |
| B3.4 | Overlays (MEM, EXT, HSG, MON) from flash; disk, tape, printer, REU commands (REU next to EasyFlash RAM) | 4.4, 4.5 | M |
| B4.1 | Boot, MEMSIZ $A000, start-up screen + golden; pixel check at the final gate | 6.1 (part) | S |
| B4.2 | Generic `GO` with mode table: `GO 64`, `GO NEO`; `GO TO` unaffected | 5.1 | S |
| B4.3 | Switch to Neo keeping the program (Y answer) | 5.2 | M |
| B4.4 | RUN-time and LOAD,8,1 detector in ROM, rule tables per target (ultra38 active) | 5.3 | M |
| B4.5 | All 39 demos from Ultra-38: 27 direct (goldens as on Neo), 12 after switching; command suite on Ultra-38 | 5.4 | M |
| B5 | Final CRT, real hardware (EasyProg, one more device, PAL/NTSC), memory maps (stock / Neo / Ultra-38), manual, licence review, release | 6.1, 6.2, 7.1–7.4 | M |

Moved to Ultra-51 (later goal): 2.2 (BASIC with 51,199 bytes), 2.3 (U2+ graphics under I/O), 3.1 (D3 interpreter base:
**not needed for Ultra-38**, it uses the C64's own BASIC ROM), 3.2 (interpreter port), 3.4 (PEEK/POKE/SYS conformance with
a moved interpreter), 4.3 (U2+ graphics). Decisions that change meaning under Ultra-38: decision 1 of 11 Nov (20/19 split)
becomes the Ultra-51 target and Ultra-38 gets 12/27 (proposed); decision 4 (DISPLAY with MEM) is moot because the MEM screen
stays at $CC00; decision 2's LOAD range becomes $8000–$BFFF. Decisions 3, 5 and 6, D-2.0a and D-2.0b are unchanged.

## Path to Ultra-51

Ultra-51 comes later as another mode in the same cartridge (`GO` + a new table row, banks 16–47 reserved).

**What carries over from Ultra-38** [Likely]:
- the bank build of tsbneo.a, the thunks, the hot-helper copies and the far-call machinery;
- the RAM stubs at $DFxx, the KERNAL-off helpers and the RAM vectors at $FF40+ (the 2.1 core already has both);
- the removal of self-modifying code and code-area variables;
- the port-switch helpers;
- boot, the start-up screen code (the number is computed, so it shows 51199 by itself), the generic `GO`;
- the Neo switch with the program kept;
- the detector with per-target rule tables (the `ultra51` target and its decided expectations are already in the repo);
- the overlays, the test harness, benchmarks, profiler and model (Ultra-51 needs only new cost constants);
- the CRT build.

**What stays open for Ultra-51:**
1. **TSB work variables.** Neo's $C000–$CFFF areas become BASIC memory: settings $C500/$CB00, PROC table $C400, key table
   $C650, X!/MAP areas $CA00/$CB00, colour data $C000, MEM screen $CC00. They need a new home (under I/O was the plan).
   That also costs compatibility: the 8 demos that run in Ultra-38 only because those addresses stay would be Neo-only
   again (20/19).
2. **Patched BASIC size against the 8K slot.** With BASIC memory up to $CFFF, the BASIC interpreter itself must reach
   program memory under ROM ($A000–$CFFF), so it needs a patched copy (D3: interpreter base and licensing). Every
   program-memory access in it goes through a helper; whether the patched interpreter still fits 8K with those helpers is
   unmeasured.
3. **Per-access cost, and the dual-interpreter idea.** 2.1 measured FETCH 15/16 cycles fast and 53 slow (native 5), STORE
   30/31 and 80 (native 6). Layout N above is a partial preview: only TSB's own pointer accesses, at fast-path cost, already
   give +30% on screen commands. The BASIC interpreter's own accesses would come on top. The idea to evaluate: run the
   unpatched Ultra-38 interpreter while program and variables fit below $A000, and switch to the patched one only when they
   don't. [Guessing whether the switch can be made safely mid-program: it changes where strings live.]
4. **The literal FAST/SLOW option.** A user-visible choice between the fast mode (38,911 bytes) and the large mode (51,199
   bytes). It could be a `GO` argument or a separate keyword (tokenizer check as in decision 6). Open: whether a program may
   switch while running, and what happens to its variables.

## Decisions needed

1. **Layout H** (recommended) over N.
2. **D4 reference**: slowdown measured against TSB Neo (Ultra-38 predicted ≤ +5%) or against a stock C64 (predicted up to
   +26% on GOSUB/GOTO, of which Neo already accounts for +22%).
3. **Ultra-38 detector verdicts**: 12 Neo-only / 27 Ultra (`expected_ultra38.json`, proposed). This includes the requirement that
   Ultra-38 keeps $C000–$CFFF exactly as Neo has it.
4. **Bank reservation** for Ultra-51 (16–47 proposed) and the eventual mode name (only needs the tokenizer check when chosen).

## Files

- `tools/neoinventory.py`: static inventory from the ACME report. `tests/neo_inventory.py` (in `make test`) pins the key counts.
- `tools/neoprofile.py`: event counts on Neo with non-stopping VICE checkpoints. `--stock` measures the time only.
- `tools/ultra38model.py`: cost model, layouts N and H.
- `tests/bench/*.bas`: the 7 benchmarks. `make bench` reruns profile and model (~5 min).
- `tools/neodetect.py`: `--target ultra51|ultra38`. `tests/detector/expected_ultra38.json` (proposed),
  9 new cases in `tests/detector/cases.json`, `tests/detector.sh` checks both targets.
- The 2.1 core (`additions/ultra/`) is unchanged and still tested (`tests/core21.py` in `make test`).
