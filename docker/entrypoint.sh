#!/usr/bin/env bash
set -euo pipefail

ensure_display() {
  if [ -z "${DISPLAY:-}" ]; then
    export DISPLAY=:99
    Xvfb :99 -screen 0 1400x900x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
    for _ in $(seq 1 50); do
      [ -S /tmp/.X11-unix/X99 ] && break
      sleep 0.1
    done
  fi
}

case "${1:-serve}" in
  serve)   shift; ensure_display; exec python3 -m uvicorn web.main:app --host 0.0.0.0 --port 8000 "$@" ;;
  generate) shift; ensure_display; exec python3 /app/scripts/generate.py "$@" ;;
  verify)  shift; exec python3 /app/scripts/verify.py "$@" ;;
  bash|sh) shift; exec /bin/bash "$@" ;;
  *)       exec "$@" ;;
esac
