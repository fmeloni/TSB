# TSB Ultra build and test entry points.
# Needs: acme (and x64sc + C64 ROMs for tests). See tools/setup-linux.sh.
ACME ?= acme
BUILD := build

.PHONY: all build test test-demos test-commands bench bench38 test-u38 clean
all: build

build: $(BUILD)/tsbneo_disk.prg $(BUILD)/tsbneo_cart.bin $(BUILD)/TSBUltra.crt $(BUILD)/spike21.crt $(BUILD)/u38_b21.crt \
       $(BUILD)/u38_spike.crt

$(BUILD)/tsbneo_disk.prg: TSBneo/tsbneo.a TSBneo/memhook.inc TSBneo/MD_memhook.inc
	@mkdir -p $(BUILD)
	cd TSBneo && $(ACME) -f cbm -o ../$@ -l ../$(BUILD)/tsbneo_disk.lbl tsbneo.a

$(BUILD)/tsbneo_cart.bin: TSBneo/tsbneo.a TSBneo/memhook.inc TSBneo/MD_memhook.inc
	@mkdir -p $(BUILD)/cartsrc
	sed 's/cartridge = 0/cartridge = 1/' TSBneo/tsbneo.a > $(BUILD)/cartsrc/tsbneo.a
	cp TSBneo/*.inc $(BUILD)/cartsrc/
	cd $(BUILD)/cartsrc && $(ACME) -f plain -o ../tsbneo_cart.bin -l ../tsbneo_cart.lbl tsbneo.a

# TSB Neo exactly as in the released CRT: the disk build with the key-table padding $c657-$c74f as $00
# (the source pads with $ea). tests/ef_tsbultra.sh checks it against build/TSBneo.crt when that is present.
$(BUILD)/tsbneo_ref.bin: $(BUILD)/tsbneo_disk.prg
	python3 -c "import sys; b=bytearray(open(sys.argv[1],'rb').read()[2:]); b[0x4657:0x4750]=bytes(0 if c==0xea else c for c in b[0x4657:0x4750]); open(sys.argv[2],'wb').write(b)" $< $@

# TSB Ultra v0.1 (task 1.4): EasyFlash CRT that starts TSB Neo; Commodore key at reset = GO 64 path.
$(BUILD)/TSBUltra.crt: $(BUILD)/tsbneo_ref.bin additions/easyflash/ef_launcher.a additions/easyflash/ef_boot.a tools/mkcrt.py
	cd additions/easyflash && $(ACME) -f plain -o ../../$(BUILD)/ef_roml.bin -l ../../$(BUILD)/ef_roml.lbl ef_launcher.a
	cd additions/easyflash && $(ACME) -f plain -o ../../$(BUILD)/ef_romh0.bin -l ../../$(BUILD)/ef_romh0.lbl ef_boot.a
	python3 tools/mkcrt.py easyflash $@ "TSB ULTRA 0.1" $(BUILD)/ef_roml.bin $(BUILD)/ef_romh0.bin

# Task 2.1: spike CRT for the bank-switching core (additions/ultra/core.a); tests/core21.py runs it.
$(BUILD)/spike21.crt: additions/ultra/spike21.a additions/ultra/core.a tools/mkcrt.py
	@mkdir -p $(BUILD)
	cd additions/ultra && $(ACME) --initmem 255 -f plain -o ../../$(BUILD)/spike21.bin -l ../../$(BUILD)/spike21.lbl spike21.a
	python3 tools/mkcrt.py easyflash16 $@ "TSB ULTRA CORE SPIKE 2.1" $(BUILD)/spike21.bin

# Phase B2.1: speed spike. TSB Neo in RAM with every crossing routed through the Ultra-38 stubs (tools/u38gen.py).
U38GEN := tools/u38gen.py tools/neoinventory.py tools/neoprofile.py additions/ultra38/core38.a TSBneo/tsbneo.a
$(BUILD)/u38/b21/img.bin: $(U38GEN)
	python3 tools/u38gen.py b21 $(BUILD)/u38/b21 > /dev/null
	cd $(BUILD)/u38/b21 && $(ACME) -f plain -o img.bin -l img.lbl -r img.rep u38_b21.a
$(BUILD)/u38_b21.crt: $(BUILD)/u38/b21/img.bin additions/ultra38/b21_launcher.a $(BUILD)/TSBUltra.crt tools/mkcrt.py
	cd additions/ultra38 && $(ACME) -f plain -DU38_INSTALL_ADDR=$$(sed -n 's/^[[:space:]]*u38_install[[:space:]]*=[[:space:]]*\$$\([0-9a-f]*\).*/0x\1/p' ../../$(BUILD)/u38/b21/img.lbl) \
	  -o ../../$(BUILD)/u38/b21_l0.bin b21_launcher.a
	cat $(BUILD)/u38/b21_l0.bin $(BUILD)/u38/b21/img.bin > $(BUILD)/u38/b21_roml.bin
	python3 tools/mkcrt.py easyflash $@ "TSB ULTRA-38 SPIKE B2.1" $(BUILD)/u38/b21_roml.bin $(BUILD)/ef_romh0.bin

# Phase B2.2: Ultra-38 flash spike. TSB Neo's code from six ROMH banks, $C000-$CFFF as in TSB Neo, MEMSIZ $A000,
# start-up screen, GO 64 / GO NEO (ROML banks 0-2 hold the v0.1 TSB Neo launcher and image).
$(BUILD)/u38/fl/img.bin: $(U38GEN)
	python3 tools/u38gen.py flash $(BUILD)/u38/fl > /dev/null
	cd $(BUILD)/u38/fl && $(ACME) -f plain -o img.bin -l img.lbl -r img.rep u38_flash.a
$(BUILD)/u38_spike.crt: $(BUILD)/u38/fl/img.bin additions/ultra38/u38_launcher.a additions/ultra38/ef_boot38.a \
                        $(BUILD)/TSBUltra.crt tools/u38crt.py tools/mkcrt.py
	python3 tools/u38crt.py $(BUILD)/u38/fl $@

# TSB_CRT: the released TSBneo Magic Desk CRT (not in git); copy it to build/TSBneo.crt or pass TSB_CRT=...
TSB_CRT ?= $(BUILD)/TSBneo.crt
test: build
	tests/boot_tsbneo.sh $(TSB_CRT)
	python3 tests/ef_tsbultra.py
	python3 tests/core21.py --video pal
	python3 tests/core21.py --video ntsc
	tests/detector.sh
	python3 tests/crunch_corpus.py
	python3 tests/no_rom_in_goldens.py
	python3 tests/corpus_fixed.py
	python3 tests/neo_inventory.py
	python3 tests/u38_gen.py
	python3 tests/u38_spike.py --quick --video pal
	python3 tests/u38_spike.py --quick --video ntsc

# Phase B2.2: the full Ultra-38 flash spike tests (start-up screen, GO, subset scenarios byte-identical to TSB Neo,
# interrupt stress, memory to $9FFF, strings in $8000-$9FFF) on PAL and NTSC, ~8 min. All 8 machines:
# tests/matrix.sh spike38.
test-u38: build
	python3 tests/u38_spike.py --video pal
	python3 tests/u38_spike.py --video ntsc

# Demo baseline (task 1.3): all corpus programs against tests/golden/, several minutes.
test-demos: build
	tests/demos_tsbneo.sh $(TSB_CRT)

# Command suite (task 1.2): every TSB Neo keyword + BASIC V2 against tests/golden/commands/, about 1 min.
test-commands: build
	tests/commands_tsbneo.sh $(TSB_CRT)

# Phase B1: count Ultra-38 events on TSB Neo for tests/bench/*.bas (one VICE per program, ~5 min) and predict the
# slowdown of both layouts (reports/B1-ultra38-design.md).
bench: build
	mkdir -p $(BUILD)/b1/profile
	for f in tests/bench/*.bas; do python3 tools/neoprofile.py --crt $(TSB_CRT) --out $(BUILD)/b1/profile/n_$$(basename $$f .bas).json $$f & done; wait
	python3 tools/neoprofile.py --stock --out $(BUILD)/b1/profile/stock.json tests/bench/v2_*.bas
	python3 tools/ultra38model.py $(BUILD)/b1/profile/n_*.json --md

# Phase B2.1: cycle-exact timing of tests/bench/*.bas on TSB Neo, the B2.1 speed spike, its IEVAL fast-path variant
# O1 (build/u38_b21f.crt) and a stock C64, PAL and NTSC; three corpus demos timed by their goldens; prints the tables
# of reports/B2-spike.md (~15 min).
bench38: build
	sh tools/mkb21f.sh
	mkdir -p $(BUILD)/u38/bench
	for v in pal ntsc; do for f in tests/bench/*.bas; do b=$$(basename $$f .bas); \
	  python3 tools/u38bench.py --video $$v --crt $(TSB_CRT) --out $(BUILD)/u38/bench/neo_$${v}_$$b.json $$f > /dev/null & \
	  python3 tools/u38bench.py --video $$v --crt $(BUILD)/u38_b21.crt --events $(BUILD)/u38/b21/img.lbl \
	    --out $(BUILD)/u38/bench/b21_$${v}_$$b.json $$f > /dev/null & \
	  python3 tools/u38bench.py --video $$v --crt $(BUILD)/u38_b21f.crt --out $(BUILD)/u38/bench/b21f_$${v}_$$b.json $$f > /dev/null & \
	  done; wait; for f in tests/bench/v2_*.bas; do b=$$(basename $$f .bas); \
	  python3 tools/u38bench.py --video $$v --stock --out $(BUILD)/u38/bench/stock_$${v}_$$b.json $$f > /dev/null & done; wait; \
	  python3 tools/u38demotime.py --video $$v --crt $(TSB_CRT) --out $(BUILD)/u38/bench/demo_neo_$$v.json fontdemo2_dmo fade_dmo do_test_dmo > /dev/null & \
	  python3 tools/u38demotime.py --video $$v --crt $(BUILD)/u38_b21.crt --out $(BUILD)/u38/bench/demo_b21_$$v.json fontdemo2_dmo fade_dmo do_test_dmo > /dev/null & \
	  wait; done
	python3 tools/u38compare.py

clean:
	rm -rf $(BUILD)
