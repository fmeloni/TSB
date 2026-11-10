#!/bin/bash
# G0 smoke test: TSBneo cartridge boots and reports 30719 bytes free with MEMSIZ at $8000.
D=$(dirname "$0"); CRT=${1:-$D/../build/TSBneo.crt}
OUT=$(mktemp -u).bin
R=$("$D/../tools/run_crt.sh" "$CRT" "$OUT" 400) || { echo "FAIL: emulator"; exit 1; }
echo "$R"
echo "$R" | grep -q "30719 BASIC BYTES FREE" && echo "$R" | grep -q "MEMSIZ=\$8000" && { echo "PASS boot_tsbneo"; exit 0; }
echo "FAIL boot_tsbneo"; exit 1
