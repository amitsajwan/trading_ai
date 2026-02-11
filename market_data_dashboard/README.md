# Market Data Dashboard

A standalone dashboard for monitoring market data status and visualization, completely decoupled from trading engine functionality.

## Features

- **Real-time Status Monitoring**: Live health checks for market data API
- **Data Validation**: Comprehensive validation of data availability and freshness
- **Visual Charts**: Interactive price charts for key instruments
- **Decoupled Architecture**: Works independently of engine/trading services
- **Responsive Design**: Modern web interface with real-time updates

## Quick Start

### Recommended (from repo root)

```bash
./start_all.sh --source mock
# Dashboard: http://localhost:8000/
```


### Full historical replay (specific date + speed)

**Bash (Linux/macOS/WSL):**

```bash
./start_all.sh --source historical --historical-source zerodha --historical-from 2026-02-11 --historical-speed 1
```

**PowerShell (Windows):**

```powershell
.\start_system.ps1 -Source historical -HistoricalSource zerodha -HistoricalFrom 2026-02-11 -HistoricalSpeed 1 -FreshStart
```

This starts the full chain (**ticks/collector -> market data API -> dashboard**) and replays from `2026-02-11` at `1x` speed.

### Local dashboard-only run

```bash
cd market_data_dashboard
pip install -r requirements.txt
python start_dashboard.py
# Dashboard: http://localhost:8000/
```

> Note: `python app.py` is still available and defaults to port `8008`, but `start_dashboard.py` is the runtime path used by `start_all.sh`.

## API Endpoints

- `GET /` - Main dashboard page
- `GET /api/health` - Service health check
- `GET /api/market-data/health` - Market data API health
- `GET /api/market-data/status` - Comprehensive status and validation
- `GET /api/market-data/ohlc/{instrument}` - OHLC data for instrument
- `GET /api/market-data/instruments` - Available instruments list

## Configuration

Environment variables:
- `MARKET_DATA_API_URL` - Market data API endpoint (default: http://localhost:8004)
- `DASHBOARD_PORT` - Dashboard port for `start_dashboard.py` (default: `8000`)
- `MARKET_DATA_DASHBOARD_PORT` - Dashboard port for direct `app.py` run (default: `8008`)

## Architecture

This dashboard is designed to be completely independent and only requires:
- Market Data API (port 8004)
- No database connections
- No trading engine dependencies
- No authentication requirements

Perfect for monitoring market data health and validating data pipelines without the complexity of full trading functionality.