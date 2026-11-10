#!/bin/bash
# Boot a cartridge (or "-" for none) in headless VICE, wait N IRQs (~N/60 s), dump $0000-$07FF, print the screen.
# Usage: tools/run_crt.sh <file.crt|-> <dump.bin> [irqs=400] [extra x64sc args]
# Env: X64SC (default: x64sc in PATH), VICE_DATA (folder holding C64/ and DRIVES/ ROMs)
CRT=$1; OUT=$2; N=${3:-400}; shift 3 2>/dev/null || shift $#
X64SC=${X64SC:-x64sc}; VICE_DATA=${VICE_DATA:-$HOME/vicedata}
MC=$(mktemp); OUTA=$(readlink -f "$OUT" 2>/dev/null || echo "$OUT")
printf 'break ff48\nignore 1 %s\ncommand 1 "save \\"%s\\" 0 0000 07ff ; quit"\nx\n' "$N" "$OUTA" > "$MC"
ARGS="-default -directory $VICE_DATA -silent -sounddev dummy -warp -moncommands $MC -limitcycles 200000000"
[ "$CRT" != "-" ] && ARGS="$ARGS -cartcrt $CRT"
timeout --foreground 170 "$X64SC" $ARGS "$@" < /dev/null > "$OUT.log" 2>&1
rm -f "$MC"
[ -f "$OUTA" ] || { echo "no dump produced, see $OUT.log"; exit 1; }
python3 "$(dirname "$0")/scr.py" "$OUTA"
