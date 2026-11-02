#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

./download-coppeliasim.sh

echo "[..] 构建镜像"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose build "$@"
else
  docker build -f docker/Dockerfile -t rlbench-demogen:v1 . "$@"
fi
echo "[ok]"
