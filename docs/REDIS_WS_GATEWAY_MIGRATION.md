# Redis WebSocket Gateway Migration

## Overview

The system has been migrated from Socket.IO-based real-time updates to a dedicated **Redis WebSocket Gateway** that provides direct Redis pub/sub to WebSocket forwarding.

## What Changed

### Before (Socket.IO)
- Market Data API (port 8004) had Socket.IO server
- Engine API (port 8006) had Socket.IO server
- UI connected to multiple Socket.IO endpoints
- Data flow: Module → Redis → Socket.IO Server → UI (3 hops)

### After (Redis WebSocket Gateway)
- **Single Redis WebSocket Gateway** (port 8889)
- Market Data API and Engine API focus on REST endpoints only
- UI connects to single gateway endpoint
- Data flow: Module → Redis → Gateway → UI (2 hops, direct)

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Modules   │────────►│    Redis     │◄─────────│ Redis WS     │
│ (Market,    │ publish │  Pub/Sub     │ subscribe│  Gateway     │
│  Engine)    │         │  Channels    │          │  (port 8889) │
└─────────────┘         └──────────────┘          └──────┬──────┘
                                                          │
                                                          │ WebSocket
                                                          │ (direct)
                                                          ▼
                                                   ┌─────────────┐
                                                   │     UI      │
                                                   │ (React App) │
                                                   └─────────────┐
```

## Supported Redis Channels

The gateway supports all Redis pub/sub channels:

- `market:tick:*` - Instrument-specific ticks (e.g., `market:tick:BANKNIFTY`)
- `market:tick` - General tick channel
- `engine:signal:*` - Instrument-specific signals
- `engine:signal` - General signal channel
- `engine:decision:*` - Instrument-specific decisions
- `engine:decision` - General decision channel
- `indicators:{instrument}` - Technical indicators (RSI, MACD, etc.)

## Migration Steps

### 1. Gateway Service
- ✅ Created `redis_ws_gateway` module
- ✅ Integrated into `start_local.py` (Step 5.5)
- ✅ Added to `docker-compose.yml`

### 2. API Services
- ✅ Removed Socket.IO from Market Data API
- ✅ Removed Socket.IO from Engine API
- ✅ REST APIs remain unchanged

### 3. UI Configuration
- ✅ Updated `VITE_WS_URL` to `ws://localhost:8889/ws`
- ✅ UI components updated to use new gateway (handled separately)

## Gateway Features

- **Sequence IDs**: Every message includes a sequence ID for gap detection
- **Authentication**: JWT/API key support (configurable)
- **ACL**: Role-based channel access control
- **Guardrails**: Max channels, max wildcards, rate limiting
- **Dumb Forwarder**: No business logic, only forwards messages

## Configuration

Environment variables:

```bash
REDIS_WS_GATEWAY_PORT=8889
REQUIRE_AUTH=false  # Set to true for production
GATEWAY_API_KEY=your-key  # For admin access
DEFAULT_ROLE=user
MAX_CHANNELS_PER_CLIENT=50
MAX_WILDCARD_SUBSCRIPTIONS=5
```

## Usage

### Connect from UI

```javascript
const ws = new WebSocket('ws://localhost:8889/ws?token=your-token');

// Subscribe to channels
ws.send(JSON.stringify({
  action: 'subscribe',
  channels: ['market:tick:BANKNIFTY', 'engine:signal:*', 'indicators:BANKNIFTY'],
  requestId: 'req-1'
}));

// Handle messages
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  // msg.type: 'data' | 'error' | 'pong' | 'subscribed' | 'unsubscribed'
  // msg.seq: sequence ID
  // msg.channel: channel name
  // msg.data: actual message data
};
```

## Benefits

✅ **Reduced Latency**: Direct Redis connection eliminates API server hop  
✅ **Better Scalability**: API servers not burdened with real-time forwarding  
✅ **Cleaner Separation**: Real-time = Redis, Historical/Actions = APIs  
✅ **Simpler Architecture**: Single WebSocket gateway instead of multiple Socket.IO servers  
✅ **Better Resource Usage**: API servers focus on business logic, not data forwarding  

## Deprecated Files

The following files are deprecated but kept for reference:

- `market_data/src/market_data/websocket_server.py` - Socket.IO server (deprecated)
- `engine_module/src/engine_module/websocket_server.py` - Socket.IO server (deprecated)

These files are no longer used but kept for historical reference.

## Next Steps

For future enhancements, consider:

- **Phase B**: Add Redis Streams for message persistence and replay
- **Multi-gateway**: Scale gateway horizontally for high load
- **Metrics**: Add detailed performance monitoring
- **Backpressure**: Handle high message rates gracefully

See `docs/UI_ARCHITECTURE_ANALYSIS.md` for detailed architecture documentation.
