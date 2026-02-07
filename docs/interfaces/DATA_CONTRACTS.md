# Data Contracts and Component Interfaces

This document defines the data contracts, schemas, and interfaces for all system components. It serves as the authoritative source for component interactions and data formats.

## Table of Contents

1. [Data Storage Contracts](#data-storage-contracts)
2. [API Interface Contracts](#api-interface-contracts)
3. [Component Communication](#component-communication)
4. [Schema Validation](#schema-validation)
5. [Error Handling Contracts](#error-handling-contracts)

## Data Storage Contracts

### OHLC Data Format

**Primary Storage**: Redis Sorted Sets
```
Key: ohlc:{instrument}:{timeframe}
Score: Unix timestamp (float)
Value: JSON string with OHLC data
```

**Legacy Storage**: Redis Individual Keys (DEPRECATED - cleaned up 2026-01-18)
```
Key: ohlc:{instrument}:{timeframe}:{timestamp}
Value: JSON string with OHLC data
TTL: 86400 seconds (24 hours)
Status: Removed - system now uses unified sorted set format only
```

**Schema**:
```json
{
  "type": "object",
  "properties": {
    "instrument": {"type": "string", "pattern": "^[A-Z0-9_]+$"},
    "timeframe": {"type": "string", "enum": ["1min", "5min", "15min", "1h", "1d"]},
    "timestamp": {"type": "string", "format": "date-time"},
    "open": {"type": "number", "minimum": 0},
    "high": {"type": "number", "minimum": 0},
    "low": {"type": "number", "minimum": 0},
    "close": {"type": "number", "minimum": 0},
    "volume": {"type": "integer", "minimum": 0},
    "start_at": {"type": "string", "format": "date-time"}
  },
  "required": ["instrument", "timeframe", "timestamp", "open", "high", "low", "close"]
}
```

### Data Management & Cleanup

**Storage Migration Completed**: 2026-01-18
- ✅ **Removed**: 108 legacy individual OHLC keys
- ✅ **Standardized**: All data now uses Redis sorted sets only
- ✅ **Eliminated**: Data validation warnings and format inconsistencies

**Benefits**:
- Unified data format across the system
- Improved query performance with sorted sets
- Simplified data validation and integrity checks
- Consistent timestamp field usage (`timestamp` vs `start_at`)

### Technical Indicators Data Format

**Storage**: Redis Individual Keys
```
Key: indicators:{instrument}:{indicator_name}
Value: String representation of numeric value
TTL: 300 seconds (5 minutes)
```

**Supported Indicators**:
- `rsi_14`: Relative Strength Index (0-100)
- `macd_value`: MACD line value
- `macd_signal`: MACD signal line
- `bollinger_upper`: Bollinger Band upper
- `bollinger_lower`: Bollinger Band lower
- `adx_14`: Average Directional Index (0-100)

### Tick Data Format

**Storage**: Redis Sorted Sets
```
Key: tick:{instrument}:latest
Value: JSON string with latest tick data
```

```
Key: tick:{instrument}:{timestamp}
Value: JSON string with historical tick data
TTL: 3600 seconds (1 hour)
```

**Schema**:
```json
{
  "type": "object",
  "properties": {
    "instrument": {"type": "string", "pattern": "^[A-Z0-9_]+$"},
    "timestamp": {"type": "string", "format": "date-time"},
    "last_price": {"type": "number", "minimum": 0},
    "volume": {"type": "integer", "minimum": 0},
    "original_timestamp": {"type": ["string", "null"], "format": "date-time"}
  },
  "required": ["instrument", "timestamp", "last_price"]
}
```

## API Interface Contracts

### Market Data API

**Base URL**: `http://localhost:8004`

#### Endpoints

**GET /health**
- **Purpose**: Basic health check
- **Response**: `{"status": "healthy", "service": "market_data_api"}`

**GET /health/detailed**
- **Purpose**: Comprehensive health check with validation
- **Response**:
```json
{
  "summary": {
    "overall_status": "healthy|degraded|unhealthy",
    "total_checks": 16,
    "passed": 15,
    "warnings": 1,
    "errors": 0,
    "critical_errors": 0
  },
  "checks": [...],
  "data_validation": {
    "ohlc_data_validation": {...},
    "technical_indicators_validation": {...},
    "system_health": {...}
  },
  "timestamp": "2026-01-18T16:38:22.929242+05:30"
}
```

**GET /api/v1/market/tick/{instrument}**
- **Purpose**: Get latest tick data
- **Parameters**:
  - `instrument`: Trading instrument symbol
- **Response**:
```json
{
  "instrument": "BANKNIFTY26JANFUT",
  "timestamp": "2026-01-18T16:38:22.929242+05:30",
  "last_price": 59968.9,
  "volume": 1000
}
```

**GET /api/v1/technical/indicators/{instrument}**
- **Purpose**: Get technical indicators
- **Parameters**:
  - `instrument`: Trading instrument symbol
  - `timeframe`: "1min" (default)
- **Response**:
```json
{
  "instrument": "BANKNIFTY26JANFUT",
  "timestamp": "2026-01-18T16:38:22.929242+05:30",
  "indicators": {
    "rsi_14": 52.79,
    "macd_value": -3.29,
    "bollinger_upper": 59931.37,
    "adx_14": 7.87
  }
}
```

### News API

**Base URL**: `http://localhost:8005`

**GET /health**
- **Purpose**: Health check
- **Response**: `{"status": "healthy", "service": "news_api"}`

**GET /api/v1/news/{instrument}**
- **Purpose**: Get news articles for instrument
- **Response**:
```json
[
  {
    "title": "Market Update",
    "content": "Article content...",
    "timestamp": "2026-01-18T16:38:22.929242+05:30",
    "sentiment": 0.2
  }
]
```

### Engine API

**Base URL**: `http://localhost:8006`

**GET /health**
- **Purpose**: Health check
- **Response**: `{"status": "healthy", "service": "engine_api"}`

**POST /api/v1/analyze**
- **Purpose**: Request trading analysis
- **Request**:
```json
{
  "instrument": "BANKNIFTY26JANFUT",
  "context": {}
}
```
- **Response**:
```json
{
  "type": "orchestrator_decision",
  "timestamp": "2026-01-18T16:38:37.829598",
  "instrument": "BANKNIFTY26JANFUT",
  "final_decision": "HOLD",
  "confidence": 0.3,
  "reasoning": "Analysis complete",
  "agent_responses": [...],
  "signal_created": false
}
```

## Component Communication

### Redis Pub/Sub Channels

**Market Data Updates**:
- `market:ohlc:{instrument}:{timeframe}` - OHLC bar updates
- `market:tick:{instrument}` - Tick data updates

**Engine Decisions**:
- `engine:orchestrator_decision` - General orchestrator decisions
- `engine:orchestrator_decision:{instrument}` - Instrument-specific decisions

**Indicators Updates**:
- `indicators:{instrument}:INDEX` - Index instrument indicators
- `indicators:{instrument}:FUT` - Futures instrument indicators
- `indicators:{instrument}:OPT` - Options instrument indicators

### WebSocket Communication

**Dashboard UI** (`ws://localhost:8888`):
```json
{
  "type": "market_data",
  "instrument": "BANKNIFTY26JANFUT",
  "data": {
    "tick": {...},
    "indicators": {...},
    "ohlc": {...}
  }
}
```

**WebSocket Gateway** (`ws://localhost:8889`):
- Forwards Redis pub/sub messages to WebSocket clients
- Supports channel subscriptions
- Handles connection management

## Schema Validation

### Pydantic Models

```python
from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime

class OHLCBar(BaseModel):
    instrument: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    start_at: Optional[datetime]

    @validator('high', 'low', 'open', 'close')
    def price_must_be_positive(cls, v):
        if v < 0:
            raise ValueError('Price must be positive')
        return v

    @validator('high')
    def high_must_be_max(cls, v, values):
        if 'low' in values and v < values['low']:
            raise ValueError('High must be >= low')
        return v

class TechnicalIndicators(BaseModel):
    timestamp: datetime
    instrument: str
    current_price: float
    timeframe: str = "1min"

    # Trend indicators
    rsi_14: Optional[float] = None
    macd_value: Optional[float] = None
    macd_signal: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_lower: Optional[float] = None
    adx_14: Optional[float] = None

    @validator('rsi_14')
    def rsi_range(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('RSI must be between 0 and 100')
        return v
```

### JSON Schema Validation

```python
import jsonschema

OHLC_SCHEMA = {
    "type": "object",
    "properties": {
        "instrument": {"type": "string", "pattern": "^[A-Z0-9_]+$"},
        "timeframe": {"type": "string", "enum": ["1min", "5min", "15min", "1h", "1d"]},
        "timestamp": {"type": "string", "format": "date-time"},
        "open": {"type": "number", "minimum": 0},
        "high": {"type": "number", "minimum": 0},
        "low": {"type": "number", "minimum": 0},
        "close": {"type": "number", "minimum": 0},
        "volume": {"type": "integer", "minimum": 0}
    },
    "required": ["instrument", "timeframe", "timestamp", "open", "high", "low", "close"]
}

def validate_ohlc_data(data: dict) -> bool:
    """Validate OHLC data against schema."""
    try:
        jsonschema.validate(data, OHLC_SCHEMA)
        return True
    except jsonschema.ValidationError:
        return False
```

## Error Handling Contracts

### HTTP Status Codes

- `200`: Success
- `400`: Bad Request (invalid parameters)
- `404`: Not Found (instrument/data not available)
- `422`: Validation Error (schema violation)
- `500`: Internal Server Error
- `503`: Service Unavailable (circuit breaker open)

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid instrument symbol",
    "details": {
      "field": "instrument",
      "value": "invalid_symbol",
      "expected": "Valid trading symbol"
    }
  },
  "timestamp": "2026-01-18T16:38:22.929242+05:30"
}
```

### Circuit Breaker States

- **CLOSED**: Normal operation
- **OPEN**: Failing, requests blocked
- **HALF_OPEN**: Testing recovery

### Fallback Responses

When services are unavailable, fallback responses provide minimal functionality:

```json
{
  "status": "service_unavailable",
  "message": "Service temporarily unavailable, using cached data",
  "timestamp": "2026-01-18T16:38:22.929242+05:30",
  "data": {
    "cached": true,
    "last_update": "2026-01-18T16:38:22.929242+05:30"
  }
}
```

## Component Dependencies

### Market Data API Dependencies

**Required Services**:
- Redis (primary data store)
- Technical Indicators Service (calculation engine)

**Optional Services**:
- News API (for market sentiment)
- Engine API (for trading signals)

### Engine API Dependencies

**Required Services**:
- Redis (data access)
- Market Data API (OHLC data)

**Optional Services**:
- News API (sentiment analysis)
- External LLM providers (AI analysis)

### Dashboard Dependencies

**Required Services**:
- Market Data API
- WebSocket Gateway

**Optional Services**:
- Engine API (trading signals)
- News API (market news)

## Monitoring and Health Checks

### Health Check Endpoints

Each service provides health check endpoints that validate:
1. Service availability
2. Dependency connectivity
3. Data integrity
4. Performance metrics

### Monitoring Metrics

**System Metrics**:
- Response times
- Error rates
- Data freshness
- Memory usage
- CPU utilization

**Business Metrics**:
- Active instruments
- Trading signals generated
- Data update frequency
- User session counts

## Data Retention Policies

### Short-term Data (Redis)
- OHLC bars: 24 hours
- Tick data: 1 hour
- Indicators: 5 minutes
- Session data: 24 hours

### Long-term Data (MongoDB)
- Trading decisions: Indefinite
- Historical signals: Indefinite
- Performance metrics: 90 days
- Audit logs: 1 year

## Dashboard UI Configuration

### Environment Variables

The React dashboard UI uses the following environment variables:

```bash
# Trading instrument (must match backend configuration)
VITE_INSTRUMENT_SYMBOL=BANKNIFTY26JANFUT

# API endpoints
VITE_API_BASE_URL=http://localhost:8000
VITE_MARKET_DATA_API_URL=http://localhost:8004
VITE_NEWS_API_URL=http://localhost:8005
VITE_ENGINE_API_URL=http://localhost:8006
VITE_USER_API_URL=http://localhost:8007

# WebSocket configuration
VITE_WS_URL=ws://localhost:8889/ws

# Dashboard settings
VITE_DASHBOARD_TITLE=Zerodha Trading System
VITE_DEFAULT_TIMEFRAME=1min
```

### Configuration File

Create `config.env` in the `dashboard/modular_ui/` directory:

```bash
# Example config.env
VITE_INSTRUMENT_SYMBOL=BANKNIFTY26JANFUT
VITE_WS_URL=ws://localhost:8889/ws
VITE_API_BASE_URL=http://localhost:8000
```

### UI Component Behavior

**Instrument Symbol Resolution:**
- UI components read `VITE_INSTRUMENT_SYMBOL` from environment
- Falls back to `BANKNIFTY26JANFUT` if not configured
- Must match the backend `INSTRUMENT_SYMBOL` in `config.py`

**API Calls:**
- All API calls use the configured instrument symbol
- Redux state keys use the instrument symbol as object property
- WebSocket subscriptions include instrument-specific channels

## Version Compatibility

### API Versioning
- URL-based versioning: `/api/v1/`
- Backward compatibility maintained for 2 major versions
- Deprecation notices provided 3 months before removal

### Data Format Versions
- Current format version: `2.0`
- Migration support for versions: `1.0` → `2.0`
- Automatic data migration on startup

### UI Configuration Versions
- Environment variable support added in v2.1
- Backward compatibility with hardcoded values maintained
- Configuration file support for easier deployment

## Troubleshooting

### Common UI Issues

**404 Errors on API Calls:**
- Check `VITE_INSTRUMENT_SYMBOL` matches backend configuration
- Verify API endpoints are accessible
- Check browser network tab for exact failing URLs

**WebSocket Connection Issues:**
- Verify `VITE_WS_URL` points to correct WebSocket gateway
- Check WebSocket gateway is running on port 8889
- Review browser console for connection errors

**No Data Display:**
- Confirm instrument symbol configuration matches
- Check Redux state in browser dev tools
- Verify WebSocket messages are being received
- Check API responses in network tab

**Environment Variables Not Loading:**
- Ensure `config.env` exists in `dashboard/modular_ui/`
- Restart Vite dev server after config changes
- Check browser console for environment variable values

This document serves as the contract for all component interactions. Any changes to interfaces, schemas, or contracts must be reflected here and communicated to all dependent components.