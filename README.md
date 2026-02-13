# Zerodha Stack Quickstart

This is the fastest way to run the current system correctly.

For architecture details, see `MODE_SYSTEM.md`.
For module details, see `market_data/README.md` and `market_data_dashboard/README.md`.
**For GenAI agent data integration**, see `GENAI_AGENT_DATA_REFERENCE.md`.

## Quickstart matrix

| Goal | Windows PowerShell (canonical) | Bash / WSL (secondary) | Real Zerodha data? |
|---|---|---|---|
| Live streaming (collector mode) | `./start_system.ps1 -Source kite` | `./start_all.sh --source kite` | Yes |
| Historical replay from Zerodha (real-only, fail-fast) | `./stop_system.ps1; ./start_system.ps1 -Source historical -HistoricalSource zerodha -HistoricalFrom 2026-02-11 -HistoricalSpeed 1 -FreshStart` | `./stop_all.sh && ./start_all.sh --source historical --historical-source zerodha --historical-from 2026-02-11 --historical-speed 1` | Yes |
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
- Logs: `.run/market_data.log`, `.run/dashboard.log`

Last updated: 2026-02-12
