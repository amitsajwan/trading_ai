# System Flow (Current, Canonical)

This document describes the **actual runtime behavior** of the current stack in this repository.

If anything conflicts with old docs, trust this file and `market_data/README.md`.

For fastest startup commands by scenario, use the matrix in `README.md` (repo root).**For GenAI agent data integration**, see `GENAI_AGENT_DATA_REFERENCE.md`.
## Overview

The platform has three running layers:

1. **Ingestion + API (`market_data`)**
2. **Dashboard backend (`market_data_dashboard`)**
3. **Browser UI (`templates/index.html`)**

Core runtime ports:

- `8004` → Market Data API
- `8000` → Dashboard app
- Redis from environment (`REDIS_HOST`, `REDIS_PORT`) — this repo commonly uses `6380`

## End-to-End Data Flow

### 1) Startup orchestration

On Windows, use:

- `start_system.ps1`
- `stop_system.ps1`

`start_system.ps1` does:

1. Loads `market_data/.env`
2. Selects source contract (`kite` / `mock` / `historical`)
3. Sets mode env (`EXECUTION_MODE`) and related vars
4. Optionally clears only selected mode keys (`FreshStart`)
5. Starts `market_data.runner`
6. Waits for API health (`/health`)
7. Starts dashboard (`start_dashboard.py`)
8. Waits for dashboard health (`/api/health`)

### 2) Historical Zerodha replay path (real-only)

When run with:

- `-Source historical -HistoricalSource zerodha`

the runner path is:

`market_data.runner` → `market_data.runner_historical` → `market_data.runtime.run_historical_replay` → `UnifiedHistoricalReplayer`

### 3) Storage + publish

Replayed bars/ticks are written into Redis and published on pub/sub channels.

Examples:

- Sorted OHLC keys: `historical:ohlc_sorted:{instrument}:{timeframe}`
- Pub/Sub OHLC: `market:ohlc:{instrument}:{timeframe}`
- Pub/Sub tick: `market:tick:{instrument}:*`
- Pub/Sub indicators: `indicators:{instrument}:*`

### 4) Dashboard backend bridge

`market_data_dashboard/app.py`:

- Serves HTML/REST endpoints
- Exposes `/ws` (WebSocket with STOMP support)
- Bridges Redis pub/sub → STOMP `MESSAGE` frames
- Applies mode-aware status reporting (`available`/`mode_mismatch`/`no_data`)
- Uses stale-cache fallback for options/depth/indicators when upstream API is slow

Topic mapping:

- `/topic/auth/status` → `auth:status`
- `/topic/market/ohlc/{instrument}` → `market:ohlc:{instrument}:*`
- `/topic/market/ohlc/{instrument}/{timeframe}` → `market:ohlc:{instrument}:{timeframe}`
- `/topic/market/tick/{instrument}` → `market:tick:{instrument}:*`
- `/topic/indicators/{instrument}` → `indicators:{instrument}:*`

### 5) Browser update loop

The dashboard UI refreshes charts/status with throttling and coalescing to avoid request storms.
Tick-topic rendering load is intentionally minimized in UI, with polling fallback on repeated websocket failures.

## Fail-Fast Policy (Important)

For **real historical Zerodha replay**, the system now fails fast by design:

- No silent fallback to synthetic/mock when `historical-source=zerodha`
- If `kiteconnect` is missing → startup fails
- If credentials/token are missing/invalid → startup fails
- If replay does not produce data in timeout window → startup fails

This policy is enforced in:

- `market_data/src/market_data/runner.py`
- `market_data/src/market_data/runtime.py`
- `market_data/src/market_data/api.py`
- `market_data/src/market_data/dependency_validator.py`

## Modes and isolation

The stack isolates data by key prefix (`live:` / `historical:` / `paper:`), and startup scripts clear only the selected namespace on fresh start.

## Quick operational checks

1. API healthy: `http://127.0.0.1:8004/health`
2. Dashboard healthy: `http://127.0.0.1:8000/api/health`
3. WS connected in browser status card
4. Instrument card shows increasing data points

## What is obsolete now

The previous docs that described broad synthetic fallback as default runtime behavior are obsolete for Zerodha real replay.

Use this doc + `market_data/README.md` as canonical references.
