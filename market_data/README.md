# Market Data (`market_data`)

Canonical runtime guide for ingestion, replay, and API.

For full system behavior (including dashboard + WS bridge), also read `../MODE_SYSTEM.md`.
For quick command selection (live / real historical / mock), see `../README.md`.
For explicit mode/source execution instructions, see `../RUN_MODES_GUIDE.md`.
**For GenAI agent data integration**, see `../GENAI_AGENT_DATA_REFERENCE.md`.
For stream topology and timestamp lineage, see `src/market_data/EVENT_DERIVATION_CONTRACT.md`.

## What this module provides

- Supervisor runtime (`market_data.runner`)
- Historical replay runtime (`market_data.runner_historical` + `runtime.py`)
- API service (`market_data.api_service`) on port `8004`
- Redis-backed storage and pub/sub messages for ticks, OHLC, and indicators

## Critical policy: Zerodha historical is real-only

When source is `zerodha`, the system is **fail-fast**:

- No automatic synthetic fallback
- `kiteconnect` must be installed
- Valid Zerodha credentials/token must be available
- Replay must produce data within readiness timeout

If any of the above fails, startup exits with a non-zero status.

## Prerequisites

- Python virtual environment (`.venv` recommended)
- Redis available at configured host/port
- Credentials for Zerodha real modes

Install runtime deps (includes `kiteconnect`):

- `python -m pip install -r market_data/requirements.txt`

Critical note: technical indicators (Momentum/Volatility/Levels/OI) require
`pandas`, `numpy`, and `pandas-ta` in the same Python environment used by
`start_system.ps1`. If these are missing, indicator APIs may return partial or
`no_data` payloads and dashboard cards will show `--`.

## Credentials

Provide one of:

- root `credentials.json`
- environment: `KITE_API_KEY`, `KITE_ACCESS_TOKEN`

Interactive auth helper:

- `python -m market_data.tools.kite_auth`

## Recommended startup (repo root)

### Windows PowerShell (canonical)

- Real historical replay (Zerodha, explicit env):
  - Ensure port 8004 is free (`Get-NetTCPConnection -LocalPort 8004`); stop any stale python on that port.
  - Start Redis on expected port (default 6380 for repo scripts).
  - Set env and run:
    ```powershell
    $env:PYTHONPATH = "$PWD\market_data\src;$PWD"
    $env:REDIS_PORT = "6380"
    $env:INSTRUMENT_SYMBOL = "BANKNIFTY26MARFUT"
    $env:MODE = "historical"
    python -m market_data.runner --mode historical --historical-source zerodha --historical-from 2026-02-11 --historical-speed 1
    ```
  - Or use helper script: `./stop_system.ps1; ./start_system.ps1 -Source historical -HistoricalSource zerodha -HistoricalFrom 2026-02-11 -HistoricalSpeed 1 -FreshStart`
  - Now-like replay for a historical date (example 13 Feb 2026):
    - `./stop_system.ps1; ./start_system.ps1 -Source historical -HistoricalSource zerodha -HistoricalFrom 2026-02-13 -HistoricalSpeed 1 -TimeSemantics rebase -FreshStart`
- Live:
  - `./start_system.ps1 -Source kite`
- Mock/dev:
  - `./start_system.ps1 -Source mock`

### Bash (legacy/secondary)

- `./start_all.sh --source historical --historical-source zerodha --historical-from 2026-02-11 --historical-speed 1`
- `./start_all.sh --source kite`
- `./start_all.sh --source mock`

Stop:

- PowerShell: `./stop_system.ps1`
- Bash: `./stop_all.sh`

## Direct module commands (advanced)

- API only: `python -m market_data.api_service`
- Supervisor: `python -m market_data.runner --mode live --start-collectors`
- Historical replay process: `python -m market_data.runner_historical --historical-source zerodha --historical-from 2026-02-11 --historical-speed 1`

## Health checks

- API: `http://127.0.0.1:8004/health`
- Dashboard proxy health (if dashboard running): `http://127.0.0.1:8000/api/market-data/health`
- Indicator metadata sample: `http://127.0.0.1:8004/api/v1/technical/indicators/{instrument}?timeframe=1min`

Indicator metadata contract:

- `indicator_timestamp`: when indicator was calculated
- `indicator_source`: source/update path (`redis_cache`, `ohlc_recalculated`, `tick`, `candle`, etc.)
- `indicator_stream`: transport stream (`Y2` snapshot, `LZ1` intrabar)
- `indicator_update_type`: `candle`, `tick`, `batch_initialize`, `batch_recalculate`
- `bars_available`: bars currently available for the timeframe
- `warmup_requirements`: minimum bars map used by indicator warm-up logic
- Use these fields for recency/provenance instead of custom freshness flags

## Technical indicator warm-up matrix

| Indicator | Minimum bars | First non-null expectation | Publish trigger |
|---|---:|---|---|
| RSI(14) | 14 | after 14 closed bars | candle-close / batch |
| MACD | 26 | after 26 closed bars | candle-close / batch |
| Bollinger(20) | 20 | after 20 closed bars | candle-close / batch |
| CCI(20) | 20 | after 20 closed bars | candle-close / batch |
| Stoch(14) | 14 | after 14 closed bars | candle-close / batch |
| ATR(14) | 14 | after 14 closed bars | candle-close / batch |
| MFI(14) | 14 | after 14 bars with usable volume | candle-close / batch |
| ROC(12) | 12 | after 12 closed bars | candle-close / batch |
| Momentum(10) | 10 | after 10 closed bars | candle-close / batch |

## Runtime environment variables

| Variable | Purpose | Typical value |
|---|---|---|
| `REDIS_HOST` | Redis host | `localhost` |
| `REDIS_PORT` | Redis port | `6380` (repo default setup) |
| `EXECUTION_MODE` | Redis namespace prefix | `live` or `historical` |
| `INSTRUMENT_SYMBOL` | Replay/ingestion instrument symbol | `BANKNIFTY26FEBFUT` |
| `HISTORICAL_SOURCE` | Replay source | `zerodha` / `synthetic` / CSV path |
| `HISTORICAL_FROM` | Replay date | `YYYY-MM-DD` |
| `HISTORICAL_SPEED` | Replay speed multiplier | `1` |
| `HISTORICAL_READY_TIMEOUT` | Fail-fast timeout (seconds) | `60` |

## Key runtime files

- `src/market_data/runner.py` — supervisor, dependency validation, preflight checks
- `src/market_data/runtime.py` — replay config, Zerodha credential resolution, fail-fast behavior
- `src/market_data/runner_historical.py` — replay process entrypoint
- `src/market_data/adapters/unified_replayer.py` — replay engine (zerodha/csv/synthetic)
- `src/market_data/api_service.py` — API server

## Troubleshooting

### `kiteconnect` missing

- Install into active venv: `python -m pip install -r market_data/requirements.txt`

### Zerodha historical exits immediately

Likely causes:

- invalid/expired access token
- missing credentials file/env vars
- no data returned for requested date/instrument

Check logs:

- `.run/market_data.log`
- `.run/market_data.err`

### API is healthy but charts look empty

- verify instrument is present in Redis with `historical:ohlc_sorted:*` (e.g., `historical:ohlc_sorted:BANKNIFTY26MARFUT:1min`)
- 5m charts need the first five 1m candles to populate; initial `No OHLC data found ...:5min` is expected until ~5 bars are stored
- verify dashboard can connect to `ws://127.0.0.1:8000/ws` (full-stack canonical)
- ensure clients are not pointing to `ws://localhost:8889/ws` (not used by this stack)
- verify Redis pub/sub channels (`market:ohlc:*`) are active
- if OI indicators throw numba typing errors, update to latest code (pandas fallbacks) and restart

Note: dashboard UI does not auto-fallback to REST polling on repeated websocket failures; it reports websocket unavailable until reconnect/manual refresh.

### Charts move but technical indicator cards stay `--`

Likely causes:
- API process is down (`:8004` not listening)
- Indicator dependencies missing in active venv (`pandas`, `numpy`, `pandas-ta`)
- Selected timeframe has no bars yet (e.g., early 5m window)

Checks:
- `http://127.0.0.1:8004/health`
- `http://127.0.0.1:8004/api/v1/technical/indicators/<INSTRUMENT>?timeframe=minute`
- `http://127.0.0.1:8004/api/v1/technical/indicators/<INSTRUMENT>?timeframe=5min`

---

Last updated: 2026-02-13
