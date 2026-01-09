# UI Architecture Analysis & Proposed Improvements

## Current Architecture Analysis

### Current Data Flow

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Modules   │────────►│    Redis     │────────►│ Socket.IO   │
│ (Market,    │ publish │  Pub/Sub     │ subscribe│  Servers    │
│  Engine)    │         │  Channels    │         │ (in APIs)   │
└─────────────┘         └──────────────┘         └──────┬──────┘
                                                          │
                                                          │ forward
                                                          ▼
                                                   ┌─────────────┐
                                                   │     UI      │
                                                   │ (React App) │
                                                   └─────────────┘
```

### Current Redis Pub/Sub Channels

1. **Market Data Channels:**
   - `market:tick:*` - Instrument-specific ticks (e.g., `market:tick:BANKNIFTY`)
   - `market:tick` - General tick channel
   - `indicators:{instrument}` - Technical indicators (RSI, MACD, etc.)

2. **Engine Channels:**
   - `engine:signal:*` - Instrument-specific signals (e.g., `engine:signal:BANKNIFTY`)
   - `engine:signal` - General signal channel
   - `engine:decision:*` - Instrument-specific decisions
   - `engine:decision` - General decision channel

### Current UI Connection Methods

#### Real-Time Data (via Socket.IO)
- **WebSocket Connection:** `ws://localhost:8888/socket.io/` (proxied to Market Data API port 8004)
- **Events Received:**
  - `tick_update` - Market tick updates
  - `signal_update` - Trading signal updates
  - `decision_update` - Agent decision updates
  - `portfolio_update` - Portfolio changes
  - `trade_executed` - Trade execution notifications

#### REST API Calls (via HTTP)
- **Market Data APIs:**
  - `GET /api/market-data/tick/{instrument}` - Get latest tick
  - `GET /api/market-data/ohlc/{instrument}` - Get OHLC data
  - `GET /api/market-data/options/chain/{instrument}` - Options chain
  - `GET /api/market-data` - Market overview
  - `GET /api/technical-indicators?symbol={instrument}` - Technical indicators

- **Engine APIs:**
  - `GET /api/engine/decision/latest` - Latest decision
  - `GET /api/engine/portfolio` - Portfolio status
  - `GET /api/engine/trades` - Recent trades
  - `GET /api/engine/agents/status` - Agent status
  - `GET /api/trading/signals?instrument={instrument}` - Trading signals
  - `GET /api/options-strategy-agent` - Options strategy

- **Trading APIs:**
  - `POST /api/trading/execute` - Execute trade
  - `POST /api/trading/execute-when-ready/{signalId}` - Conditional execution
  - `GET /api/trading/positions` - Get positions
  - `POST /api/trading/close/{positionId}` - Close position

- **News APIs:**
  - `GET /api/news/articles` - News articles
  - `GET /api/news/sentiment/{instrument}` - Sentiment analysis

### Current Issues

1. **Extra Hop:** Data flows: Module → Redis → Socket.IO Server → UI (3 hops)
2. **API Server Load:** Socket.IO servers in API modules add unnecessary load
3. **Latency:** Additional processing layer increases latency
4. **Complexity:** Multiple Socket.IO servers (Market Data API, Engine API) need coordination
5. **Scalability:** API servers become bottlenecks for real-time data

---

## Proposed Architecture

### New Data Flow

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Modules   │────────►│    Redis     │◄─────────│ Redis WS     │
│ (Market,    │ publish │  Pub/Sub     │ subscribe│  Gateway     │
│  Engine)    │         │  Channels    │          │  (New)       │
└─────────────┘         └──────────────┘          └──────┬──────┘
                                                           │
                                                           │ WebSocket
                                                           │ (direct)
                                                           ▼
                                                    ┌─────────────┐
                                                    │     UI      │
                                                    │ (React App) │
                                                    └─────────────┘

For Historical Data & Actions:
┌─────────────┐
│   Modules   │────────►┌─────────────┐
│ (Market,    │  REST   │     UI      │
│  Engine)    │  APIs   │ (React App) │
└─────────────┘         └─────────────┘
```

### Architecture Principles

1. **Real-Time Data:** UI connects directly to Redis via WebSocket gateway
   - No API server in the path
   - Lower latency
   - Better scalability

2. **Historical Data:** UI uses REST APIs from modules
   - On-demand data fetching
   - Cached/aggregated data
   - Complex queries

3. **Actions:** UI uses REST APIs from modules
   - Trade execution
   - Signal management
   - Configuration changes

### Benefits

✅ **Reduced Latency:** Direct Redis connection eliminates API server hop  
✅ **Better Scalability:** API servers not burdened with real-time forwarding  
✅ **Cleaner Separation:** Real-time = Redis, Historical/Actions = APIs  
✅ **Simpler Architecture:** Single WebSocket gateway instead of multiple Socket.IO servers  
✅ **Better Resource Usage:** API servers focus on business logic, not data forwarding  

---

## Implementation Plan

### Phase 1: Create Redis WebSocket Gateway

**New Service:** `redis_ws_gateway` (or add to dashboard module)

**Responsibilities:**
- Accept WebSocket connections from UI
- Authenticate connections (JWT/API key)
- Subscribe to Redis pub/sub channels
- Forward Redis messages to connected WebSocket clients
- Handle client subscriptions/unsubscriptions
- Manage connection lifecycle
- Enforce channel access control (ACL)
- Rate limiting and guardrails

**⚠️ Critical Principle: Gateway Must Be Dumb**

The gateway should **NOT**:
- ❌ Aggregate data
- ❌ Enrich messages
- ❌ Apply business rules
- ❌ Filter indicators logic

The gateway should **ONLY**:
- ✅ Authenticate
- ✅ Subscribe/forward
- ✅ Throttle
- ✅ Enforce ACLs

> **Treat the gateway like Nginx for Redis events.** If logic creeps in, you'll recreate the same bottleneck under a new name.

**Technology:**
- Python with `websockets` library
- Or Node.js with `ws` and `redis` libraries
- Or FastAPI with WebSocket support

### Phase 2: Update UI to Use Direct Redis WebSocket

**Changes:**
- Replace Socket.IO client with native WebSocket client
- Connect to Redis WebSocket gateway
- Subscribe to Redis channels directly
- Handle Redis message format
- **Implement explicit reconnection logic:**
  - Ping/pong heartbeat
  - Exponential backoff on reconnect
  - Automatic resubscription on reconnect
  - Gap detection using sequence IDs

**⚠️ Important:** Socket.IO hides reconnection complexity. With raw WebSocket, you must implement:
- Explicit ping/pong for connection health
- Exponential backoff (e.g., 1s, 2s, 4s, 8s, max 30s)
- Resubscribe to all channels after reconnection
- Track last sequence ID to detect gaps

### Phase 3: Keep REST APIs for Historical/Actions

**No Changes Needed:**
- All REST API endpoints remain unchanged
- UI continues using them for:
  - Historical data queries
  - Trade execution
  - Configuration
  - Analytics

### Phase 4: Deprecate Socket.IO Servers

**Cleanup:**
- Remove Socket.IO servers from Market Data API
- Remove Socket.IO servers from Engine API
- Keep REST APIs intact

---

## Redis WebSocket Gateway Design

### Connection Flow

```
1. UI connects to WebSocket gateway (ws://localhost:8889/ws)
2. Gateway authenticates (optional) and accepts connection
3. UI sends subscription messages:
   {
     "action": "subscribe",
     "channels": ["market:tick:BANKNIFTY", "engine:signal:*", "indicators:BANKNIFTY"]
   }
4. Gateway subscribes to Redis pub/sub channels
5. Gateway forwards Redis messages to UI as WebSocket messages
6. UI processes messages and updates state
```

### Message Format

**From UI to Gateway:**
```json
{
  "action": "subscribe|unsubscribe|ping",
  "channels": ["channel1", "channel2", "pattern:*"],
  "requestId": "optional-id-for-response-matching"
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
  "requestId": "optional-id-if-response-to-request"
}
```

**Note:** Sequence IDs (`seq`) are critical for:
- Detecting message gaps
- Debugging latency and drops
- Enabling replay logic later
- Minimal cost, significant debugging value

### Supported Redis Channel Patterns

- `market:tick:*` - All instrument ticks
- `market:tick:{instrument}` - Specific instrument ticks
- `engine:signal:*` - All signals
- `engine:signal:{instrument}` - Specific instrument signals
- `engine:decision:*` - All decisions
- `engine:decision:{instrument}` - Specific instrument decisions
- `indicators:{instrument}` - Technical indicators for instrument

### Pattern Subscription Guardrails

**⚠️ Critical:** Pattern subscriptions can explode memory and CPU if not controlled.

**Safeguards to implement:**
- **Max channels per connection:** e.g., 50 channels max
- **Max wildcard subscriptions:** e.g., 5 pattern subscriptions max
- **Server-side allowlist:** Role-based channel access
  - Example: `market:*` allowed for all users
  - Example: `engine:*` restricted to admin users
  - Example: `internal:*` blocked for UI users

**Why:** If a client subscribes to many wildcards:
- Redis creates many pattern subscriptions
- Gateway fan-out cost increases exponentially
- Memory usage grows unbounded

---

## Migration Strategy

### Step 1: Add Redis WebSocket Gateway (Non-Breaking)
- Create new service alongside existing Socket.IO servers
- UI can optionally use new gateway
- Both systems run in parallel

### Step 2: Update UI to Support Both (Backward Compatible)
- Add new WebSocket connection option
- Feature flag to switch between Socket.IO and direct Redis
- Test both paths

### Step 3: Switch UI to Direct Redis (Breaking)
- Update UI to use Redis gateway by default
- Remove Socket.IO client code
- Monitor for issues

### Step 4: Remove Socket.IO Servers (Cleanup)
- Remove Socket.IO from Market Data API
- Remove Socket.IO from Engine API
- Clean up dependencies

---

## Technical Considerations

### Security

**Authentication (Required):**
- JWT or API key during WebSocket connection handshake
- Validate token before accepting connection
- Reject unauthenticated connections

**Access Control (Required):**
- Channel-level ACL based on user role
- Role → allowed channel prefixes mapping
  - Example: `role: "user"` → `["market:*", "indicators:*"]`
  - Example: `role: "admin"` → `["market:*", "engine:*", "indicators:*"]`
- Block access to internal/risk channels from UI
- Simple prefix-based allowlist is sufficient initially

**Rate Limiting:**
- Per-client subscription limits
- Per-client message rate limits
- Prevent DoS via excessive subscriptions

### Performance

**Gateway Implementation:**
- **Must be async** (Python asyncio, Node.js event loop, etc.)
- **Redis connection pooling** - reuse connections, don't create per client
- **No unnecessary copying** - forward messages directly, don't deserialize/reserialize
- Message batching for high-frequency channels (optional, measure first)

**Expected Performance:**
- ✅ 10k+ msgs/sec throughput
- ✅ 1k+ concurrent UI clients
- ✅ Sub-100ms end-to-end latency (local/same region)

**Only achievable if:**
- Gateway is async
- Redis connections are pooled
- Messages are not copied unnecessarily

### Reliability

**Redis Pub/Sub Limitations (Important):**

⚠️ **Redis Pub/Sub has NO persistence.**

If:
- UI disconnects
- Gateway restarts
- Network blips

👉 **Messages are lost**

**This is OK only if:**
- UI can tolerate missed ticks (can rehydrate via REST)
- REST APIs can quickly provide current state
- Signals/decisions are idempotent

**Future-Proofing (Phase B):**

For critical events that cannot be lost, consider Redis Streams:

| Use Case            | Recommended Solution |
| ------------------- | -------------------- |
| Live ticks          | Redis Pub/Sub (OK to lose) |
| Signals / decisions | Redis Streams (replayable) |
| Trades / executions | DB + Stream (audit trail) |

**Reconnection:**
- Automatic reconnection with exponential backoff
- Resubscribe to all channels after reconnect
- Track sequence IDs to detect gaps
- Health checks and monitoring

**Message Queuing:**
- Optional: Queue messages for disconnected clients (requires Streams)
- Not needed for Phase A (Pub/Sub only)

### Scalability

- Gateway can be horizontally scaled
- Load balancing for WebSocket connections (sticky sessions)
- Redis cluster support
- Each gateway instance is stateless (except active subscriptions)

---

## Two-Phase Maturity Model

### Phase A: Current Proposal (Start Here)

**Technology Stack:**
- Redis Pub/Sub for all real-time events
- WebSocket gateway (dumb forwarder)
- REST APIs for historical data and actions
- No Socket.IO

**Characteristics:**
- ✅ Simple to implement
- ✅ Low latency
- ✅ Good for live trading
- ⚠️ Messages lost on disconnect (acceptable for ticks)

**When to use:**
- Live trading mode
- UI can tolerate missed ticks
- REST APIs can rehydrate state quickly

### Phase B: Future Growth (When Needed)

**Technology Stack:**
- Redis Streams for signals & decisions (replayable)
- Redis Pub/Sub for high-frequency ticks (OK to lose)
- Optional message queuing for disconnected clients
- Multi-gateway scaling with metrics
- Backpressure handling

**Characteristics:**
- ✅ Message persistence
- ✅ Replay capability
- ✅ Better reliability
- ⚠️ More complex

**When to add:**
- Need to replay signals/decisions
- Cannot tolerate any message loss
- System scale requires it
- Audit/compliance requirements

---

## Questions to Consider

1. **Authentication:** ✅ **Required** - JWT/API key during connection
2. **Message Queuing:** Phase A: No (Pub/Sub only). Phase B: Yes (Streams)
3. **Rate Limiting:** ✅ **Required** - Max channels, max wildcards, per-client limits
4. **Monitoring:** Metrics for gateway performance, connection counts, message rates
5. **Historical Replay:** Phase A: Use REST APIs. Phase B: Use Redis Streams replay

---

## Recommendation

**✅ Proceed with proposed architecture**

The architecture is fundamentally correct and scalable. This is the right architectural evolution:
- Moving from **API-centric real-time delivery** to **event-centric real-time delivery**
- Mirrors how professional trading platforms work
- Removes API servers from the hot path
- Uses Pub/Sub as the system backbone

**Key Benefits:**
- Lower latency for real-time data
- Better scalability
- Cleaner separation of concerns
- Simpler overall system
- API servers focus on business logic, not data forwarding

**Critical Refinements (Must Implement):**

1. **Gateway must be dumb** - No business logic, only forward
2. **Add sequence IDs** - For gap detection and debugging
3. **Pattern subscription guardrails** - Max channels, wildcards, allowlists
4. **Explicit reconnection logic** - Ping/pong, backoff, resubscribe
5. **Security & ACL** - JWT auth, channel-level access control
6. **Async + connection pooling** - Required for performance

**Architecture Maturity:**

- **Phase A (Now):** Redis Pub/Sub + WebSocket Gateway + REST APIs
- **Phase B (Future):** Add Redis Streams for critical events, replay capability

**Next Steps:**
1. Create Redis WebSocket gateway service (dumb forwarder)
2. Implement authentication and ACL
3. Add sequence IDs to message format
4. Update UI with explicit reconnection logic
5. Test thoroughly with guardrails enabled
6. Migrate gradually (parallel run)
7. Remove old Socket.IO servers

---

## Summary

> **You're moving from API-driven real-time to event-driven real-time — that's the right architectural leap.**
> 
> **Keep the gateway dumb, add guardrails, and plan for persistence later.**
