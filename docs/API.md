# REST API Reference

## Overview

The GenAI Trading System provides a comprehensive REST API for monitoring, control, and data access. The API is served by FastAPI and includes automatic OpenAPI documentation.

## Base URL

- **Single Instrument**: `http://localhost:8888`
- **Multi-Instrument**:
  - BTC: `http://localhost:8001`
  - Bank Nifty: `http://localhost:8002`
  - Nifty 50: `http://localhost:8003`

## Authentication

Currently no authentication required (development mode). In production, implement API key authentication.

## Core Endpoints

### System Status

#### GET `/api/status`
Get overall system health and status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T10:00:00Z",
  "version": "1.0.0",
  "uptime": "2h 30m",
  "services": {
    "database": "connected",
    "redis": "connected",
    "websocket": "active",
    "llm": "ready"
  }
}
```

### Agent Status

#### GET `/api/agent-status`
Get current status and analysis from all agents.

**Response:**
```json
{
  "timestamp": "2024-01-01T10:00:00Z",
  "instrument": "BTC-USD",
  "agents": {
    "technical": {
      "status": "completed",
      "signal": "BUY",
      "confidence": 0.75,
      "reasoning": "Strong uptrend with RSI divergence",
      "last_update": "2024-01-01T09:58:00Z"
    },
    "fundamental": {
      "status": "completed",
      "signal": "HOLD",
      "confidence": 0.60,
      "reasoning": "Fair valuation reached",
      "last_update": "2024-01-01T09:57:00Z"
    },
    "sentiment": {
      "status": "running",
      "signal": null,
      "confidence": null,
      "last_update": "2024-01-01T09:59:00Z"
    }
  },
  "portfolio_manager": {
    "status": "pending",
    "final_signal": null,
    "confidence": null
  }
}
```

### Market Data

#### GET `/api/market-data`
Get current market data and recent OHLC.

**Query Parameters:**
- `timeframe` (optional): `1min`, `5min`, `15min`, `1h`, `daily` (default: `5min`)
- `limit` (optional): Number of candles to return (default: 100)

**Response:**
```json
{
  "instrument": "BTC-USD",
  "current_price": 45000.50,
  "price_change_24h": 2.5,
  "volume_24h": 1234567890,
  "ohlc_data": [
    {
      "timestamp": "2024-01-01T10:00:00Z",
      "open": 44900.00,
      "high": 45100.00,
      "low": 44800.00,
      "close": 45050.00,
      "volume": 1234567
    }
  ]
}
```

#### GET `/api/ticker`
Get real-time ticker data.

**Response:**
```json
{
  "instrument": "BTC-USD",
  "last_price": 45000.50,
  "bid": 45000.00,
  "ask": 45001.00,
  "volume": 1234567,
  "timestamp": "2024-01-01T10:00:00Z"
}
```

### Trading Data

#### GET `/api/positions`
Get current open positions.

**Response:**
```json
{
  "positions": [
    {
      "instrument": "BTC-USD",
      "side": "BUY",
      "quantity": 0.01,
      "entry_price": 44500.00,
      "current_price": 45000.50,
      "pnl": 50.50,
      "pnl_percentage": 1.14,
      "entry_timestamp": "2024-01-01T09:30:00Z"
    }
  ],
  "summary": {
    "total_pnl": 50.50,
    "total_pnl_percentage": 1.14,
    "open_positions": 1
  }
}
```

#### GET `/api/trades`
Get recent trade history.

**Query Parameters:**
- `limit` (optional): Number of trades to return (default: 50)
- `status` (optional): `OPEN`, `CLOSED`, `CANCELLED`

**Response:**
```json
{
  "trades": [
    {
      "trade_id": "BTC_20240101_001",
      "instrument": "BTC-USD",
      "status": "OPEN",
      "side": "BUY",
      "quantity": 0.01,
      "entry_price": 44500.00,
      "exit_price": null,
      "pnl": 50.50,
      "confidence": 0.75,
      "entry_timestamp": "2024-01-01T09:30:00Z",
      "agent_decisions": {
        "technical": "BUY",
        "fundamental": "HOLD",
        "sentiment": "BUY"
      }
    }
  ],
  "pagination": {
    "total": 25,
    "limit": 50,
    "offset": 0
  }
}
```

### News and Sentiment

#### GET `/api/news`
Get recent news and sentiment analysis.

**Query Parameters:**
- `limit` (optional): Number of news items (default: 20)
- `sentiment` (optional): `positive`, `negative`, `neutral`

**Response:**
```json
{
  "news": [
    {
      "title": "Bitcoin ETF Sees Record Inflows",
      "source": "CoinDesk",
      "sentiment": "positive",
      "impact": "high",
      "timestamp": "2024-01-01T09:45:00Z",
      "url": "https://coindesk.com/...",
      "summary": "Spot Bitcoin ETF attracted $500M in inflows..."
    }
  ],
  "sentiment_summary": {
    "overall": "bullish",
    "positive": 12,
    "negative": 3,
    "neutral": 5
  }
}
```

### Performance Analytics

#### GET `/api/performance`
Get trading performance metrics.

**Query Parameters:**
- `period` (optional): `1d`, `7d`, `30d`, `90d` (default: `30d`)

**Response:**
```json
{
  "period": "30d",
  "metrics": {
    "total_trades": 45,
    "winning_trades": 32,
    "losing_trades": 13,
    "win_rate": 0.711,
    "avg_win": 125.50,
    "avg_loss": -85.30,
    "profit_factor": 1.85,
    "sharpe_ratio": 1.23,
    "max_drawdown": -3.2,
    "total_pnl": 1250.75,
    "total_pnl_percentage": 8.5
  },
  "daily_pnl": [
    {"date": "2024-01-01", "pnl": 45.50},
    {"date": "2024-01-02", "pnl": -12.25}
  ]
}
```

### System Control

#### POST `/api/trading/pause`
Pause trading execution.

**Request Body:**
```json
{
  "reason": "Manual pause for maintenance"
}
```

**Response:**
```json
{
  "status": "paused",
  "timestamp": "2024-01-01T10:00:00Z",
  "reason": "Manual pause for maintenance"
}
```

#### POST `/api/trading/resume`
Resume trading execution.

**Response:**
```json
{
  "status": "active",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

#### POST `/api/force-signal`
Force a specific trading signal (development only).

**Request Body:**
```json
{
  "signal": "BUY",
  "confidence": 0.8,
  "reason": "Manual override"
}
```

**Response:**
```json
{
  "status": "executed",
  "trade_id": "MANUAL_20240101_001",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

### Configuration

#### GET `/api/config`
Get current system configuration.

**Response:**
```json
{
  "instrument": {
    "symbol": "BTC-USD",
    "name": "Bitcoin",
    "data_source": "CRYPTO"
  },
  "trading": {
    "paper_trading": true,
    "max_position_size_pct": 5.0,
    "max_leverage": 2.0,
    "default_stop_loss_pct": 1.5
  },
  "llm": {
    "provider": "groq",
    "model": "llama-3.1-8b-instant",
    "temperature": 0.3
  },
  "risk": {
    "daily_loss_limit_pct": 2.0,
    "max_drawdown_pct": 15.0
  }
}
```

## WebSocket Endpoints

### Real-time Updates

#### WS `/ws/market-data`
Real-time market data updates.

**Message Format:**
```json
{
  "type": "ticker",
  "data": {
    "instrument": "BTC-USD",
    "price": 45000.50,
    "volume": 1234567,
    "timestamp": "2024-01-01T10:00:00Z"
  }
}
```

#### WS `/ws/agent-updates`
Real-time agent analysis updates.

**Message Format:**
```json
{
  "type": "agent_update",
  "agent": "technical",
  "data": {
    "signal": "BUY",
    "confidence": 0.75,
    "timestamp": "2024-01-01T10:00:00Z"
  }
}
```

## Error Handling

### HTTP Status Codes

- `200`: Success
- `400`: Bad Request (invalid parameters)
- `404`: Not Found (endpoint doesn't exist)
- `500`: Internal Server Error (system error)

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid timeframe parameter",
    "details": {
      "parameter": "timeframe",
      "provided": "invalid",
      "allowed": ["1min", "5min", "15min", "1h", "daily"]
    }
  },
  "timestamp": "2024-01-01T10:00:00Z"
}
```

## Rate Limiting

- **Authenticated Requests**: 1000 requests per minute
- **Anonymous Requests**: 100 requests per minute
- **WebSocket Connections**: 10 concurrent connections

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

## SDK and Examples

### Python Client

```python
import requests

class TradingAPI:
    def __init__(self, base_url="http://localhost:8888"):
        self.base_url = base_url

    def get_status(self):
        response = requests.get(f"{self.base_url}/api/status")
        return response.json()

    def get_positions(self):
        response = requests.get(f"{self.base_url}/api/positions")
        return response.json()

# Usage
api = TradingAPI()
status = api.get_status()
positions = api.get_positions()
```

### JavaScript Client

```javascript
class TradingAPI {
    constructor(baseURL = 'http://localhost:8888') {
        this.baseURL = baseURL;
    }

    async getStatus() {
        const response = await fetch(`${this.baseURL}/api/status`);
        return response.json();
    }

    async getMarketData(timeframe = '5min') {
        const response = await fetch(
            `${this.baseURL}/api/market-data?timeframe=${timeframe}`
        );
        return response.json();
    }
}

// Usage
const api = new TradingAPI();
const status = await api.getStatus();
const marketData = await api.getMarketData('1min');
```

## Monitoring

### Health Checks

#### GET `/health`
Simple health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

#### GET `/metrics`
Prometheus-compatible metrics.

**Response:**
```
# HELP api_requests_total Total number of API requests
# TYPE api_requests_total counter
api_requests_total{method="GET",endpoint="/api/status"} 1250

# HELP agent_analysis_duration_seconds Time spent on agent analysis
# TYPE agent_analysis_duration_seconds histogram
agent_analysis_duration_seconds_bucket{le="5"} 0
agent_analysis_duration_seconds_bucket{le="10"} 15
```

## Production Considerations

### Security

- Implement HTTPS in production
- Add API key authentication
- Rate limiting and DDoS protection
- Input validation and sanitization

### Scaling

- Use load balancer for multiple instances
- Redis clustering for cache scaling
- MongoDB sharding for data scaling
- Horizontal pod scaling in Kubernetes

### Monitoring

- Implement comprehensive logging
- Set up alerting for critical errors
- Monitor API latency and error rates
- Track business metrics (P&L, win rate)