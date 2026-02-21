# Run Modes Guide (Canonical)

This is the clearest operator guide for running the stack in different modes.

If anything conflicts with older notes, follow this file + `start_system.ps1`.

## Primary daily workflow (recommended)

For your normal operations, treat this as a 2-mode runbook:

1. **Live mode** for normal trading day operations
2. **Historical mode** when starting a new day from a chosen historical date

Use the **same replay speed profile** for historical starts (typically `-HistoricalSpeed 1`) so behavior stays consistent run-to-run.

### A) Live mode (default day-to-day)

- `./stop_system.ps1`
- `./start_system.ps1 -Source kite`

### B) Historical mode (new day from historical date, same speed profile)

- `./stop_system.ps1`
- `./start_system.ps1 -Source historical -HistoricalSource local -HistoricalFrom <YYYY-MM-DD> -HistoricalSpeed 1 -FastForwardTo 11:21 -FastForwardSpeed 20 -TimeSemantics clock -FreshStart`

Example:

- `./start_system.ps1 -Source historical -HistoricalSource local -HistoricalFrom 2023-06-15 -HistoricalSpeed 1 -FastForwardTo 11:21 -FastForwardSpeed 20 -TimeSemantics clock -FreshStart`

Notes:
- Keep `-HistoricalSpeed 1` unless you intentionally want faster/slower replay.
- `-TimeSemantics clock` keeps replay aligned to wall clock for day-to-day historical simulation.
- `-FastForwardTo 11:21 -FastForwardSpeed 20` is recommended so indicators warm up quickly, then run at normal speed.
- Optional local data override: `$env:LOCAL_HISTORICAL_BASE = 'C:\archive\banknifty_data'`.

## One mental model (most important)

Only **source** should change between runs. The pipeline remains the same.

`Source Adapter -> Unified Replay/Ingestion -> Redis Store -> Indicators -> API (8004) -> Dashboard (8002) -> UI/WS`

### Source choices

- `kite` -> live Zerodha websocket/collectors
- `historical + local` -> local archive replay (e.g., `C:\archive\banknifty_data`)
- `historical + zerodha` -> real historical replay (secondary)
- `historical + synthetic` -> synthetic replay data (secondary)
- `mock` -> mock source for local development

Price expectation note:
- `historical + local` and `historical + zerodha` use real historical price levels from their data sources.
- `historical + synthetic` uses generated values (default base is near `45000` unless generator config is changed).

## Architecture clarity: canonical replay only

- Canonical replay engine: `market_data/src/market_data/adapters/unified_replayer.py`

This means behavior should be consistent across sources because all paths converge to the same replay/store/indicator stack.

## Execution settings (separate from source)

These settings affect runtime behavior but are not data-source changes.

| Setting | Purpose | Typical owner |
|---|---|---|
| Namespace mode (`live:` / `historical:` / `paper:`) | Redis key isolation | startup scripts |
| Time semantics (`-TimeSemantics`) | `rebase` = fixed now-shift, `clock` = wall-clock aligned timeline, `virtual` = system virtual clock | startup scripts |
| Replay speed (`HISTORICAL_SPEED`) | replay time multiplier (`1` real intervals, `2` 2x faster, `0.5` slower, `<=0` instant) | startup flags |
| Fresh start | clears only selected namespace | startup scripts |

### Time semantics quick reference

- `-TimeSemantics auto` (default)
  - `historical + synthetic` -> behaves as `rebase` (now-like)
  - `historical + zerodha` -> keeps historical timestamps
- `-TimeSemantics rebase`
  - Replays historical data with timestamps shifted to now-like time.
- `-TimeSemantics clock`
  - Replays historical data on a wall-clock aligned timeline.
  - Primary choice for `historical + local`.
  - With fast-forward enabled, replay warms up quickly then aligns to wall clock at anchor.
- `-TimeSemantics virtual`
  - Enables Redis-backed virtual clock keys:
    - `system:virtual_time:enabled=1`
    - `system:virtual_time:current=<ISO time>`
  - Optional: `-VirtualTimeStart 2026-02-13T09:15:00+05:30`

## Canonical commands (Windows PowerShell)

Run from repo root `C:\code\trading_genai\trading_ai`.

### 1) Live real market

- `./start_system.ps1 -Source kite`

### 2) Historical local archive (primary)

- `./stop_system.ps1`
- `./start_system.ps1 -Source historical -HistoricalSource local -HistoricalFrom 2023-06-15 -HistoricalSpeed 1 -FastForwardTo 11:21 -FastForwardSpeed 20 -TimeSemantics clock -FreshStart`

Optional base path override:

- `$env:LOCAL_HISTORICAL_BASE = 'C:\archive\banknifty_data'`

### 2b) Historical local archive without fast-forward

- `./start_system.ps1 -Source historical -HistoricalSource local -HistoricalFrom 2023-06-15 -HistoricalSpeed 1 -FreshStart`

### 2c) Historical local archive with custom fast-forward target

- `./start_system.ps1 -Source historical -HistoricalSource local -HistoricalFrom 2023-06-15 -HistoricalSpeed 1 -FastForwardTo 11:36 -FastForwardSpeed 20 -TimeSemantics clock -FreshStart`

### 2d) Historical real Zerodha (secondary)

- `./stop_system.ps1`
- `./start_system.ps1 -Source historical -HistoricalSource zerodha -HistoricalFrom 2026-02-11 -HistoricalSpeed 1 -FreshStart`

### 3) Historical synthetic replay

- `./stop_system.ps1`
- `./start_system.ps1 -Source historical -HistoricalSource synthetic -HistoricalSpeed 1 -FreshStart`

### 3b) Historical synthetic replay with virtual time

- `./stop_system.ps1`
- `./start_system.ps1 -Source historical -HistoricalSource synthetic -HistoricalSpeed 1 -TimeSemantics virtual -FreshStart`

### 3c) Historical synthetic replay with pinned virtual start

- `./stop_system.ps1`
- `./start_system.ps1 -Source historical -HistoricalSource synthetic -HistoricalSpeed 1 -TimeSemantics virtual -VirtualTimeStart 2026-02-13T09:15:00+05:30 -FreshStart`

### 4) Mock/dev mode

- `./stop_system.ps1`
- `./start_system.ps1 -Source mock -FreshStart`

### Stop stack

- `./stop_system.ps1`

## Bash/WSL equivalents (secondary)

- Live: `./start_all.sh --source kite`
- Historical zerodha: `./start_all.sh --source historical --historical-source zerodha --historical-from 2026-02-11 --historical-speed 1`
- Historical synthetic: `./start_all.sh --source historical --historical-source synthetic --historical-speed 1`
- Mock: `./start_all.sh --source mock`
- Stop: `./stop_all.sh`

## Verify after each start

- API health: `http://127.0.0.1:8004/health`
- Dashboard health: `http://127.0.0.1:8002/api/health`
- Mode: `http://127.0.0.1:8004/api/v1/system/mode`
- Instruments: `http://127.0.0.1:8004/api/v1/market/instruments`
- OHLC sample: `http://127.0.0.1:8002/api/market-data/ohlc/{instrument}?timeframe=1m&limit=20`
- Indicator metadata sample: `http://127.0.0.1:8002/api/market-data/indicators/{instrument}?timeframe=1m` and verify `indicator_timestamp` + `indicator_source`
- Also verify:
  - `indicator_stream` (`Y2` for snapshot updates, `LZ1` for intrabar tick updates)
  - `indicator_update_type` is set (`candle`, `tick`, `batch_initialize`, `batch_recalculate`)
  - `bars_available` and `warmup_requirements` explain any `--` warm-up indicators
  - STOMP consumers parse wrapped frames (`type`, `channel`, `data`) and read indicator values from `data.payload`
- For virtual mode: call `/api/v1/system/mode` twice after 3-5s and confirm `virtual_time` changes.

### Dynamic consumer contract API (runtime-aware)

- Capabilities (mode/instruments/features): `http://127.0.0.1:8002/api/capabilities`
- Runtime catalog (resolved Redis keys + API probes): `http://127.0.0.1:8002/api/catalog?instrument={instrument}`
- Schema index (versioned): `http://127.0.0.1:8002/api/schema`
- Topic schema: `http://127.0.0.1:8002/api/schema/{topic}` where topic is one of `mode,tick,ohlc,indicators,depth,options`
- Live sample payload by topic: `http://127.0.0.1:8002/api/examples/{topic}?instrument={instrument}&timeframe=1m`

## Key contract (canonical Redis)

- All runtime keys are mode-prefixed: `live:*`, `historical:*`, `paper:*`.
- Canonical timeframe labels in Redis are `1m`, `5m`, `15m`.
- Do not validate against unprefixed keys or `5min`/`15min` Redis keys.

Examples:

- `historical:ohlc_sorted:{instrument}:1m`
- `historical:ohlc_sorted:{instrument}:5m`
- `historical:ohlc_sorted:{instrument}:15m`
- `historical:indicators:{instrument}:1m:rsi_14`
- `historical:indicators:{instrument}:5m:macd_value`

## Operational guardrails

- Always run `./stop_system.ps1` before switching source/mode.
- Avoid mixed startup paths in one session (PowerShell + Bash simultaneously).
- Keep one active stack per machine/session to avoid duplicate writers.
- For zerodha historical, no synthetic fallback is expected by design.

---

Last updated: 2026-02-20


