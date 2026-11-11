#!/bin/sh
# Command suite (plan task 1.2): every TSB Neo keyword (117 of 121; see reports/1.2-command-suite.md) and all
# 76 BASIC V2 tokens, against tests/golden/commands/. Needs the TSB Neo CRT; the overlay test needs the corpus D64.
set -e
cd "$(dirname "$0")/.."
CRT=${1:-build/TSBneo.crt}
[ -f "$CRT" ] || { echo "SKIP commands_tsbneo: $CRT missing"; exit 0; }
python3 tools/demo_capture.py check --crt "$CRT" --scenarios tests/commands.json --golden tests/golden/commands -j ${JOBS:-6} \
  > build/commands.log 2>&1 && ok=1 || ok=0
cat build/commands.log
python3 tools/cmd_coverage.py
[ $ok = 1 ] && echo "PASS commands_tsbneo" || { echo "FAIL commands_tsbneo"; exit 1; }
