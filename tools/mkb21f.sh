#!/bin/sh
# Phase B2.1 option O1 (IEVAL fast path in RAM): build/u38_b21f.crt, the B2.1 speed spike assembled with
# U38_FASTEVAL. Used by make bench38 (reports/B2-spike.md). Needs build/TSBUltra.crt (make build) for ef_romh0.bin.
set -e
cd "$(dirname "$0")/.."
python3 tools/u38gen.py b21 build/u38/b21f > /dev/null
(cd build/u38/b21f && sed 's/^	!cpu 6510/	!cpu 6510\
	U38_FASTEVAL = 1/' u38_b21.a > u38_b21f.a && ${ACME:-acme} -f plain -o img.bin -l img.lbl -r img.rep u38_b21f.a)
A=$(sed -n 's/^[[:space:]]*u38_install[[:space:]]*=[[:space:]]*\$\([0-9a-f]*\).*/0x\1/p' build/u38/b21f/img.lbl)
(cd additions/ultra38 && ${ACME:-acme} -f plain -DU38_INSTALL_ADDR=$A -o ../../build/u38/b21f_l0.bin b21_launcher.a)
cat build/u38/b21f_l0.bin build/u38/b21f/img.bin > build/u38/b21f_roml.bin
python3 tools/mkcrt.py easyflash build/u38_b21f.crt "TSB U38 SPIKE B2.1 O1" build/u38/b21f_roml.bin build/ef_romh0.bin
