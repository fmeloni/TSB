#!/bin/bash
# Load and RUN one program from a D64 under a cartridge, capture the screen after N IRQs.
# Usage: tools/run_demo.sh <file.crt> <disk.d64> <program-name> <dump.bin> [irqs=900]
# Program name is typed via the keyboard buffer, so give it in lower case (shows as upper case on the C64).
D=$(dirname "$0")
exec "$D/run_crt.sh" "$1" "$4" "${5:-900}" -drive8type 1541 -drive8truedrive -8 "$2" -keybuf "load\"$3\",8
run
"
