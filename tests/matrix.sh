#!/bin/bash
# Machine test matrix (decision of 11 Nov): PAL/NTSC x KERNAL (stock/JiffyDOS 6.01) x 1541 DOS ROM (stock/JiffyDOS).
#   tests/matrix.sh change [crt]  every change: full demo + command suites on pal-stock-stock and ntsc-stock-stock,
#                                 the disk-heavy subset on the other 6 machines        (~25 min)
#   tests/matrix.sh gate [crt]    before each gate: full suites on all 8 machines    (~60 min)
#   tests/matrix.sh disk [crt]    the disk-heavy subset on all 8 machines
#   tests/matrix.sh oldntsc [crt] optional: full suites on the 4 oldntsc machines (VICE -model oldntsc, VIC-II
#                                 6567R56A). Not part of change/gate until Fafa says whether his NTSC C64 has that chip.
#   MACHINES="m1 m2 ..." tests/matrix.sh gate [crt]   any list of machines, e.g. oldntsc-stock-stock
# Every mode also runs the task 2.1 core spike (tests/core21.py, build/spike21.crt; CRT-independent) on each machine
# it runs a full suite on: change = pal/ntsc-stock-stock, gate = all 8.
# crt defaults to build/TSBneo.crt. Logs: build/matrix/<crt name>/<machine>.<suite>.log, summary at the end.
# The goldens are pal-stock-stock; other machines map JiffyDOS identity text back (tools/demo_capture.py
# MACHINE_TEXT) and report accepted differences as KNOWN (scenario field "known").
# JiffyDOS images: corpus/roms/ (commercial, git-ignored); without them the jiffy machines are SKIPped.
# Drives: VICE true-drive 1541 for the real 1541 and the Pi1541. SD2IEC cannot be emulated (real hardware only).
cd "$(dirname "$0")/.."
MODE=${1:-change}; CRT=${2:-build/TSBneo.crt}; J=${JOBS:-6}
[ -f "$CRT" ] || { echo "SKIP matrix: $CRT missing"; exit 0; }
[ -f corpus/tsbneo_260228.d64 ] || { echo "SKIP matrix: corpus/tsbneo_260228.d64 missing"; exit 0; }
# disk-heavy subset: LOAD/SAVE/VERIFY, DIR, DISK, file I/O, SHOW DRIVES, programs that load data or extensions
DISK_CMDS="v2_io tsb_disk tsb_session tsb_overlays tsb_misc"
DISK_DEMOS="show_drives dirselect_dmo img_viewer_koala writeimages2reu neoblister extinstaller mayhem_dmo"
OLDNTSC="oldntsc-stock-stock oldntsc-jiffy-stock oldntsc-stock-jiffy oldntsc-jiffy-jiffy"
ALL=${MACHINES:-"pal-stock-stock ntsc-stock-stock pal-jiffy-stock ntsc-jiffy-stock pal-stock-jiffy ntsc-stock-jiffy pal-jiffy-jiffy ntsc-jiffy-jiffy"}
LOGDIR=build/matrix/$(basename "$CRT" .crt); mkdir -p "$LOGDIR"
fails=0; summary=""

run() {  # run <machine> <suite: demos|commands> [ids...]
  local m=$1 suite=$2; shift 2
  local video=${m%%-*} rest=${m#*-}   # e.g. oldntsc-jiffy-stock
  local kernal=${rest%-*} dos=${rest#*-}
  if [[ $m == *jiffy* ]] && { [ ! -f "${JIFFY_KERNAL:-corpus/roms/JiffyDOS_C64/JiffyDOS_C64_6.01.bin}" ] ||
                               [ ! -f "${JIFFY_DOS:-corpus/roms/JiffyDOS_1541/JiffyDOS_1541-II_6.00.bin}" ]; }; then
    summary+=$(printf "\n%-18s %-9s SKIP (JiffyDOS ROMs missing)" "$m" "$suite"); return
  fi
  local sc=() log=$LOGDIR/$m.$suite${1:+-subset}.log
  [ $suite = commands ] && sc=(--scenarios tests/commands.json --golden tests/golden/commands)
  python3 tools/demo_capture.py check --crt "$CRT" "${sc[@]}" -j $J --video $video --kernal $kernal --dos $dos "$@" > "$log" 2>&1
  local rc=$? n=$(grep -cE '^(PASS|FAIL|ERROR|KNOWN) ' "$log") p=$(grep -c '^PASS ' "$log") k=$(grep -c '^KNOWN ' "$log")
  summary+=$(printf "\n%-18s %-9s %s  %d/%d pass%s" "$m" "$suite${1:+ (subset)}" "$([ $rc = 0 ] && echo PASS || echo FAIL)" \
             $p $n "$([ $k -gt 0 ] && echo ", $k known")")
  [ $rc = 0 ] || { fails=$((fails + 1)); grep -E '^(FAIL|ERROR) ' "$log" | sed "s/^/    $m: /"; }
}

spike() {  # spike <machine>: tests/core21.py
  local m=$1 video=${1%%-*} rest=${1#*-}
  local kernal=${rest%-*} dos=${rest#*-} log=$LOGDIR/$1.core21.log
  if [[ $m == *jiffy* ]] && [ ! -f "${JIFFY_KERNAL:-corpus/roms/JiffyDOS_C64/JiffyDOS_C64_6.01.bin}" ]; then return; fi
  python3 tests/core21.py --video $video --kernal $kernal --dos $dos > "$log" 2>&1; local rc=$?
  summary+=$(printf "\n%-18s %-9s %s" "$m" core21 "$(tail -1 "$log")")
  [ $rc = 0 ] || { fails=$((fails + 1)); grep FAIL "$log" | sed "s/^/    $m: /"; }
}

case $MODE in
  change) for m in pal-stock-stock ntsc-stock-stock; do run $m demos; run $m commands; spike $m; done
          for m in $ALL; do case $m in pal-stock-stock|ntsc-stock-stock) continue;; esac
            run $m demos $DISK_DEMOS; run $m commands $DISK_CMDS; done ;;
  gate)   for m in $ALL; do run $m demos; run $m commands; spike $m; done ;;
  disk)   for m in $ALL; do run $m demos $DISK_DEMOS; run $m commands $DISK_CMDS; done ;;
  oldntsc) for m in $OLDNTSC; do run $m demos; run $m commands; spike $m; done ;;
  *) echo "usage: [MACHINES=...] tests/matrix.sh change|gate|disk|oldntsc [crt]"; exit 2 ;;
esac
echo "matrix $MODE on $CRT:$summary"
[ $fails = 0 ] && echo "PASS matrix_$MODE" || { echo "FAIL matrix_$MODE ($fails runs)"; exit 1; }
