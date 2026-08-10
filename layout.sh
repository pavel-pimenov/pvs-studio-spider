#!/usr/bin/env bash
for spec in \
  "haproxy|https://github.com/haproxy/haproxy.git" \
  "lz4|https://github.com/lz4/lz4.git" \
  "farmanager|https://github.com/FarGroup/FarManager.git" \
  "mediainfo|https://github.com/MediaArea/MediaInfo.git" \
  "mpc-be-core|https://github.com/Aleksoid1978/MPC-BE.git" \
  "mtproxy|https://github.com/TelegramMessenger/MTProxy.git"; do
  slug="${spec%%|*}"; repo="${spec##*|}"
  echo "=== $slug ==="
  rm -rf /tmp/layout_$slug
  git clone --depth 1 "$repo" /tmp/layout_$slug >/dev/null 2>&1
  ls /tmp/layout_$slug 2>/dev/null | head -25
  echo "--- CMakeLists ---"
  find /tmp/layout_$slug -maxdepth 3 -name CMakeLists.txt 2>/dev/null | head -8
  echo "--- top Makefile ---"
  ls /tmp/layout_$slug/Makefile /tmp/layout_$slug/makefile 2>/dev/null
  rm -rf /tmp/layout_$slug
done
echo OK
