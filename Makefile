# TSB Ultra build and test entry points.
# Needs: acme (and x64sc + C64 ROMs for tests). See tools/setup-linux.sh.
ACME ?= acme
BUILD := build

.PHONY: all build test test-demos clean
all: build

build: $(BUILD)/tsbneo_disk.prg $(BUILD)/tsbneo_cart.bin

$(BUILD)/tsbneo_disk.prg: TSBneo/tsbneo.a TSBneo/memhook.inc TSBneo/MD_memhook.inc
	@mkdir -p $(BUILD)
	cd TSBneo && $(ACME) -f cbm -o ../$@ -l ../$(BUILD)/tsbneo_disk.lbl tsbneo.a

$(BUILD)/tsbneo_cart.bin: TSBneo/tsbneo.a TSBneo/memhook.inc TSBneo/MD_memhook.inc
	@mkdir -p $(BUILD)/cartsrc
	sed 's/cartridge = 0/cartridge = 1/' TSBneo/tsbneo.a > $(BUILD)/cartsrc/tsbneo.a
	cp TSBneo/*.inc $(BUILD)/cartsrc/
	cd $(BUILD)/cartsrc && $(ACME) -f plain -o ../tsbneo_cart.bin -l ../tsbneo_cart.lbl tsbneo.a

# TSB_CRT: the released TSBneo Magic Desk CRT (not in git); copy it to build/TSBneo.crt or pass TSB_CRT=...
TSB_CRT ?= $(BUILD)/TSBneo.crt
test: build
	tests/boot_tsbneo.sh $(TSB_CRT)

# Demo baseline (task 1.3): all corpus programs against tests/golden/, several minutes.
test-demos: build
	tests/demos_tsbneo.sh $(TSB_CRT)

clean:
	rm -rf $(BUILD)
