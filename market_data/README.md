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

## 🐳 Docker Compose (market_data only)

Use the single compose file in `market_data/docker-compose.yml`.

### Live mode

- `TRADING_MODE=live docker compose -f market_data/docker-compose.yml up --build`

### Historical mode (Zerodha)

- `TRADING_MODE=historical HISTORICAL_SOURCE=zerodha HISTORICAL_FROM=2026-01-28 docker compose -f market_data/docker-compose.yml up --build`

### Mock mode (synthetic)

- `TRADING_MODE=mock HISTORICAL_SOURCE=synthetic docker compose -f market_data/docker-compose.yml up --build`

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
- `python -m market_data.runner_historical` — historical replay only
- `python -m market_data.services.unified_ingestion` — unified ingestion (live/historical/mock)
- `python -m market_data.services.unified_processor` — mode-agnostic processing (volume enhancer)

## 🧱 Simplified structure

```
market_data/
├── src/market_data/
│   ├── adapters/
│   │   └── unified_replayer.py
│   ├── sources/
│   │   ├── websocket.py
│   │   ├── historical.py
│   │   ├── mock.py
│   │   └── depth.py
│   ├── processors/
│   │   ├── volume_enhancer.py
│   │   ├── ohlc_builder.py
│   │   └── indicator_engine.py
│   ├── services/
│   │   ├── unified_ingestion.py
│   │   └── unified_processor.py
│   ├── collectors/
│   │   ├── websocket_tick_collector.py
│   │   ├── ltp_collector.py
│   │   └── depth_collector.py
│   ├── api_service.py
│   └── api.py
└── docker-compose.yml
```

## 🛠️ Troubleshooting

### Redis not reachable
- Verify Redis is running and `REDIS_HOST`/`REDIS_PORT` are correct.

### API starts but has no data
- In live mode: ensure credentials are valid and collectors started.
- In historical/mock: ensure replay is running and Redis keys are populated.

### Wrong mode data
- Set `EXECUTION_MODE` explicitly before starting services.

---

**Last Updated:** February 2026
