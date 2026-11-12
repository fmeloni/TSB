# Phase B2 — Ultra-38 spikes (B2.1 speed, B2.2 core and flash spike) and the G-B2 checklist

Date: 2026-11-12. Decisions this builds on (Fafa, 12 Nov):
- layout H;
- Ultra-38 detector 12 Neo-only / 27 Ultra (provisional, confirm in B4.5);
- flash banks 16–47 reserved for Ultra-51;
- D4 pending: report the slowdown against TSB Neo **and** against a stock C64.

Labels: [Certain] = run or read here; [Likely] = strong inference; [Guessing] = plausible, unchecked. Everything runs in
VICE 3.10 x64sc. Nothing here has run on real hardware yet; that is the last item of the checklist.

## Result

- **G-B2 numbers, layout H as built (B2.1 speed spike, PAL; NTSC within 0.1 point):**

  | Against | Range over the 7 benchmarks | Worst case |
  |---|---|---|
  | TSB Neo | **+3.6% to +18.4%** | tsb_flow, +18.4% |
  | Stock C64 (BASIC V2 benchmarks) | arithmetic +6.8%, strings +15.1%, GOSUB/GOTO +35.5% | GOSUB/GOTO |

  Neo itself is +3.1% / +7.6% / +22.1% over the stock C64 on the same three. The results (variables, screen) are
  identical to Neo on every run [Certain].
- **So D4 decides it:**
  - With D4 measured against TSB Neo, Ultra-38 is inside the plan's 25% default everywhere.
  - Measured against a stock C64, the GOSUB/GOTO benchmark is over: Neo is already at 22.1%, and Ultra-38 adds 11 points.
  - One optimisation (O1, an IEVAL fast path in RAM) brings GOSUB/GOTO to +7.0% over Neo and +30.7% over stock (measured).
  - A second (O2, IGONE fast path) would take it to an estimated +26–28% over stock [Guessing]. Both need RAM that
    $DF0B–$DFFD no longer has. **Decision needed (D4 reference, and whether B3 includes O1/O2).**
- **B1's model was optimistic, for three reasons**, all measured here:
  1. B1 converted IRQs to cycles with the PAL video frame (19,656). The KERNAL's IRQ comes from a CIA timer, every
     16,422 cycles. So every B1 percentage is ×1.197 too low [Certain: Neo's v2_math is 1,331 IRQs and exactly
     21,856,906 cycles = 1,331 × 16,422].
  2. The real stubs cost more than the sketches:

     | Event | Real cycles | B1 sketch |
     |---|---|---|
     | Entry | 34 | 20 |
     | Exit | 47 | 28 |
     | ROM call | 110 | 71 |
     | Far call | 100 | 63 |
     | Far jump | 46 | 27 |

     They must keep A and all flags, save the bank for nested entries, and be shared stubs with an indirect target,
     because 243 bytes of RAM don't hold per-target stubs.
  3. Events that B1 didn't count: TSB's own ROM-call helper (up to 11,353 calls per benchmark), tail calls into ROM
     routines that return, the IRQ wrapper, the return trampoline for TSB functions, the command dispatch, and the
     KERNAL-off pixel helpers.

  The real costs times the event counts measured in the spike explain 83–89% of the measured extra cycles
  (hi-res: 52%, because the pixel helpers aren't in the model).
- **B2.2: the Ultra-38 core and flash spike CRT work in VICE.**
  - `build/u38_spike.crt` boots into the exact start-up screen of the 12 Nov amendment, with 38911 computed at boot.
  - It runs **all of TSB Neo's code from six flash banks** with BASIC up to $9FFF.
  - The required subset matches TSB Neo byte for byte: dispatch, PRINT AT, DO/DONE/ELSE, PROC/EXEC,
    HIRES+PLOT/LINE/TEST, PLAY from the IRQ (SID trace compared), single NMIs, and an interrupt stress run.
  - GO 64, GO NEO (Neo's code byte-identical), GO TO and GO 51 behave as decided.
  - Arrays up to $9FFF and strings in $8000–$9FFF check out.
  - [Certain, VICE] on all 8 matrix machines.
- **The spike found the porting problems B3 has to solve.** Most are solved in the generator already (list below).
  The ones still open:
  - four cross-bank jumps to routines that sometimes return;
  - NMIs during character-ROM reads;
  - TSB Neo's overlays;
  - the full command suite;
  - RAM for more helpers: $DF0B–$DFFD has 15 bytes left.
- Recorded for B4.4 (pending Fafa): a Neo-only program larger than 30,719 bytes, or ending at or above $8000, cannot
  switch to Neo. Proposed: the warning says it is too large for TSB Neo, offers no Y, and runs it in Ultra-38.

## G-B2 checklist

| Item | Status |
|---|---|
| 38,911 bytes free | **Done** [Certain, VICE]. The start-up screen shows ` 64K RAM SYSTEM 38911 BASIC BYTES FREE`, computed as MEMSIZ − TXTTAB at boot, with MEMSIZ $A000. A float array fills memory to $9EF8 (257 bytes left) and reads back without error; strings live at $9076–$9FFF. |
| Measured slowdown vs TSB Neo | **+3.6% to +18.4%** (PAL; NTSC the same within 0.1 point); with O1 +2.5% to +15.1%. Table below. |
| Measured slowdown vs stock C64 | V2 arithmetic +6.8%, strings +15.1%, GOSUB/GOTO **+35.5%** (Neo: +3.1 / +7.6 / +22.1). With O1: +5.7 / +11.4 / +30.7. |
| D4 | **Pending Fafa.** Against Neo: passes 25%. Against stock: GOSUB/GOTO fails (Neo alone uses 22 of the 25 points). |
| Stress clean | **Done on all 8 matrix machines** [Certain, VICE]. About 9,100 NMIs (every 1,734 cycles) and 5,300 IRQs (every 3,036 cycles) during PROC/EXEC, DO, HIRES+LINE+TEST, PRINT AT and strings, with the result identical to Neo's. About 95 NMIs and 65 IRQs landed inside the KERNAL-off pixel helpers, and 20 NMIs went through TSB Neo's own handler. |
| Spike CRT ready for Fafa's real-hardware test | **Ready**: `make build` produces `build/u38_spike.crt` (EasyFlash, type 32; ROML 0–3, ROMH 0–6). What to check on hardware: section "Real-hardware test". |
| Speed spike vs B1 model, per event type | Done (tables below). |
| 3 corpus demos timed by their goldens | Done: FONTDEMO2 +0.7%, FADE +13.4%, DO-TEST −0.7% (PAL). |

## B2.1 — speed spike

**What it is.** TSB Neo stays in RAM at $8000–$CFFF, but its source is rewritten (`tools/u38gen.py b21`) so every
crossing that layout H has goes through the real Ultra-38 stubs (`additions/ultra38/core38.a`):
- entries from the six BASIC vectors and IRQ/NMI/BRK/LOAD/SAVE;
- exits and tail calls into the BASIC ROM;
- ROM calls;
- calls and jumps between Neo's $8000, $A000 and $C000 regions (each counted as its own bank);
- the command dispatch table;
- TSB's own ROM-call helper;
- the KERNAL-off pixel accesses.

Every replacement has the size of what it replaces, so all 1,162 TSB Neo labels keep their addresses (checked by
`tests/u38_gen.py`). The stubs write $DE02 = $04 (cartridge stays off) instead of $07 — same cycles. The thunks
(5 KB) sit at $6000–$73DF, so MEMSIZ is $6000. All benchmarks therefore set MEMSIZ to $6000 on every system (same
string space, same garbage collection).

**Correctness.** On the command suite, 16 of 22 scenarios match Neo's goldens exactly. The other 6:
- 3 differ only in the bytes-free figure on the boot screen;
- tsb_disk and tsb_reu use $6000, where the spike keeps its thunks;
- tsb_editor's TRACE snapshot catches a line half-printed, because the spike is slower.

On the demo suite, 30 of 44 scenarios pass on the spike. The failures are the expected kind for a spike with MEMSIZ
$6000 and changed code bytes [Likely: demos that patch or SYS into Neo's code, or load to $6000+; not each checked].
Benchmark results are identical to Neo [Certain].

**Timing.** `make bench38`:
- `tools/u38bench.py` counts cycles exactly. CIA 2 timers A+B form a 32-bit counter, started at BASIC's RUN handler
  and read when the main loop is reached again.
- Events are counted with non-stopping VICE checkpoints on the stubs.
- `tools/u38stubcost.py` measured single stub paths and confirms the hand counts: entry 34, exit 47.

### Measured cycles (RUN to READY, MEMSIZ $6000 on all systems)

| Benchmark | Machine | Stock C64 | TSB Neo | B2.1 spike | Neo vs stock | **spike vs Neo** | **spike vs stock** | O1 vs Neo | O1 vs stock |
|---|---|---|---|---|---|---|---|---|---|
| tsb_flow | PAL | — | 22,293,501 | 26,395,717 | — | **+18.4%** | — | +15.1% | — |
| tsb_hires | PAL | — | 42,611,534 | 46,328,395 | — | **+8.7%** | — | +8.2% | — |
| tsb_screen | PAL | — | 9,268,717 | 9,892,905 | — | **+6.7%** | — | +5.2% | — |
| tsb_text | PAL | — | 9,472,832 | 10,728,821 | — | **+13.3%** | — | +11.1% | — |
| v2_goto | PAL | 16,116,412 | 19,679,032 | 21,837,612 | +22.1% | **+11.0%** | **+35.5%** | +7.0% | +30.7% |
| v2_math | PAL | 21,199,505 | 21,856,906 | 22,645,975 | +3.1% | **+3.6%** | **+6.8%** | +2.5% | +5.7% |
| v2_string | PAL | 9,670,252 | 10,402,625 | 11,125,721 | +7.6% | **+7.0%** | **+15.1%** | +3.5% | +11.4% |
| tsb_flow | NTSC | — | 22,472,086 | 26,599,304 | — | **+18.4%** | — | +15.0% | — |
| tsb_hires | NTSC | — | 42,976,508 | 46,684,507 | — | **+8.6%** | — | +8.1% | — |
| tsb_screen | NTSC | — | 9,343,016 | 9,968,893 | — | **+6.7%** | — | +5.2% | — |
| tsb_text | NTSC | — | 9,548,392 | 10,811,540 | — | **+13.2%** | — | +11.1% | — |
| v2_goto | NTSC | 16,250,494 | 19,836,119 | 22,005,607 | +22.1% | **+10.9%** | **+35.4%** | +7.0% | +30.6% |
| v2_math | NTSC | 21,375,412 | 22,030,948 | 22,819,519 | +3.1% | **+3.6%** | **+6.8%** | +2.5% | +5.6% |
| v2_string | NTSC | 9,750,540 | 10,486,120 | 11,211,260 | +7.5% | **+6.9%** | **+15.0%** | +3.5% | +11.3% |

[Certain] for the numbers: they are deterministic emulated cycles, and all runs gave the same results as Neo.

O1 is a variant spike (`build/u38_b21f.crt`, `tools/mkb21f.sh`). IEVAL goes to a 30-byte routine in RAM that handles
digits, variables and V2 functions without entering flash; only `$`, `%` and TSB functions go into flash. Command
suite: same 16/22 as B2.1.

### Per event type: real costs vs the B1 model

Events counted in the spike (PAL), with the extra cycles each costs over Neo (counted from the code; entry and exit
also measured):

| Event | Real extra cycles | B1 cycles | tsb_flow | tsb_hires | tsb_screen | tsb_text | v2_goto | v2_math | v2_string |
|---|---|---|---|---|---|---|---|---|---|
| entry IGONE | 34 | 20 | 4,209 | 1,031 | 244 | 1,054 | 4,803 | 1,204 | 1,252 |
| entry IEVAL | 34 | 20 | 10,608 | 3,074 | 1,602 | 3,002 | 8,800 | 2,703 | 4,011 |
| entry cold (IERROR IMAIN ICRNCH IQPLOP BRK LOAD SAVE) | 91 | — (not modelled) | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| IRQ | 100 | — (not modelled) | 1,614 | 2,828 | 609 | 660 | 1,337 | 1,386 | 684 |
| ROM call (RC, RT, RCS) | 110 | 71 | 21,609 | 12,859 | 2,521 | 6,747 | 7,201 | 1,803 | 1,237 |
| exit (RX) | 47 | 28 | 13,018 | 3,805 | 1,847 | 3,607 | 13,604 | 3,908 | 5,264 |
| far call (FC) | 100 | 63 | 0 | 1,337 | 1,160 | 450 | 0 | 0 | 0 |
| far jump (FJ) | 46 | 27 | 1,803 | 363 | 80 | 450 | 0 | 0 | 0 |
| return trampoline (ev_ret) | 53 | — (not modelled) | 1,801 | 302 | 1 | 751 | 1 | 1 | 1 |
| of the ROM calls: through TSB's pspeibe | (in the above) | — | 6,402 | 11,353 | 2,520 | 4,050 | 3,998 | 0 | 0 |
| jsr basromein/aus removed (B1 count) | −19 | −23 | 10,009 | 12,684 | 2,923 | 5,253 | 5,598 | 1 | 1 |

How the stub costs come about (code in `additions/ultra38/core38.a`):
- **Entry (34):** a 13-byte RAM stub per hot vector: save A, $01 = $36, cartridge on. Then the common block, the same
  in every bank: set the bank, restore A, jump.
- **Exit (47):** a flash thunk (php, A and the target into RAM) and a shared RAM stub: $01 = $37, cartridge off,
  restore A/P, `jmp` through the vector.
- **ROM call (110):** like an exit, plus the caller's bank pushed (a ROM routine can call back into TSB through a
  vector, which changes the bank), the way back with A and P kept, and the bank restored in the common block.
- **Far call (100) and far jump (46):** a thunk plus the common block. No RAM is needed, because the bank switch runs
  in code that is the same in every bank.

### Model check and the deviations (B1 prediction vs measurement)

| Benchmark | Measured extra cycles | Real costs × counted events | Predicted/measured | B1 prediction (×1.197 corrected) | Measured | Off by |
|---|---|---|---|---|---|---|
| tsb_flow | 4,102,216 | 3,642,416 | 0.89 | +6.3% | +18.4% | +12.1 points |
| tsb_hires | 3,716,861 | 1,941,285 | 0.52 | +3.5% | +8.7% | +5.3 points |
| tsb_screen | 624,188 | 552,161 | 0.88 | +1.2% | +6.7% | +5.5 points |
| tsb_text | 1,255,989 | 1,121,481 | 0.89 | +3.7% | +13.3% | +9.5 points |
| v2_goto | 2,158,580 | 1,921,573 | 0.89 | +3.9% | +11.0% | +7.0 points |
| v2_math | 789,069 | 653,660 | 0.83 | +1.6% | +3.6% | +2.1 points |
| v2_string | 723,096 | 631,036 | 0.87 | +3.4% | +7.0% | +3.6 points |

Everything except v2_math is off by more than 3 points. Why [Certain for the causes, Likely for the shares]:
- **tsb_flow (+12.1):** ROM calls. DIV, MOD and FRAC call the BASIC ROM 21,609 times. B1 counted 10,406 because it
  didn't see TSB's own ROM-call helper (6,402) or the tail calls into ROM routines that return (they become
  call + `rts`). Each costs 110 cycles, not 71. ROM calls alone are 2.4 M of the 4.1 M extra cycles. The return
  trampoline of TSB functions (1,801) is also new.
- **tsb_text (+9.5):** the same: 6,747 ROM calls (4,050 through TSB's helper), plus 751 function trampolines.
- **v2_goto (+7.0):** 13,603 entries and 13,604 exits at 34/47 cycles instead of 20/28, plus 3,998 ROM calls through
  TSB's helper for GOSUB/RETURN.
- **tsb_screen (+5.5):** 2,520 helper ROM calls B1 didn't count; the IRQ wrapper.
- **tsb_hires (+5.3):** KERNAL-off pixel helpers (the model leaves them out, hence 0.52) and 11,353 helper ROM calls.
- **v2_string (+3.6):** exits 47 instead of 28, and the IEVAL entry on every operand.

The remaining 11–17% that real costs × events doesn't explain is in events counted together. It is mainly the per-IRQ
cost: the IRQ path now also saves the stubs' scratch bytes, so it costs about 140 cycles rather than 100. Smaller
shares are the extra `jsr`/`rts` of tail calls and a thunk variant [Likely].

**Hot helpers.** B1 chose the helpers to copy from the benchmarks. That missed DO's search, which far-called the
7-byte `inc20` once per program byte: DO-TEST ran +94% slower. The rule is now "copy every helper called across banks
that is at most 32 bytes with what it reaches": 71 helpers, 0.9 KB per bank. DO-TEST is now −0.7%. B3.1 should keep
the size rule.

### Corpus demos timed by their goldens

From RUN until the display first equals the scenario's golden (`tools/u38demotime.py`):

| Demo | Machine | TSB Neo cycles | B2.1 spike | spike vs Neo |
|---|---|---|---|---|
| FONTDEMO2.DMO | PAL | 9,406,621 | 9,470,755 | +0.7% |
| FADE.DMO | PAL | 4,512,880 | 5,119,271 | +13.4% |
| DO-TEST.DMO | PAL | 226,898 | 225,360 | −0.7% |
| FONTDEMO2.DMO | NTSC | 9,596,158 | 9,697,026 | +1.1% |
| FADE.DMO | NTSC | 4,550,570 | 5,145,919 | +13.1% |
| DO-TEST.DMO | NTSC | 220,858 | 236,496 | +7.1% |

FONTDEMO2 waits on TSB's jiffy counter most of the time, so it hardly changes. FADE is a BASIC loop and lands near
the benchmarks. DO-TEST is short (0.2 M cycles); its NTSC figure moves with where the first IRQ falls [Likely].

### Optimisations measured or estimated (for B3)

| Option | What | Effect | RAM |
|---|---|---|---|
| O1 | IEVAL fast path in RAM (V2 operands never enter flash) | measured: −1 to −4 points vs Neo (v2_goto 11.0 → 7.0, stock 35.5 → 30.7) | ~30 bytes |
| O2 | IGONE fast path for V2 statements when no ON KEY / TRACE / DO-ELSE state is active | estimated −2 to −3 points on v2_goto and tsb_flow [Guessing] | ~40 bytes |
| O3 | Ultra versions of TSB's ROM-call helper (no port save/restore, thunk directly) | estimated −1 to −3 points on tsb_flow/hires [Guessing] | none |
| O4 | ROM calls from banks that cannot be re-entered without pushing the bank | needs analysis of which ROM routines call vectors | none |

O1 and O2 need always-visible RAM beyond $DF0B–$DFFD. Candidates: Neo's $C750–$C9CE code area (if that code moves to
flash, which the B1 detector already treats as Neo-only), $0334–$033B. **Decision with B3.**

## B2.2 — Ultra-38 core and flash spike

### Core (`additions/ultra38/core38.a`)

- **EasyFlash RAM $DF0B–$DFFD: 228 of 243 bytes.** $DF00–$DF0A is never touched.
  - Bank shadow, two scratch bytes and a shared jump vector.
  - Two hot entry stubs (IGONE, IEVAL); seven cold entries (IERROR, IMAIN, ICRNCH, IQPLOP, BRK, LOAD, SAVE) through one
    shared stub.
  - ROM-call stub and exit stub.
  - IRQ and NMI wrappers.
  - The return trampoline `ev_ret`, and the two NMI/IRQ pieces for the KERNAL-off modes.
  - KERNAL-off pixel helpers `k_rd` / `k_rmw` (read, and read-modify-write with ora/and/eor).
- **RAM under the KERNAL $FF40–$FFFF (from the 2.1 core):** RAM IRQ and NMI vectors for interrupts taken while a
  helper has the KERNAL off. An IRQ there enters the KERNAL's $FF48 by switching the KERNAL in at $FF46/$FF47, so the
  next fetch comes from ROM (the same in stock and JiffyDOS KERNALs).
- **State rule:** the cartridge is on exactly when CPU port bit 0 is clear. Every switch writes $01 first and $DE02
  second, so an interrupt between the two writes saves a port value that restores a consistent state.
- **Common block** (1.5 KB, the same bytes in every bank at $B800): the second half of the entries, far call and far
  jump, the ROM-call return, IRQ/NMI bodies, and the thunks for Neo's $C000 code.
- **Interrupts:**
  - IRQ: KERNAL → $0314 → u_irq. Saves port, bank and the stubs' scratch bytes, runs TSB's handler in its bank,
    restores, then `jmp $EA31`.
  - NMI: KERNAL $FE43 → $0318 → u_nmi → TSB Neo's handler, with a fake return frame so its `rti` comes back through
    the restore.
  - BRK: a cold entry to TSB's handler.
  - Interrupts while a KERNAL-off helper runs: RAM vectors → KERNAL → the same paths → back through `df_ramret`.

### Flash build (`tools/u38gen.py flash`, `tools/u38crt.py`)

- TSB Neo's $8000–$9FFF and $A000–$BFFF code goes into six parts, split at routine boundaries (no fall-through and no
  branch across a split; the routine at $9FF4 that crosses Neo's $A000 boundary stays whole). Each part is assembled at
  $A000 in its own ROMH bank, 1–6, followed by:
  - its thunks;
  - copies of the data tables it reads from other parts (33 copies for 51 read sites);
  - its helpers.
- Neo's $C000–$CFFF (data, tables and the code there) is copied to RAM at boot, exactly where Neo has it, and its code
  runs from RAM. Its calls into flash go through thunks in the common block, which push whatever bank is current.
- CRT bank map:

  | Bank | Contents |
  |---|---|
  | ROMH 0 | Ultimax boot (Commodore key = GO 64 path) |
  | ROML 0–2 | the v0.1 TSB Neo launcher and image (GO NEO) |
  | ROML 3 | the Ultra-38 launcher with the RAM images |
  | ROMH 1–6 | TSB |

  Banks 7–15 are free, and 16–47 are kept free for Ultra-51.
- Boot: KERNAL init, RAM parts installed, then TSB's COLD from flash with MEMSIZ $A000. COLD prints the start-up screen
  (border/background 6, text 15, rows 1 and 3 as specified, the number computed), then ends in BASIC's NEW, as the
  stock start message does.
- **GO:** TSB's statement hook sees the V2 token GO before the ROM does and looks the argument up in a mode table
  (`64`, `neo`; Ultra-51 is one more row). Anything else, `TO` included, goes to BASIC V2 unchanged.
  - GO 64: cartridge off, KERNAL reset.
  - GO NEO: 8K mode, bank 0, KERNAL reset, which starts the v0.1 Neo launcher. Both set $01 = $37 first: the KERNAL
    looks for CBM80 before it sets the port itself.

### Tests (`tests/u38_spike.py`, in `make test-u38`; `--quick` in `make test`)

All on pal-stock-stock and ntsc-stock-stock: **PASS** [Certain, VICE].

| Test | Checks |
|---|---|
| Start-up screen | rows 1/3/5 exactly, colours 6/6/15, MEMSIZ $A000; screen, colour RAM and VIC against `tests/golden/u38_boot` |
| GO | GO 64 → stock C64, 38911, stock vectors; GO NEO → TSB Neo, 30719, "tuned", Neo's code $8000–$BFFF identical to `build/tsbneo_ref.bin`; `10 GO TO 30` jumps; `GO 51` → ?SYNTAX ERROR |
| Subset, byte-identical to TSB Neo (`tests/u38.json`, goldens captured on Neo in `tests/golden/u38`) | print_at (dispatch, PRINT AT, strings), do_else (IF/ELSE, DO/DONE taken and skipped, nested), proc_exec (PROC/EXEC/END PROC nested, CALL), hires_plot (HIRES, LINE, PLOT, TEST; bitmap compared), play_irq (MUSIC + PLAY from TSB's IRQ; SID trace compared), nmi_once (20 NMIs through TSB Neo's handler), stress |
| Interrupt stress (as 2.1 T5) | CIA 1 IRQ every 3,036 cycles, CIA 2 NMI every 1,734 cycles, three rounds of PROC/EXEC, DO, HIRES+LINE+TEST, PRINT AT, strings; result identical to Neo; ~9,100 NMIs, ~5,300 IRQs, ~95 NMIs and ~65 IRQs inside KERNAL-off helpers |
| Memory (`tests/u38_mem.json`, self-checking) | float array to $9EF8 written and read back, PRINT AT meanwhile; 151 strings built with DUP, three garbage collections, checked; string area from $9076 |
| Static (`tests/u38_gen.py`, in `make test`) | B2.1 labels unchanged, RAM core size, banks below the common block |

The stress program's NMIs go to a counting handler. TSB Neo's own handler switches CIA 2's interrupts off after the
first NMI, so 20 single NMIs (nmi_once) test that path instead. Neo can't take NMIs while its KERNAL is off: its RAM NMI
vector doesn't switch the KERNAL off again. So Neo's golden for the stress program is the same program without NMIs
(it enables them only when MEMSIZ is $A000). Ultra-38 takes them in every state.

**Beyond the subset (information).** On Neo's full command suite:
- 11 of 22 scenarios differ only in colour RAM and VIC registers: v2_math, v2_flow, v2_io, tsb_structures,
  tsb_errors, tsb_screen, tsb_sprites, tsb_sound, tsb_input, tsb_disk, merge_nodev. The programs don't set
  colours, and Ultra-38 starts 6/6/15 in upper case; screen text and variables match.
- tsb_hires and tsb_multi match until their final screen.
- tsb_onkey, tsb_misc and tsb_overlays differ.
- tsb_mem never ends; tsb_functions, tsb_reu, tsb_editor, tsb_printer and tsb_session time out.

That is B3.

### Porting problems found (solved in the generator unless marked open)

Each of these crashed or misbehaved in a spike first; `tools/trace38.py` / `trace38f.py` found them [Certain].

1. **Jumps into the BASIC ROM come in two kinds.**
   - True exits (NEWSTT, READY, errors, LIST loop, warm start) take the exit stub.
   - Tail calls into routines that return (PUTNEW, FIN, CHKCLS, CRUNCH, …) become call + `rts`. Otherwise the routine
     returns into TSB code in BASIC state.
   - IEVAL's TSB-function paths and ICRNCH get a return trampoline (`ev_ret`).
   - The V2 path of IEVAL must not: BASIC's EVAL pulls its caller's return address off the stack for unary minus and
     NOT.
2. **BASIC routines that reset the stack** (CLR, NEW, `$E422`) keep only one return address. A dedicated thunk puts
   the caller's return and bank at $01FB–$01FD, where the stub pops them after CLR.
3. BASIC's RAM init `$E3BF` writes $01FC/$01FD, so TSB starts with SP $F7.
4. `$B2EA` (PLACE on arrays) takes arguments its caller pushed: plain exit. **Open:** its `rts` may return into TSB
   code in BASIC state; it's outside the subset.
5. **Cross-bank jumps.** A jump to a routine that returns needs a far call + `rts`: 30 such sites, decided by static
   analysis of where each target ends. **Open:** four targets end both ways (mve3, onkey1, sintprt0, useready); they
   need a hand decision in B3.
6. Neo's `basromein`/`basromaus` leave the port value in A, and the dispatch saves it (portspei, restored by prestor).
   The replacement loads $36.
7. **Code that runs with the KERNAL off** cannot run from flash ($A000 turns into RAM), and with $34 not even the
   $DFxx stubs are visible. kerromaus is gone; pixel reads and writes go through `k_rd`/`k_rmw`.
8. **Character-ROM spans** (CHAR): the char ROM is switched in only around each read, with IRQs off. **Open:** an NMI
   during such a read (RESTORE) finds $0318's stub invisible. That applies to CHAR, TEXT and MEM's charset copy.
9. **BASIC ROM data** ($A326 error table, ROM message text) and `newopen` (called in BASIC state through TSB's
   ROM-call table) are read or run through tiny RAM helpers in Neo's unused gap $C3E8–$C3FF (22 of 24 bytes).
   TSB's own error messages are copied to $0200 before the ROM prints them.
10. **Data tables** read from another bank are copied into the reading bank: 33 copies for 51 read sites.
11. **Self-modifying code and code-area variables:** `getpktf` (MOB), `vecrenum`/`vecplace` (MEM/NRM), `toul3` (USE),
    the SCRSV/SCRLD operands. **Open** (B3.2), outside the subset.
12. **TSB Neo's overlays** (TSB.MEM, TSB.EXT, TSB.HSG) call Neo's code at fixed addresses. **Open** (B3.4).
13. **RAM:** $DF0B–$DFFD has 15 bytes left. B3 needs more always-visible RAM for helpers (O1/O2, char ROM). **Open.**
14. **Flash spike speed:** it has no helper copies yet (one far call per bitmap byte in HIRES's clear, per pixel in
    LINE). B3.1 adds the copies as measured in B2.1.

### Matrix

`tests/matrix.sh spike38` runs `tests/u38_spike.py` on all 8 machines (`gate` now includes it):

**PASS on all 8 machines** [Certain, VICE]: pal/ntsc × KERNAL stock/JiffyDOS 6.01 × 1541 DOS stock/JiffyDOS.
Each run covers the start-up screen, GO, the 7 subset scenarios, the memory tests and the interrupt counts.
Under the JiffyDOS KERNAL, GO 64 leaves JiffyDOS's own BASIC vectors; the test checks that none points at the
Ultra-38 stubs.

## Real-hardware test (for Fafa)

`make build` → `build/u38_spike.crt`. Flash it with EasyProg to an EasyFlash / EasyFlash 3, or load it on a Kung Fu
Flash or Ultimate. Expected:
1. Power on → the Ultra-38 start-up screen (blue, light grey text, 38911). Commodore key held at power-on → stock C64.
2. The programs in `tests/u38/*.bas` (print_at, do_else, proc_exec, hires_plot, play_irq) typed in give the same screen
   as on TSB Neo. The stress program also exercises the NMI timer; nmi_once uses TSB Neo's NMI handler.
3. `GO 64` → stock C64; `GO NEO` → TSB Neo 2.60.228 (30719); reset afterwards → Ultra-38 again.
4. RUN/STOP+RESTORE in Ultra-38 → TSB's warm start. Untested in VICE beyond single NMIs [Guessing].
5. Things outside the subset may fail. That is expected for the spike.

The mapping ($DE02 $07 with $01 $36: RAM at $8000, ROMH at $A000) is the standard 16K-cartridge PLA mode [Likely on
hardware; task 2.5].

## Revised task list notes

- B2.3 (gate G-B2): this report's checklist, plus Fafa's hardware test and the D4 decision.
- B3.1 should reuse the generator: banks, thunks, the copy-by-size rule, return analysis and data-table copies.
- Open items 4, 5, 8, 11, 12 and 13 above go into B3.1–B3.4.
- O1/O2 are the levers if D4 is measured against a stock C64.
- B4.4: the "too large for TSB Neo" warning above.

## Files

- `additions/ultra38/core38.a` (RAM core, thunk macros, common block), `ef_boot38.a`, `u38_launcher.a`, `b21_launcher.a`.
- `tools/u38gen.py` (b21 / flash / report), `u38crt.py`, `u38bench.py`, `u38demotime.py`, `u38compare.py`,
  `u38stubcost.py`, `trace38.py`, `trace38f.py`, `mkb21f.sh`.
- `tests/u38_spike.py`, `tests/u38_gen.py`, `tests/u38/*.bas`, `tests/u38.json`, `tests/u38_mem.json`, goldens in
  `tests/golden/u38`, `tests/golden/u38_mem` and `tests/golden/u38_boot`.
- Makefile: `build` makes `build/u38_b21.crt` and `build/u38_spike.crt`; `make test` adds the static check and the
  quick spike test (PAL/NTSC); `make test-u38` (full, PAL/NTSC); `make bench38` (timings and tables).
  `tests/matrix.sh spike38`.
- B1 erratum: `reports/B1-ultra38-design.md` now notes the ×1.197 IRQ-period correction.
