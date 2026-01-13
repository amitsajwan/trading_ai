# Realtime Integration Plan: SignalMonitor → WS → Frontend

## Executive Summary

This design document outlines the end-to-end real-time integration between the SignalMonitor, Redis WebSocket Gateway, and React frontend. The goal is to achieve sub-500ms latency for signal updates while maintaining system reliability and graceful degradation.

**Key Components:**
- **SignalMonitor**: Evaluates trading conditions on every market tick
- **Redis Pub/Sub**: Message bus for real-time data distribution
- **WebSocket Gateway**: Dumb forwarder from Redis to WebSocket clients
- **React Frontend**: Real-time UI updates via WebSocket

**Latency Target:** <500ms end-to-end (market tick → UI update)
**Reliability:** 99.9% uptime with automatic reconnection and fallback polling

---

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Market Data   │    │ SignalMonitor   │    │   Redis Pub/Sub │    │   WS Gateway    │
│   Collectors    │────│   (Engine)      │────│                 │────│   (FastAPI)     │
│                 │    │                 │    │                 │    │                 │
│ • Live ticks    │    │ • Condition     │    │ • engine:signal │    │ • WebSocket     │
│ • Historical    │    │   evaluation    │    │ • market:tick   │    │   clients       │
│   replay        │    │ • Trade exec    │    │ • indicators:*  │    │ • ACL/rate      │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
                                                                          │
                                                                          ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React App     │    │   Redux Store   │    │   useWebSocket  │    │   RTK Query     │
│   (Dashboard)   │────│   (State)       │────│   Hook          │────│   (API Layer)   │
│                 │    │                 │    │                 │    │                 │
│ • Real-time     │    │ • Signal state  │    │ • WS connection │    │ • REST fallback │
│   updates       │    │ • Market data   │    │ • Auto-reconnect│    │ • Error handling│
│ • UI feedback   │    │ • Notifications │    │ • Debouncing    │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## Message Flow Design

### 1. Signal Creation Flow

**Sequence Diagram:**
```
Agent Analysis → Signal Creator → MongoDB → Redis Pub/Sub → WS Gateway → Frontend

1. Agent completes 15-min analysis cycle
2. create_signals_from_decision() generates TradingCondition
3. save_signal_to_mongodb() stores signal + publishes to Redis
4. Redis publishes: "engine:signal" + "engine:signal:{instrument}"
5. WS Gateway forwards to subscribed clients
6. Frontend receives → Redux update → UI refresh
```

**Message Format:**
```json
{
  "type": "data",
  "seq": 12345,
  "channel": "engine:signal:BANKNIFTY",
  "data": {
    "signal_id": "BANKNIFTY_BUY_rsi_oversold_001",
    "condition_id": "BANKNIFTY_BUY_rsi_oversold_001",
    "instrument": "BANKNIFTY",
    "action": "BUY",
    "indicator": "rsi_14",
    "operator": "LESS_THAN",
    "threshold": 32.0,
    "confidence": 0.75,
    "status": "pending",
    "created_at": "2024-01-10T10:30:00Z",
    "expires_at": "2024-01-10T10:45:00Z"
  },
  "timestamp": "2024-01-10T10:30:00.123Z"
}
```

### 2. Real-time Signal Monitoring Flow

**Sequence Diagram:**
```
Market Tick → Indicators Service → SignalMonitor → Trade Execution → Redis → WS → UI

1. Market tick arrives (100-200ms intervals)
2. TechnicalIndicatorsService.update_indicators()
3. Redis publishes: "indicators:{instrument}" with updated values
4. SignalMonitor.check_signals() evaluates all active conditions
5. Condition met → SignalTriggerEvent → trade execution
6. Signal status update → Redis publish → WS forward → UI update
```

**Indicator Update Message:**
```json
{
  "type": "data",
  "channel": "indicators:BANKNIFTY",
  "data": {
    "rsi_14": 28.5,
    "macd_value": -15.2,
    "sma_20": 45120.0,
    "current_price": 44950.0,
    "timestamp": "2024-01-10T10:30:01.500Z"
  }
}
```

**Signal Trigger Message:**
```json
{
  "type": "data",
  "channel": "engine:signal",
  "data": {
    "signal_id": "BANKNIFTY_BUY_rsi_oversold_001",
    "status": "triggered",
    "triggered_at": "2024-01-10T10:30:01.750Z",
    "indicator_value": 28.5,
    "current_price": 44950.0,
    "executed": true
  }
}
```

### 3. Market Data Flow

**Sequence Diagram:**
```
Market Data → Redis Store → Redis Pub/Sub → WS Gateway → Frontend

1. Live market data arrives from Zerodha Kite
2. RedisMarketStore publishes tick data
3. Redis publishes: "market:tick" + "market:tick:{instrument}"
4. WS Gateway forwards to subscribed clients
5. Frontend updates tick data → UI refresh (debounced)
```

**Market Tick Message:**
```json
{
  "type": "data",
  "channel": "market:tick:BANKNIFTY",
  "data": {
    "instrument": "BANKNIFTY",
    "last_price": 44950.0,
    "timestamp": "2024-01-10T10:30:02.000Z",
    "volume": 1250000,
    "oi": 890000
  }
}
```

---

## WebSocket Bridge Implementation

### Server-Side (Redis WebSocket Gateway)

**Configuration:**
```python
# Environment variables
REDIS_WS_GATEWAY_PORT=8889
REDIS_HOST=localhost
REDIS_PORT=6379
MAX_CHANNELS_PER_CLIENT=50
MAX_WILDCARD_SUBSCRIPTIONS=5
MAX_MESSAGES_PER_SECOND=1000
REQUIRE_AUTH=false  # For development
```

**Channel ACL (Role-Based Access):**
```python
CHANNEL_ACL = {
    "user": [
        "market:tick:*",      # Market data
        "engine:signal:*",    # Trading signals
        "engine:decision:*",  # Agent decisions
        "indicators:*",       # Technical indicators
    ],
    "admin": [
        "*",  # All channels
    ]
}
```

**Guardrails:**
- **Rate Limiting:** 1000 messages/second per client
- **Channel Limits:** 50 channels + 5 wildcards per client
- **Message Size:** 64KB max per message
- **Connection Timeout:** 30 seconds ping/pong

### Client-Side (React Frontend)

**WebSocket Hook (useWebSocket.tsx):**
```typescript
const WS_URL = 'ws://localhost:8889/ws'
const RECONNECT_ATTEMPTS = 10
const BACKOFF_BASE = 1000  // ms
const HEARTBEAT_INTERVAL = 20000  // 20s
const DEBOUNCE_DELAY = 100  // 100ms for tick updates
```

**Subscription Strategy:**
```typescript
// On dashboard load
subscribe([
  'market:tick:BANKNIFTY',
  'engine:signal:BANKNIFTY',
  'engine:decision',
  'indicators:BANKNIFTY'
])
```

**Reconnection Logic:**
```typescript
// Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s max
const backoff = (attempt) => Math.min(30000, 1000 * Math.pow(2, attempt))
```

---

## Backpressure and Heartbeat Rules

### Heartbeat Protocol

**Client → Server (Ping):**
```json
{
  "action": "ping",
  "requestId": "ping-1704882600000",
  "timestamp": "2024-01-10T10:30:00Z"
}
```

**Server → Client (Pong):**
```json
{
  "type": "pong",
  "requestId": "ping-1704882600000",
  "timestamp": "2024-01-10T10:30:00.050Z"
}
```

**Rules:**
- Ping every 20 seconds
- Pong timeout: 5 seconds
- 3 missed pongs → reconnection
- Latency tracking for monitoring

### Backpressure Handling

**Server-Side:**
- Monitor queue depth per client
- Drop messages if queue > 100
- Rate limit: 1000 msg/sec per client
- Priority: signals > ticks > indicators

**Client-Side:**
- Debounce rapid updates (100ms for ticks)
- Queue processing with microtask scheduling
- Memory limits: max 1000 queued messages
- Graceful degradation: drop non-critical updates

---

## Integration Points

### SignalMonitor → Redis Bridge

**Current Implementation:**
```python
# In signal_creator.py
redis_client.publish("engine:signal", json.dumps(signal_dict))
redis_client.publish(f"engine:signal:{signal.instrument}", json.dumps(signal_dict))
```

**Enhanced Implementation:**
```python
async def publish_signal_update(signal: TradingCondition, action: str):
    """Publish signal lifecycle events to Redis.
    
    Args:
        signal: TradingCondition object
        action: 'created' | 'triggered' | 'executed' | 'expired'
    """
    payload = {
        "signal_id": signal.condition_id,
        "instrument": signal.instrument,
        "action": signal.action,
        "status": action,
        "timestamp": datetime.now().isoformat(),
        # Include relevant fields based on action
    }
    
    redis_client.publish("engine:signal", json.dumps(payload))
    redis_client.publish(f"engine:signal:{signal.instrument}", json.dumps(payload))
```

### Technical Indicators → SignalMonitor Bridge

**Current Implementation:**
```python
# In realtime_signal_integration.py
async def on_tick(self, instrument: str, tick: Dict[str, Any]):
    # Update indicators
    self.technical_service.update_indicators(instrument, tick)
    
    # Check signals
    triggered = await self.signal_monitor.check_signals(instrument)
    
    return {
        "processed": True,
        "triggered_signals": len(triggered),
        "indicators_updated": True
    }
```

**Integration Points:**
- Called on every market tick (100-200ms)
- Updates indicators → checks conditions → executes trades
- Publishes results to Redis for UI updates

---

## Failure Modes and Recovery

### 1. WebSocket Connection Loss

**Detection:**
- Ping/pong heartbeat fails
- Connection close event received

**Recovery:**
- Exponential backoff reconnection (1s → 30s max)
- Resubscribe to all channels on reconnect
- Show "Reconnecting..." indicator in UI
- Fallback to polling after 10 failed attempts

**UI Behavior:**
```typescript
// Connection states
enum WSState {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  RECONNECTING = 'reconnecting',
  DISCONNECTED = 'disconnected'
}
```

### 2. Redis Pub/Sub Failure

**Detection:**
- Publish operations fail
- Subscriber connection drops

**Recovery:**
- Automatic reconnection with retry
- Queue messages during outage (max 1000)
- Flush queue when reconnected
- Alert monitoring system

### 3. SignalMonitor Failure

**Detection:**
- Exception in check_signals()
- Technical service unavailable

**Recovery:**
- Continue processing ticks (don't block)
- Log errors for monitoring
- Graceful degradation (skip signal checking)
- Alert when service recovers

### 4. High Load Scenarios

**Backpressure:**
- Drop non-critical messages (indicators before ticks)
- Reduce update frequency (500ms → 1000ms)
- Show "High load - reduced updates" warning

**Client-Side:**
- Debounce all updates (100ms minimum)
- Virtual scrolling for large lists
- Progressive loading of components

---

## Testing Strategy

### Unit Tests

**WebSocket Gateway:**
```python
def test_channel_acl():
    # Test role-based access control
    assert gateway.can_subscribe("user", "market:tick:BANKNIFTY") == True
    assert gateway.can_subscribe("user", "admin:internal") == False

def test_rate_limiting():
    # Test message rate limiting
    for i in range(1001):
        assert gateway.check_rate_limit(client_id) == (i < 1000)
```

**SignalMonitor:**
```python
def test_condition_evaluation():
    condition = TradingCondition(
        indicator="rsi_14",
        operator=LESS_THAN,
        threshold=30.0
    )
    indicators = {"rsi_14": 25.0}
    assert monitor._evaluate_condition(condition, indicators) == True
```

### Integration Tests

**End-to-End Flow:**
```python
async def test_signal_to_ui_flow():
    # 1. Create signal via API
    signal = await create_test_signal()
    
    # 2. Verify Redis publish
    published = redis_client.get_published_messages("engine:signal")
    assert len(published) == 1
    
    # 3. Verify WS Gateway forward
    ws_client = await connect_test_ws()
    messages = await ws_client.receive_messages(timeout=5.0)
    assert len(messages) == 1
    assert messages[0]["channel"] == "engine:signal"
    
    # 4. Verify UI update (mock frontend)
    ui_state = await get_ui_signal_state()
    assert signal.condition_id in ui_state["signals"]
```

**Load Testing:**
```python
async def test_high_frequency_updates():
    # Simulate 100 ticks/second
    for i in range(1000):
        await process_tick({"price": 45000 + i, "timestamp": "..."})
    
    # Verify no message loss
    assert len(ws_messages) >= 900  # Allow some backpressure drops
    
    # Verify UI debouncing
    assert len(ui_updates) <= 100  # Max 10 updates/sec
```

### Performance Benchmarks

**Latency Targets:**
- Market tick → UI update: <500ms
- Signal creation → UI: <200ms
- WebSocket reconnect: <5 seconds
- Redis publish: <10ms

**Throughput Targets:**
- 1000 ticks/second processing
- 100 concurrent WebSocket clients
- 99.9% message delivery rate

---

## Monitoring and Observability

### Metrics to Track

**WebSocket Gateway:**
- Connection count by role
- Messages per second per client
- Channel subscription counts
- Reconnection attempts
- Message drop rate

**SignalMonitor:**
- Signals processed per second
- Condition evaluation time
- Trigger rate (signals/minute)
- Execution success rate

**Frontend:**
- WebSocket connection state
- Message processing latency
- Redux update frequency
- UI render performance

### Alerting Rules

**Critical Alerts:**
- WebSocket gateway down (>5 min)
- Redis pub/sub unavailable (>1 min)
- Signal processing backlog (>100 pending)
- Message delivery rate <95%

**Warning Alerts:**
- High latency (>1000ms end-to-end)
- Connection drops (>10/min)
- Memory usage >80%
- CPU usage >70%

---

## Deployment and Configuration

### Environment Variables

**WebSocket Gateway:**
```bash
REDIS_WS_GATEWAY_PORT=8889
REDIS_HOST=localhost
REDIS_PORT=6379
MAX_CHANNELS_PER_CLIENT=50
MAX_WILDCARD_SUBSCRIPTIONS=5
MAX_MESSAGES_PER_SECOND=1000
REQUIRE_AUTH=false
DEFAULT_ROLE=user
```

**Frontend:**
```bash
VITE_WS_URL=ws://localhost:8889/ws
VITE_API_URL=http://localhost:8888
VITE_RECONNECT_ATTEMPTS=10
VITE_HEARTBEAT_INTERVAL=20000
```

### Startup Sequence

1. **Redis Server** (port 6379)
2. **MongoDB** (for signal persistence)
3. **Engine Module** (SignalMonitor initialization)
4. **WebSocket Gateway** (port 8889)
5. **Dashboard API** (port 8888)
6. **Frontend** (Vite dev server or build)

### Health Checks

**WebSocket Gateway:**
```bash
curl http://localhost:8889/health
# Returns: {"status": "healthy", "connections": 5, "redis": "connected"}
```

**Frontend:**
```typescript
// WebSocket health indicator
const isHealthy = ws.connected && ws.lastPong < 30000
```

---

## Migration Strategy

### Phase 1: Infrastructure Setup (Week 1)
- Deploy Redis WebSocket Gateway
- Configure channel ACLs
- Set up monitoring and alerting
- Test basic pub/sub forwarding

### Phase 2: Signal Integration (Week 2)
- Connect SignalMonitor to Redis publishing
- Implement signal lifecycle events
- Test end-to-end signal flow
- Add signal status updates

### Phase 3: Frontend Integration (Week 3)
- Implement WebSocket hook reconnection
- Add Redux real-time updates
- Test UI responsiveness
- Implement graceful degradation

### Phase 4: Production Optimization (Week 4)
- Performance tuning and load testing
- Add comprehensive error handling
- Implement monitoring dashboards
- Production deployment and validation

---

## Risk Mitigation

### Technical Risks

**High Latency:**
- **Mitigation:** Optimize Redis pub/sub, implement message batching, use WebSocket compression
- **Fallback:** Polling API for critical data

**Message Loss:**
- **Mitigation:** Implement message acknowledgments, persistent queues, delivery guarantees
- **Detection:** Sequence number tracking, gap detection

**Connection Instability:**
- **Mitigation:** Exponential backoff, connection pooling, multiple gateway instances
- **Fallback:** REST API polling when WebSocket fails

### Operational Risks

**Single Point of Failure:**
- **Mitigation:** Redis cluster, multiple gateway instances, load balancing
- **Monitoring:** Health checks every 30 seconds

**Resource Exhaustion:**
- **Mitigation:** Rate limiting, connection limits, memory monitoring
- **Auto-scaling:** Horizontal scaling based on connection count

**Security Vulnerabilities:**
- **Mitigation:** Input validation, rate limiting, authentication
- **Auditing:** Regular security reviews, dependency updates

---

*This design document provides the complete technical specification for real-time WebSocket integration. Implementation should follow the phased approach with comprehensive testing at each stage.*</content>
<parameter name="filePath">c:\code\zerodha\REALTIME_INTEGRATION_PLAN.md