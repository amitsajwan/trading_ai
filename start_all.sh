#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"
mkdir -p "$RUN_DIR"

SOURCE="mock"
FRESH_START="1"
HISTORICAL_SOURCE="${HISTORICAL_SOURCE:-synthetic}"
HISTORICAL_SPEED="${HISTORICAL_SPEED:-5}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

usage() {
  cat <<USAGE
Usage: ./start_all.sh --source kite|mock|historical [options]

Options:
  --source <kite|mock|historical>   Upstream source contract selector (default: mock)
  --fresh-start <0|1>               Delete only selected mode keys before launch (default: 1)
  --historical-source <value>       zerodha|synthetic|/path/file.csv (default: synthetic)
  --historical-speed <float>        Replay speed multiplier (default: 5)
  -h, --help                        Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      SOURCE="$2"; shift 2 ;;
    --fresh-start)
      FRESH_START="$2"; shift 2 ;;
    --historical-source)
      HISTORICAL_SOURCE="$2"; shift 2 ;;
    --historical-speed)
      HISTORICAL_SPEED="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1 ;;
  esac
done

case "$SOURCE" in
  kite)
    RUNNER_MODE="live"
    EXEC_MODE="live"
    WS_SOURCE="real"
    RUNNER_ARGS=(--mode live --start-collectors --prompt-login)
    ;;
  mock)
    RUNNER_MODE="live"
    EXEC_MODE="historical"
    WS_SOURCE="mock"
    RUNNER_ARGS=(--mode live --start-collectors)
    ;;
  historical)
    RUNNER_MODE="live"
    EXEC_MODE="historical"
    WS_SOURCE="historical"
    RUNNER_ARGS=(--mode live --start-collectors)
    ;;
  *)
    echo "Invalid --source '$SOURCE'. Use: kite|mock|historical" >&2
    exit 1 ;;
esac

# Stop existing processes launched by this script if still running.
for pid_file in "$RUN_DIR"/*.pid; do
  [[ -e "$pid_file" ]] || continue
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" || true
    sleep 1
  fi
  rm -f "$pid_file"
done

if [[ "$FRESH_START" == "1" ]]; then
  echo "[start_all] Fresh start enabled: deleting '${EXEC_MODE}:*' keys only"
  python3 - <<PY
import os
import redis

host = os.getenv('REDIS_HOST', '$REDIS_HOST')
port = int(os.getenv('REDIS_PORT', '$REDIS_PORT'))
mode = '$EXEC_MODE'

r = redis.Redis(host=host, port=port, db=0, decode_responses=True)
cursor = 0
deleted = 0
while True:
    cursor, keys = r.scan(cursor=cursor, match=f"{mode}:*", count=1000)
    if keys:
        deleted += r.delete(*keys)
    if cursor == 0:
        break
# remove historical readiness marker for deterministic replay checks
if mode == 'historical':
    r.delete('system:historical:ready')
print(f"[start_all] Deleted keys for mode '{mode}': {deleted}")
PY
fi

echo "[start_all] Starting market_data runner (source=$SOURCE, mode=$RUNNER_MODE)..."
(
  cd "$ROOT_DIR"
  export PYTHONPATH="$ROOT_DIR/market_data/src:$ROOT_DIR"
  export EXECUTION_MODE="$EXEC_MODE"
  export KITE_WS_SOURCE="$WS_SOURCE"
  if [[ "$WS_SOURCE" != "real" ]]; then
    export USE_MOCK_KITE="1"
  fi
  if [[ "$WS_SOURCE" == "historical" ]]; then
    export HISTORICAL_WS_SOURCE="$HISTORICAL_SOURCE"
    export HISTORICAL_WS_TICK_INTERVAL="0.25"
  fi
  nohup python3 -m market_data.runner "${RUNNER_ARGS[@]}" > "$RUN_DIR/market_data.log" 2>&1 &
  echo $! > "$RUN_DIR/market_data.pid"
)

# Wait for API health
for _ in {1..60}; do
  if curl -sf "http://127.0.0.1:8004/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -sf "http://127.0.0.1:8004/health" >/dev/null 2>&1; then
  echo "[start_all] ERROR: market_data API did not become healthy. Check $RUN_DIR/market_data.log" >&2
  exit 1
fi


echo "[start_all] Starting dashboard..."
(
  cd "$ROOT_DIR/market_data_dashboard"
  export MARKET_DATA_API_URL="http://127.0.0.1:8004"
  nohup python3 start_dashboard.py > "$RUN_DIR/dashboard.log" 2>&1 &
  echo $! > "$RUN_DIR/dashboard.pid"
)

# Wait for dashboard health
for _ in {1..30}; do
  if curl -sf "http://127.0.0.1:8000/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo ""
echo "[start_all] ✅ system started"
echo "  Source:      $SOURCE"
echo "  Exec mode:   $EXEC_MODE"
echo "  API:         http://127.0.0.1:8004/health"
echo "  Dashboard:   http://127.0.0.1:8000/"
echo "  Logs:        $RUN_DIR/market_data.log, $RUN_DIR/dashboard.log"
echo "  Stop:        ./stop_all.sh"
