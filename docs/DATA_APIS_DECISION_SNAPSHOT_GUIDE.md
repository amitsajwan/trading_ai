# Data + API Upgrade Guide (Decision Snapshot, Futures-First, Normalized Keys)

This guide documents the recent data pipeline and API upgrades, the decision snapshot schema, and their impact on strategies and GenAI agents. Use this as a working reference for analysis and next steps.

## 1) Overview
- Unified instrument key normalization: Bank Nifty → `NIFTYBANK`; Nifty 50 → `NIFTY`.
- Futures-first collection for Indian markets when `INSTRUMENT_EXCHANGE=NFO`.
- New live metrics captured from Zerodha `quote()`: `volume`, `vwap` (average_price), `oi`.
- Robust Redis caching via MarketMemory for ticks, prices, and futures metrics.
- `/api/market-data` upgraded: now returns live `volume_24h`, `vwap`, and `futures.oi` when available.
- Decision Snapshot (`/api/decision-snapshot`): single-call consolidated context (LTP, depth analytics, futures, options summary).
- Health endpoint enhanced to report LTP freshness and recent depth presence.
- Reset tooling to purge Redis + Mongo cleanly per instrument.

## 2) Data Pipeline Changes
- Collectors:
  - LTP Data Collector: builds OHLC candles; computes per-candle volume via delta from cumulative exchange volume; writes to Mongo.
  - Depth Collector: persists full tick with depth (top 5), totals, best bid/ask; also stores live `volume`, `average_price` (VWAP), `oi` in Redis.
- Normalized Keys in Redis (Bank Nifty only): use `NIFTYBANK` for all keys.
  - `price:<KEY>:latest`, `price:<KEY>:latest_ts`
  - `tick:<KEY>:<iso_ts>`
  - `volume:<KEY>:latest`, `vwap:<KEY>:latest`, `oi:<KEY>:latest`
  - `snapshot:<KEY>:latest`
- MongoDB: `ohlc_history` indexes improved for `(instrument,timestamp)` and `(instrument,timeframe,timestamp)`.

## 3) API Contracts (Key Endpoints)
- GET `/api/market-data`
  - Returns snake_case plus camelCase aliases (e.g., `current_price` and `currentPrice`).
  - Zerodha example fields: `current_price`, `market_open`, `volume_24h`, `vwap`, `change_24h`, `futures.{volume,oi,average_price}`.
  - Data source flag: `data_source` = `Redis` when live; otherwise `MongoDB` fallback.
- GET `/api/decision-snapshot`
  - Consolidated view with:
    - `ltp`
    - `futures.{volume,oi,average_price}`
    - `depth.{best_bid,best_ask,total_bid_qty,total_ask_qty,spread,view,large_orders,imbalance}`
    - `options` summary: futures price, ATM row, PCR, totals.
  - Cached at `snapshot:<KEY>:latest` with short TTL (~60s).
- GET `/api/health`
  - `status`: `ok` (fresh LTP and recent depth), `degraded` (one fresh), `unhealthy` (neither fresh).
  - Includes `ltp_fresh`, `ltp_age_seconds`, `depth_recent`, `depth_age_seconds`.

See: `dashboard/app.py` for current shapes; `docs/API.md` now includes the Decision Snapshot section and Zerodha-specific notes.

## 4) Decision Snapshot Schema (Working)
```json
{
  "instrument": "NIFTYBANK",
  "timestamp": "2026-01-05T10:00:00Z",
  "ltp": 60500.0,
  "futures": { "volume": 123456.0, "oi": 98765.0, "average_price": 60420.5 },
  "depth": {
    "best_bid": 60490.0,
    "best_ask": 60510.0,
    "total_bid_qty": 120000,
    "total_ask_qty": 115000,
    "spread": { "bps": 33.0, "value": 20.0 },
    "view": { "buy": [], "sell": [] },
    "large_orders": { "buy": [], "sell": [] },
    "imbalance": { "ratio": 0.52 }
  },
  "options": {
    "available": true,
    "futures_price": 60510.0,
    "atm_strike": 60500,
    "ce_ltp": 350.0,
    "pe_ltp": 420.0,
    "ce_oi": 1200000,
    "pe_oi": 1300000,
    "pcr": 1.08,
    "total_ce_oi": 12000000,
    "total_pe_oi": 13000000,
    "strikes_sampled": 50
  }
}
```

## 5) Impact on Technical Calculations / Algos
- Prefer futures metrics for intraday F&O strategies:
  - Use `futures.oi` for OI trend and OI/price divergence.
  - Use live `volume_24h` and `vwap` from Redis when available (lower latency than OHLC aggregation).
- Candle volume correctness:
  - OHLC candle volume is derived from the delta of cumulative volume; downstream volume-based indicators (VWAP, OBV, volume ratio) become more reliable.
- Order Flow:
  - Access depth analytics from snapshot for spread, imbalance, and large orders.
  - Consider integrating top-of-book changes into momentum/mean-reversion logic.
- Options Analytics (current):
  - PCR and ATM row are included; expand to use OI change deltas (planned).
- Signals should consume `/api/decision-snapshot` where possible to minimize fan-out reads and keep consistency across modules.

## 6) Impact on GenAI Agents
- Agent context:
  - Provide `decision-snapshot` as primary market context (ltp, futures, depth, options) instead of piecemeal calls.
  - Include data freshness hints (e.g., health endpoint summary) to let agents reason about data validity.
- Prompting changes (suggested):
  - Ask portfolio/review agents to ground their reasoning in `futures.oi`, `vwap`, and `depth.imbalance` where relevant.
  - Encourage technical and sentiment agents to reference the snapshot and avoid recomputing from raw series unless necessary.
- Metrics & Limits:
  - `/api/metrics/llm` available to monitor provider health/usage; can gate heavy analysis cycles.

## 7) Ops, Testing, and Tooling
- Reset: `scripts/reset_data.py` supports per-instrument cleanup; normalized to `NIFTYBANK`/`NIFTY`.
- Health: `/api/health` should be used by container healthchecks to detect lagging collectors.
- Tests:
  - Fast local tests stub Redis to validate endpoints without Docker.
  - Docker tests verify live endpoints across BTC, BankNifty, Nifty setups.
- Docker: Collectors and backends defined with healthchecks; rebuild required to pick up response aliasing and key normalization.

## 8) Migration Checklist
- [ ] Ensure all services read/write `NIFTYBANK` (no `BANKNIFTY` keys).
- [ ] Set `.env.banknifty` → `INSTRUMENT_SYMBOL=NIFTY BANK`; `INSTRUMENT_EXCHANGE=NFO` for futures-first.
- [ ] Rebuild and restart backend containers after pulling changes.
- [ ] Strategy code to prefer `/api/decision-snapshot` over multiple endpoints.
- [ ] Update any custom dashboards/clients to accept snake_case or camelCase (both provided).

## 9) Open Items / Next Steps
- Options analytics: add OI change deltas by strike and across curve.
- Strategy runner: consume decision snapshot and emit paper signals with risk limits.
- Health docs: add brief section in API.md with `ok/degraded/unhealthy` logic.
- Deprecations: migrate FastAPI `on_event` startup to lifespan events; replace `utcnow()` uses.
- Add dual-instrument switcher in UI if needed (BankNifty/Nifty) using normalized keys.

## 10) Quick Commands
```powershell
# Rebuild and restart backends to pick latest API aliasing and keys
docker-compose build backend-btc backend-banknifty backend-nifty
docker-compose up -d backend-btc backend-banknifty backend-nifty

# Health checks
Invoke-WebRequest -Uri "http://localhost:8002/api/health" -UseBasicParsing

# Market data + decision snapshot
(Invoke-WebRequest -Uri "http://localhost:8002/api/market-data" -UseBasicParsing).Content
(Invoke-WebRequest -Uri "http://localhost:8002/api/decision-snapshot" -UseBasicParsing).Content
```
