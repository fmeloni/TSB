#!/bin/bash
# Builds the TSB Ultra toolchain on a Linux box: ACME, xa65, flex, headless VICE x64sc.
# Usage: tools/setup-linux.sh [prefix]   (default prefix: $HOME/tsbtools)
# C64 ROMs are not included: point VICE_DATA at a folder with C64/ and DRIVES/ ROM files
# (e.g. copied from a VICE install's share/vice).
set -e
P=${1:-$HOME/tsbtools}; mkdir -p "$P/src" "$P/bin"; cd "$P/src"
export PATH="$P/bin:$PATH"
[ -x "$P/bin/acme" ] || { git clone -q --depth 1 https://github.com/meonwax/acme.git acme && make -s -C acme/src && cp acme/src/acme "$P/bin/"; }
[ -x "$P/bin/xa" ]   || { git clone -q --depth 1 https://github.com/fachat/xa65.git xa65 && make -s -C xa65/xa xa && cp xa65/xa/xa "$P/bin/"; }
command -v flex >/dev/null || { curl -sSL -o flex.tgz https://github.com/westes/flex/releases/download/v2.6.4/flex-2.6.4.tar.gz && tar xzf flex.tgz && (cd flex-2.6.4 && ./configure -q --prefix="$P" && make -s && make -s install); }
command -v dos2unix >/dev/null || { printf '#!/bin/sh\nfor f in "$@"; do case "$f" in -*) ;; *) sed -i "s/\\r$//" "$f";; esac; done\n' > "$P/bin/dos2unix"; chmod +x "$P/bin/dos2unix"; }
if [ ! -x "$P/bin/x64sc" ]; then
  [ -d vice ] || { git clone -q --depth 1 --filter=blob:none --sparse https://github.com/VICE-Team/svn-mirror.git vice-mirror && (cd vice-mirror && git sparse-checkout set vice) && ln -s vice-mirror/vice vice; }
  (cd vice && ./autogen.sh >/dev/null)
  mkdir -p vice-build && cd vice-build
  ../vice/configure -q --enable-headlessui --disable-pdf-docs --disable-html-docs --without-pulse --without-alsa --without-oss \
     --without-png --without-gif --disable-realdevice --disable-ethernet --disable-catweasel --disable-hardsid --disable-parsid --without-libcurl >/dev/null
  make -s -j"$(nproc)" -C src/lib/linenoise-ng >/dev/null; make -s -j"$(nproc)" x64sc >/dev/null || make -s -j"$(nproc)" -C src x64sc >/dev/null
  cp src/x64sc "$P/bin/"; make -s -C src/tools/cartconv >/dev/null 2>&1 && cp src/tools/cartconv/cartconv "$P/bin/" || true
fi
echo "toolchain ready in $P/bin"
