# TSB Ultra build and test entry points.
# Needs: acme (and x64sc + C64 ROMs for tests). See tools/setup-linux.sh.
ACME ?= acme
BUILD := build

.PHONY: all build test test-demos test-commands bench clean
all: build

build: $(BUILD)/tsbneo_disk.prg $(BUILD)/tsbneo_cart.bin $(BUILD)/TSBUltra.crt $(BUILD)/spike21.crt

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

clean:
	rm -rf $(BUILD)
