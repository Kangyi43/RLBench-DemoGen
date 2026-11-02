#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

URL="https://downloads.coppeliarobotics.com/V4_1_0/CoppeliaSim_Player_V4_1_0_Ubuntu20_04.tar.xz"
DEST="docker/coppeliasim.tar.xz"
MIN_BYTES=60000000

if [ -f "$DEST" ] && [ "$(stat -c%s "$DEST")" -ge "$MIN_BYTES" ]; then
  echo "[ok] 已存在 $DEST（$(du -h "$DEST" | cut -f1)），跳过下载"
  exit 0
fi

mkdir -p docker
echo "[..] 下载 CoppeliaSim Player 4.1 (~62MB)"
echo "     直链: $URL"
echo "     若以下方式都很慢，请用浏览器/下载工具把文件保存到 $DEST 后重新运行本脚本"

if command -v aria2c >/dev/null 2>&1; then
  aria2c -x16 -s16 -c -d docker -o coppeliaSim.tar.xz.tmp "$URL" \
    && mv docker/coppeliasim.tar.xz.tmp "$DEST"
elif command -v wget >/dev/null 2>&1; then
  wget -c --tries=20 --timeout=30 --progress=dot:giga -O "$DEST.tmp" "$URL" \
    && mv "$DEST.tmp" "$DEST"
else
  curl -L -C - --retry 20 --retry-delay 3 -o "$DEST.tmp" "$URL" \
    && mv "$DEST.tmp" "$DEST"
fi

SIZE=$(stat -c%s "$DEST")
if [ "$SIZE" -lt "$MIN_BYTES" ]; then
  echo "[!] 文件不完整（$SIZE 字节），请重跑本脚本续传" >&2
  exit 1
fi
echo "[ok] 下载完成: $DEST（$SIZE 字节）"
