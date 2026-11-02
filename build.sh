#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

./download-coppeliasim.sh

echo "[..] 构建镜像（首次约 5–15 分钟）"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose build "$@"
else
  docker build -f docker/Dockerfile -t rlbench-demogen:v1 . "$@"
fi
echo "[ok] 完成。冒烟测试: docker compose run --rm demogen generate --tasks reach_and_drag --episodes 2 --workers 1"
