# Market Data (market_data)

Mode-aware market data ingestion, storage, and APIs for live, historical, and mock workflows. This guide is the **single source of truth** for running the `market_data` module.

## ✅ What this module does

- Live market data ingestion via Zerodha WebSocket and REST
- Historical replay (Zerodha or CSV) into Redis
- Mock/synthetic replay for local testing
- REST API for ticks, OHLC, depth, options chain, and indicators
- Mode isolation via Redis key prefixes

## 🧭 Architecture (market_data only)

```
Sources (Live / Historical / Mock)
                        │
                        ▼
 Ingestion + Replay (collectors / replayer)
                        │
                        ▼
                    Redis
                        │
                        ▼
                Market Data API
```

**Mode isolation:** keys are prefixed using `EXECUTION_MODE` (`live` or `historical`).

## ⚙️ Prerequisites

- Python 3.8+
- Redis running (default: `localhost:6379`)
- Zerodha credentials for live or Zerodha historical replay

## 🔐 Credentials (live or zerodha historical)

Provide either:
- `credentials.json` in the repo root, or
- environment variables: `KITE_API_KEY`, `KITE_ACCESS_TOKEN`

Generate credentials interactively:

- `python -m market_data.tools.kite_auth`

## 🚀 Run (recommended)

### Live mode (WebSocket + LTP + depth)

- `python -m market_data.runner --mode live --start-collectors`

### Historical mode (Zerodha)

- `python -m market_data.runner --mode historical --historical-source zerodha --historical-from 2026-01-28 --historical-speed 10`

### Historical mode (CSV file)

- `python -m market_data.runner --mode historical --historical-source path/to/file.csv --historical-speed 10`

### Mock mode (synthetic)

- `python -m market_data.runner --mode mock --historical-speed 5`

## 🧰 One-command full startup (repo root)

## ✅ Startup command clarity (important)

Use these as the only startup commands:

- Linux/macOS/Git-Bash:
  - `./start_all.sh --source kite`
  - `./start_all.sh --source historical --historical-source synthetic`
  - `./start_all.sh --source mock`
  - Stop: `./stop_all.sh`

- PowerShell users (native, no bash):
  - `./start_system.ps1 -Source kite`
  - `./start_system.ps1 -Source historical -HistoricalSource synthetic`
  - `./start_system.ps1 -Source mock`
  - Stop: `./stop_system.ps1`

Legacy compatibility:
- `-Mode live|historical|paper` is still accepted and mapped to `-Source kite|historical|mock`.

From the repository root you can start the full stack (ingestion + API + dashboard) with a single command:

- `./start_all.sh --source kite`
- `./start_all.sh --source mock`
- `./start_all.sh --source historical --historical-source zerodha`

Behavior:
- Uses one websocket-source contract (`kite` / `mock` / `historical`) while keeping downstream collectors/processors/API/dashboard unchanged.
- `--source historical` now runs through the same websocket collector path (historical websocket adapter), so switching source does not change downstream flow.
- `--source kite` includes auth as part of startup via `market_data.runner --prompt-login`.
- Fresh start is enabled by default and only clears the selected mode namespace (`live:*` or `historical:*`) so live and historical caches remain isolated.
- Stop all started services with `./stop_all.sh`.

## 🧪 API health checks

- `http://localhost:8004/health`
- `http://localhost:8004/api/v1/market/price/BANKNIFTY`

## 🔧 Configuration

| Variable | Purpose | Default |
|---|---|---|
| `REDIS_HOST` | Redis host | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
| `EXECUTION_MODE` | Redis key prefix (`live` / `historical`) | `live` |
| `INSTRUMENT_SYMBOL` | Default instrument | `BANKNIFTY26JANFUT` |
| `INSTRUMENTS` | Comma-separated instruments for unified ingestion | _(optional)_ |
| `INSTRUMENT_TRADING_SYMBOLS` | Comma-separated trading symbols | _(optional)_ |
| `INSTRUMENT_EXCHANGES` | Comma-separated exchanges | _(optional)_ |
| `INSTRUMENT_EXCHANGE` | Exchange | `NFO` |
| `KITE_API_KEY` | Zerodha API key | _(required for live/zerodha)_ |
| `KITE_ACCESS_TOKEN` | Zerodha access token | _(required for live/zerodha)_ |
| `TRADING_MODE` | Unified ingestion mode (`live` / `historical` / `mock`) | `live` |
| `HISTORICAL_SOURCE` | Replay source (`zerodha` / `synthetic` / CSV path) | `synthetic` |
| `HISTORICAL_FROM` | Replay start date (YYYY-MM-DD) | _(optional)_ |
| `HISTORICAL_SPEED` | Replay speed multiplier | `1.0` |
| `TRADING_PROVIDER` | Provider selection (`zerodha` / `mock`) | _(optional)_ |
| `USE_MOCK_KITE` | Force mock provider when set | `0` |

## 🧩 Key entrypoints

- `python -m market_data.api_service` — run API only
- `python -m market_data.runner` — supervisor for API + collectors + replay
- `python -m market_data.collectors.websocket_tick_collector` — websocket collector (source via `KITE_WS_SOURCE=real|mock|historical`)
- `python -m market_data.runner_historical` — legacy replay-only path
- `./start_all.sh --source kite|mock|historical` — bash full-stack startup from repo root
- `./start_system.ps1 -Source kite|mock|historical` — PowerShell-native full-stack startup

## 🧱 Core runtime files (current)

```
market_data/
├── README.md
├── src/market_data/
│   ├── runner.py
│   ├── api_service.py
│   ├── collectors/
│   │   ├── websocket_tick_collector.py
│   │   ├── ltp_collector.py
│   │   └── depth_collector.py
│   ├── sources/
│   │   ├── mock_kite_websocket.py
│   │   ├── historical_kite_websocket.py
│   │   └── websocket.py
│   └── adapters/
│       └── unified_replayer.py
└── ../start_all.sh
```

## 🛠️ Troubleshooting

### Redis not reachable
- Verify Redis is running and `REDIS_HOST`/`REDIS_PORT` are correct.

### API starts but has no data
- In live mode: ensure credentials are valid and collectors started.
- In historical/mock: ensure websocket source is running (`--source historical` or `--source mock`) and Redis keys are populated.

### Full process (cleanup + start)

Run from repo root.

**PowerShell (Windows):**

```powershell
.\stop_system.ps1; .\start_system.ps1 -Source historical -HistoricalSource zerodha -HistoricalFrom 2026-02-11 -HistoricalSpeed 1 -FreshStart
```

This sequence:
- stops old tracked processes,
- starts historical source with Zerodha,
- replays from `2026-02-11` at `1x`,
- starts API + dashboard.

**Equivalent Bash (WSL/Linux/macOS):**

```bash
./stop_all.sh && ./start_all.sh --source historical --historical-source zerodha --historical-from 2026-02-11 --historical-speed 1
```

### Quick verify

**PowerShell:**

```powershell
iwr http://127.0.0.1:8004/health
iwr http://127.0.0.1:8000/api/health
Get-Content .\.run\market_data.log -Tail 100 -Wait
Get-Content .\.run\dashboard.log -Tail 100 -Wait
```

### Local dashboard-only run

### Wrong mode data
- Set `EXECUTION_MODE` explicitly before starting services.

---

**Last Updated:** March 2026
