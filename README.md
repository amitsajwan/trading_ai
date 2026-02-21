# Zerodha Stack Quickstart

This is the fastest way to run the current system correctly.

For architecture details, see `MODE_SYSTEM.md`.
For operator run instructions by source/mode/settings, see `RUN_MODES_GUIDE.md`.
For module details, see `market_data/README.md` and `market_data_dashboard/README.md`.
**For GenAI agent data integration**, see `GENAI_AGENT_DATA_REFERENCE.md`.

## Core operating principle

Only the **source** should change between runs (`kite`, `historical+zerodha`, `historical+synthetic`, `historical+local`, `mock`).
The rest of the pipeline is intentionally shared:

`source -> unified replay/ingestion -> Redis store -> indicators -> API -> dashboard/UI`

Execution settings (namespace mode, time semantics, replay speed) are separate controls.

## Primary daily run pattern (2 modes)

For most usage, operate in only these two modes:

1. **Live mode** (normal day)
	- `./stop_system.ps1`
	- `./start_system.ps1 -Source kite`
2. **Historical mode** (start from specific historical date, same speed profile)
	- `./stop_system.ps1`
	- `./start_system.ps1 -Source historical -HistoricalSource zerodha -HistoricalFrom <YYYY-MM-DD> -HistoricalSpeed 1 -TimeSemantics rebase -FreshStart`

Example:

- `./start_system.ps1 -Source historical -HistoricalSource zerodha -HistoricalFrom 2026-02-13 -HistoricalSpeed 1 -TimeSemantics rebase -FreshStart`

Keep `-HistoricalSpeed 1` as the default consistent profile unless you intentionally want faster/slower replay.

## Quickstart matrix

| Goal | Windows PowerShell (canonical) | Bash / WSL (secondary) | Real Zerodha data? |
|---|---|---|---|
| Live streaming (collector mode) | `./start_system.ps1 -Source kite` | `./start_all.sh --source kite` | Yes |
| Historical replay from Zerodha (real-only, fail-fast) | `./stop_system.ps1; ./start_system.ps1 -Source historical -HistoricalSource zerodha -HistoricalFrom 2026-02-11 -HistoricalSpeed 1 -FreshStart` | `./stop_all.sh && ./start_all.sh --source historical --historical-source zerodha --historical-from 2026-02-11 --historical-speed 1` | Yes |
| Historical replay from local archive | `./stop_system.ps1; ./start_system.ps1 -Source historical -HistoricalSource local -HistoricalFrom 2023-06-15 -HistoricalSpeed 1 -FreshStart` | `./stop_all.sh && ./start_all.sh --source historical --historical-source local --historical-from 2023-06-15 --historical-speed 1` | Local file data |
| Historical replay as live-now (13 Feb example) | `./stop_system.ps1; ./start_system.ps1 -Source historical -HistoricalSource zerodha -HistoricalFrom 2026-02-13 -HistoricalSpeed 1 -TimeSemantics rebase -FreshStart` | `./stop_all.sh && ./start_all.sh --source historical --historical-source zerodha --historical-from 2026-02-13 --historical-speed 1` | Yes |
| Mock/dev mode | `./start_system.ps1 -Source mock` | `./start_all.sh --source mock` | No |
| Stop stack | `./stop_system.ps1` | `./stop_all.sh` | N/A |

## Important runtime rules

- `historical + zerodha` is **real-only**: no synthetic fallback.
- If `kiteconnect` is missing, credentials are invalid, or replay produces no data in time, startup fails fast.
- Mode namespaces are isolated in Redis (`live:*`, `historical:*`, `paper:*`).
- Fresh start clears only the selected namespace.
- Use the same venv as scripts (`.venv`) and install `market_data/requirements.txt` before first run.

## Verify after start

- API health: `http://127.0.0.1:8004/health`
- Dashboard health: `http://127.0.0.1:8000/api/health`
- Dashboard UI: `http://127.0.0.1:8000/`
- WebSocket/STOMP: `ws://127.0.0.1:8000/ws`
- Note: no service in this stack listens on `ws://localhost:8889/ws`
- Indicator metadata check: `http://127.0.0.1:8000/api/market-data/indicators/{instrument}?timeframe=1min` and confirm `indicator_timestamp` + `indicator_source`
- Indicator metadata clarity:
  - `indicator_source` = where calculation came from
  - `indicator_stream` = stream family (`Y2` snapshot / `LZ1` intrabar)
  - `indicator_update_type` = `candle`, `tick`, `batch_initialize`, `batch_recalculate`
- STOMP parsing rule:
  - Dashboard WS messages are wrapped (`type`, `channel`, `data`); for indicators, read values from `data.payload`
- Logs: `.run/market_data.log`, `.run/dashboard.log`

UI runtime note:

- On repeated websocket failures, dashboard shows WS unavailable and does **not** auto-fallback to REST polling.
- Dashboard now includes an **Indicator Metadata** card (Calculated At, Source, Timeframe, Update Type, Mode, Status).

Last updated: 2026-02-14
