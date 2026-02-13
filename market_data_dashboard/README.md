# Market Data Dashboard (`market_data_dashboard`)

Frontend + backend dashboard service for status monitoring, charts, and Redis-to-browser streaming.

For quick run commands by scenario, see `../README.md`.
**For GenAI agent data integration**, see `../GENAI_AGENT_DATA_REFERENCE.md`.

## What this service does

- Serves dashboard UI (`/`)
- Proxies market-data HTTP endpoints
- Reads Redis directly when API endpoints are missing/slow
- Bridges Redis pub/sub to browser via STOMP-over-WebSocket (`/ws`)

## Runtime dependencies

From `requirements.txt`:

- `fastapi`, `uvicorn`, `jinja2`, `requests`, `redis`, `python-dotenv`

## Run

### Recommended (full stack)

- Start from repo root with `start_system.ps1` (Windows) or `start_all.sh` (bash)

### Dashboard only

- `python market_data_dashboard/start_dashboard.py`

Environment used by dashboard:

- `DASHBOARD_HOST` (default `0.0.0.0`)
- `DASHBOARD_PORT` (default `8000`)
- `MARKET_DATA_API_URL` (default `http://localhost:8004`)
- `REDIS_HOST`, `REDIS_PORT`

## Main endpoints

- `GET /` → dashboard page
- `GET /api/health` → dashboard health
- `GET /api/market-data/status` → merged status view
- `GET /api/market-data/ohlc/{instrument}`
- `GET /api/market-data/indicators/{instrument}`
- `GET /api/market-data/depth/{instrument}`
- `GET /api/market-data/options/{instrument}`
- `GET /api/market-data/instruments`
- `WS /ws` → STOMP + legacy JSON websocket

### Endpoint behavior notes

- `/api/market-data/status` is mode-aware and can mark per-instrument `mode_mismatch` when Redis data exists in a non-current namespace.
- `/api/market-data/options/{instrument}` is resilient to upstream slowness:
	- returns `status=ok` when fresh,
	- `status=stale` when serving last-good cache,
	- `status=no_data` with mode-aware message when no chain is present.
- `/api/market-data/depth/{instrument}` and `/api/market-data/indicators/{instrument}` also use stale fallback behavior under transient upstream failures.

## STOMP topic mapping

Dashboard maps STOMP destinations to Redis channels/patterns:

- `/topic/auth/status` → `auth:status`
- `/topic/market/ohlc/{instrument}` → `market:ohlc:{instrument}:*`
- `/topic/market/ohlc/{instrument}/{timeframe}` → `market:ohlc:{instrument}:{timeframe}`
- `/topic/market/tick/{instrument}` → `market:tick:{instrument}:*`
- `/topic/indicators/{instrument}` → `indicators:{instrument}:*`

It supports STOMP subprotocols (`v12.stomp`, `v11.stomp`, `v10.stomp`, `stomp`).

## Redis integration notes

- Dashboard uses **sync Redis pubsub in a background thread** for WS forwarding.
- This avoids issues observed with async pubsub in some Windows environments.
- Instrument list can be auto-discovered from Redis `ohlc_sorted` keys.

## UI behavior highlights

- Auto-selects an instrument that is actually available in Redis
- Throttles/coalesces chart refreshes under streaming load
- Uses fallback polling when websocket repeatedly fails
- In live mode, options-chain fetches may take ~10-20s depending on provider response times
- Tick-topic rendering load is intentionally minimized to keep websocket stable

## Troubleshooting

### WebSocket connected but no chart updates

Check:

1. Redis pub/sub channels are active (`market:ohlc:*`)
2. UI subscribed to correct instrument topic
3. `/api/market-data/ohlc/{instrument}` returns data

### Dashboard health fails

Check:

- `.run/dashboard.log`
- `.run/dashboard.err`
- `MARKET_DATA_API_URL` reachability

---

Last updated: 2026-02-13
