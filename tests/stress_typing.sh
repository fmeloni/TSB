#!/bin/bash
# Typing determinism under host load (step 2.0 finding 6): the three sprite scenarios that failed only in parallel
# gate runs, each run N times (default 10) with -j JOBS (default 6) while every host core runs a busy loop.
#   tests/stress_typing.sh [crt] [machine]      e.g. tests/stress_typing.sh build/TSBUltra.crt pal-jiffy-stock
cd "$(dirname "$0")/.."
CRT=${1:-build/TSBneo.crt}; M=${2:-pal-stock-stock}; N=${N:-10}; J=${JOBS:-6}; LOAD=${LOAD:-$(sysctl -n hw.ncpu 2>/dev/null || nproc)}
[ -f "$CRT" ] || { echo "SKIP stress_typing: $CRT missing"; exit 0; }
IFS=- read video kernal dos <<< "$M"
pids=(); for _ in $(seq "$LOAD"); do (while :; do :; done) & pids+=($!); done
trap 'kill ${pids[@]} 2>/dev/null' EXIT
echo "stress_typing: $CRT $M, $N runs each, -j $J, $LOAD busy loops on the host"
m=(--crt "$CRT" --video $video --kernal $kernal --dos $dos -j $J --repeat $N)
python3 tools/demo_capture.py check "${m[@]}" check_detect_background check_detect_sprites; a=$?
python3 tools/demo_capture.py check "${m[@]}" --scenarios tests/commands.json --golden tests/golden/commands tsb_sprites; b=$?
[ $a = 0 ] && [ $b = 0 ] && echo "PASS stress_typing" || { echo "FAIL stress_typing"; exit 1; }
