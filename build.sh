#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

./download-coppeliasim.sh

MIRROR="${DEMOGEN_GH_MIRROR:-}"
if [ -z "$MIRROR" ]; then
  if ! timeout 10 git ls-remote https://github.com/stepjam/PyRep HEAD >/dev/null 2>&1; then
    MIRROR="https://ghfast.top/"
    echo "[..] GitHub 直连不通，启用镜像加速: ${MIRROR}"
  fi
fi

ARGS=()
[ -n "$MIRROR" ] && ARGS+=(--build-arg "GITHUB_MIRROR=${MIRROR}")
[ -n "${DEMOGEN_PIP_INDEX:-}" ] && ARGS+=(--build-arg "PIP_INDEX_URL=${DEMOGEN_PIP_INDEX}")

echo "[..] 构建镜像"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose build "${ARGS[@]}" "$@"
else
  docker build -f docker/Dockerfile "${ARGS[@]}" -t rlbench-demogen:latest .
fi
echo "[ok] 完成。冒烟测试: docker compose run --rm demogen generate --tasks reach_and_drag --episodes 2 --workers 1"
