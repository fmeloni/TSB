#!/bin/bash
# Boot a cartridge (or "-" for none) in VICE, wait N IRQs (~N/60 s), dump $0000-$07FF, print the screen.
# Usage: tools/run_crt.sh <file.crt|-> <dump.bin> [irqs=400] [extra x64sc args]
# Env: X64SC   path to x64sc (default: x64sc in PATH, else the macOS VICE in ~/Applications)
#      VICE_DATA folder holding C64/ and DRIVES/ ROMs (default: next to that x64sc, or ~/vicedata)
CRT=$1; OUT=$2; N=${3:-400}; shift 3 2>/dev/null || shift $#
MACVICE="$HOME/Applications/VICE-3.10-SDL2-BluetoothFix"
if [ -z "$X64SC" ]; then
  if command -v x64sc >/dev/null; then X64SC=$(command -v x64sc); else X64SC="$MACVICE/bin/x64sc"; fi
fi
if [ -z "$VICE_DATA" ]; then
  if [ -d "$(dirname "$X64SC")/../share/vice/C64" ]; then VICE_DATA="$(cd "$(dirname "$X64SC")/../share/vice" && pwd)"; else VICE_DATA="$HOME/vicedata"; fi
fi
case "$OUT" in /*) OUTA=$OUT ;; *) OUTA="$PWD/$OUT" ;; esac
MC=$(mktemp)
printf 'break ff48\nignore 1 %s\ncommand 1 "save \\"%s\\" 0 0000 07ff ; quit"\nx\n' "$N" "$OUTA" > "$MC"
ARGS="-default -directory $VICE_DATA -silent -sounddev dummy -warp -moncommands $MC -limitcycles 200000000"
[ "$CRT" != "-" ] && ARGS="$ARGS -cartcrt $CRT"
rm -f "$OUTA"
# no coreutils 'timeout' on stock macOS: -limitcycles already bounds the run
if command -v timeout >/dev/null; then T="timeout --foreground 170"; else T=""; fi
$T "$X64SC" $ARGS "$@" < /dev/null > "$OUTA.log" 2>&1
rm -f "$MC"
[ -f "$OUTA" ] || { echo "no dump produced, see $OUTA.log"; exit 1; }
python3 "$(dirname "$0")/scr.py" "$OUTA" $SCRFLAGS
