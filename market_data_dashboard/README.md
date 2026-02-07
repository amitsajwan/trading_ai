# Market Data Dashboard

A standalone dashboard for monitoring market data status and visualization, completely decoupled from trading engine functionality.

## Features

- **Real-time Status Monitoring**: Live health checks for market data API
- **Data Validation**: Comprehensive validation of data availability and freshness
- **Visual Charts**: Interactive price charts for key instruments
- **Decoupled Architecture**: Works independently of engine/trading services
- **Responsive Design**: Modern web interface with real-time updates

## Quick Start

### Docker (Recommended)

```bash
# Start with Docker Compose
docker-compose up -d market-data-dashboard

# Access at http://localhost:8008/
```

### Local Development

```bash
cd market_data_dashboard
pip install -r requirements.txt
python app.py
```

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
- `MARKET_DATA_DASHBOARD_PORT` - Dashboard port (default: 8008)

## Architecture

This dashboard is designed to be completely independent and only requires:
- Market Data API (port 8004)
- No database connections
- No trading engine dependencies
- No authentication requirements

Perfect for monitoring market data health and validating data pipelines without the complexity of full trading functionality.