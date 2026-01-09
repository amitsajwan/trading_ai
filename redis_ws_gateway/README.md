# Redis WebSocket Gateway

Direct Redis pub/sub to WebSocket forwarding service. This is a **dumb gateway** that only forwards messages - no business logic.

## Architecture

```
Modules → Redis Pub/Sub → Gateway → WebSocket → UI
```

The gateway:
- ✅ Accepts WebSocket connections from UI
- ✅ Authenticates connections (JWT/API key)
- ✅ Subscribes to Redis pub/sub channels on behalf of clients
- ✅ Forwards Redis messages to WebSocket clients
- ✅ Enforces guardrails (max channels, ACL, rate limiting)
- ❌ **NO business logic** - only forwards

## Features

- **Sequence IDs**: Every message includes a sequence ID for gap detection
- **Authentication**: JWT/API key support (configurable)
- **ACL**: Role-based channel access control
- **Guardrails**: Max channels, max wildcards, rate limiting
- **Reconnection**: Automatic cleanup on disconnect

## Configuration

Environment variables:

```bash
# Redis connection
REDIS_HOST=localhost
REDIS_PORT=6379

# Gateway server
REDIS_WS_GATEWAY_HOST=0.0.0.0
REDIS_WS_GATEWAY_PORT=8889

# Guardrails
MAX_CHANNELS_PER_CLIENT=50
MAX_WILDCARD_SUBSCRIPTIONS=5
MAX_MESSAGES_PER_SECOND=1000

# Authentication
REQUIRE_AUTH=false  # Set to true to require authentication
GATEWAY_API_KEY=your-api-key  # API key for admin access
DEFAULT_ROLE=user  # Default role for unauthenticated clients
```

## Usage

### Start the gateway

```bash
python -m redis_ws_gateway.main
```

Or via `start_local.py` (automatically started).

### Connect from UI

```javascript
const ws = new WebSocket('ws://localhost:8889/ws?token=your-token');

// Subscribe to channels
ws.send(JSON.stringify({
  action: 'subscribe',
  channels: ['market:tick:BANKNIFTY', 'engine:signal:*'],
  requestId: 'req-1'
}));

// Handle messages
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log('Message:', msg);
  // msg.type: 'data' | 'error' | 'pong' | 'subscribed' | 'unsubscribed'
  // msg.seq: sequence ID
  // msg.channel: channel name
  // msg.data: actual message data
};
```

### Message Format

**From UI to Gateway:**
```json
{
  "action": "subscribe|unsubscribe|ping",
  "channels": ["channel1", "pattern:*"],
  "requestId": "optional-id"
}
```

**From Gateway to UI:**
```json
{
  "type": "data|error|pong|subscribed|unsubscribed",
  "seq": 182736,
  "channel": "market:tick:BANKNIFTY",
  "data": { /* actual message data */ },
  "timestamp": "2026-01-09T10:30:00Z",
  "requestId": "optional-id"
}
```

## Supported Channels

- `market:tick:*` - All instrument ticks
- `market:tick:{instrument}` - Specific instrument ticks
- `engine:signal:*` - All signals
- `engine:signal:{instrument}` - Specific instrument signals
- `engine:decision:*` - All decisions
- `engine:decision:{instrument}` - Specific instrument decisions
- `indicators:{instrument}` - Technical indicators

## Channel ACL

Default roles and permissions:

- **user**: `market:tick:*`, `indicators:*`
- **admin**: `market:tick:*`, `engine:signal:*`, `engine:decision:*`, `indicators:*`
- **internal**: `*` (all channels)

## Health & Stats

- `GET /health` - Health check
- `GET /stats` - Gateway statistics

## Notes

- Gateway is **stateless** (except active subscriptions)
- Messages are **not persisted** (Redis Pub/Sub has no persistence)
- For message persistence, use Redis Streams (Phase B)
- Gateway can be horizontally scaled
