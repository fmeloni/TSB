#!/bin/bash
# Boot a cartridge (or "-" for none) in VICE, wait N IRQs (~N/60 s), dump $0000-$07FF, print the screen.
# Usage: tools/run_crt.sh <file.crt|-> <dump.bin> [irqs=400] [extra x64sc args]
# Env: X64SC   path to x64sc (default: x64sc in PATH, else the macOS VICE in ~/Applications)
#      VICE_DATA folder holding C64/ and DRIVES/ ROMs (default: next to that x64sc, or ~/vicedata)
#      PNG     optional path for a screenshot of the VIC-II display
# Drives VICE through its binary monitor (tools/vicemon.py). The text monitor's 'quit' from
# -moncommands does not close the macOS SDL build, which made the old approach hang.
CRT=$1; OUT=$2; N=${3:-400}; shift 3 2>/dev/null || shift $#
case "$OUT" in /*) OUTA=$OUT ;; *) OUTA="$PWD/$OUT" ;; esac
rm -f "$OUTA"
python3 "$(dirname "$0")/vicemon.py" run "$CRT" "$OUTA" "$N" ${PNG:+--png "$PNG"} -- "$@" \
  || { echo "emulator run failed, see $OUTA.log"; exit 1; }
[ -f "$OUTA" ] || { echo "no dump produced, see $OUTA.log"; exit 1; }
python3 "$(dirname "$0")/scr.py" "$OUTA" $SCRFLAGS
