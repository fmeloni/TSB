#!/bin/sh
# Neo-only detector (plan task 1.3): synthetic cases + the verdict for every program on the demo disk.
set -e
cd "$(dirname "$0")/.."
python3 tests/detector/run_cases.py > build/detector_cases.log || { cat build/detector_cases.log; echo "FAIL detector cases"; exit 1; }
D64=${D64:-corpus/tsbneo_260228.d64}
if [ ! -f "$D64" ]; then echo "PASS detector cases ($(grep -c '^ok' build/detector_cases.log)); SKIP corpus check: $D64 missing"; exit 0; fi
python3 tools/neodetect.py "$D64" --check tests/detector/expected.json > build/detector_corpus.log || { cat build/detector_corpus.log; echo "FAIL detector corpus"; exit 1; }
echo "PASS detector ($(grep -c '^ok' build/detector_cases.log) cases; corpus: $(tail -1 build/detector_corpus.log))"
