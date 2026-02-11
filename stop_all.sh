#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"

stopped=0
for service in dashboard market_data; do
  pid_file="$RUN_DIR/${service}.pid"
  if [[ -f "$pid_file" ]]; then
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" || true
      echo "[stop_all] Stopped $service (pid=$pid)"
      stopped=$((stopped+1))
    fi
    rm -f "$pid_file"
  fi
done

if [[ "$stopped" -eq 0 ]]; then
  echo "[stop_all] No tracked processes were running"
else
  echo "[stop_all] ✅ Done"
fi
