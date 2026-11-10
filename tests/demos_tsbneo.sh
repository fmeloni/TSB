#!/bin/bash
# Task 1.3 demo baseline: every program on corpus/tsbneo_260228.d64 reaches its checkpoints and matches
# tests/golden/ (captured on TSB Neo 2.60.228). Takes several minutes. Usage: tests/demos_tsbneo.sh [crt] [ids...]
D=$(dirname "$0"); CRT=${1:-$D/../build/TSBneo.crt}; shift
[ -f "$D/../corpus/tsbneo_260228.d64" ] || { echo "SKIP demos: corpus/tsbneo_260228.d64 missing"; exit 0; }
python3 "$D/../tools/demo_capture.py" check --crt "$CRT" -j "${JOBS:-6}" "$@" && echo "PASS demos_tsbneo" && exit 0
echo "FAIL demos_tsbneo"; exit 1
