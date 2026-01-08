# Engine API Contract

## Base URL
`http://localhost:8006`

## Health Check

### GET /health
Check service health and dependencies.

**Response:**
```json
{
  "status": "healthy" | "degraded",
  "module": "engine",
  "timestamp": "2024-01-01T00:00:00",
  "dependencies": {
    "redis": "healthy" | "unhealthy",
    "mongodb": "healthy" | "unhealthy",
    "orchestrator": "initialized" | "not_initialized"
  }
}
```

## Analysis Endpoints

### POST /api/v1/analyze
Run orchestrator analysis cycle.

**Request Body:**
```json
{
  "instrument": "BANKNIFTY",
  "context": {
    "market_hours": true,
    "additional_params": "value"
  }
}
```

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "decision": "BUY" | "SELL" | "HOLD",
  "confidence": 0.85,
  "details": {
    "agent_analysis": {},
    "technical_indicators": {}
  },
  "timestamp": "2024-01-01T00:00:00"
}
```

## Signals Endpoints

### GET /api/v1/signals/{instrument}
Get recent trading signals for an instrument.

**Parameters:**
- `instrument` (path): Instrument symbol
- `limit` (query, optional): Maximum number of signals (default: 10)

**Response:**
```json
[
  {
    "signal_id": "507f1f77bcf86cd799439011",
    "instrument": "BANKNIFTY",
    "action": "BUY",
    "confidence": 0.85,
    "reasoning": "Strong momentum with volume confirmation",
    "timestamp": "2024-01-01T00:00:00"
  }
]
```

## Orchestrator Endpoints

### POST /api/v1/orchestrator/initialize
Initialize orchestrator with dependencies.

**Request Body:**
```json
{
  "llm_config": {},
  "market_store_config": {},
  "options_data_config": {}
}
```

**Response:**
```json
{
  "status": "info",
  "message": "Orchestrator initialization requires proper dependency injection...",
  "timestamp": "2024-01-01T00:00:00"
}
```

## Error Responses

All endpoints may return:
- `500`: Internal server error
- `503`: Service unavailable (orchestrator not initialized)

