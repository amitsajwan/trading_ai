# Test Plan: End-to-End Message Flow and Failure Modes

## Overview

This test plan validates the real-time integration between SignalMonitor, Redis WebSocket Gateway, and React frontend. Tests cover normal operation, failure scenarios, and performance requirements.

**Test Environment:**
- Redis server (localhost:6379)
- WebSocket Gateway (localhost:8889)
- Dashboard API (localhost:8888)
- React frontend (localhost:3000)
- MongoDB (localhost:27017)

**Success Criteria:**
- All latency targets met (<500ms end-to-end)
- 99.9% message delivery rate
- Graceful handling of all failure modes
- Automatic recovery within specified timeouts

---

## Test Case Categories

### 1. Normal Operation Tests

#### TC-1.1: Signal Creation to UI Display
**Objective:** Verify end-to-end signal creation and display flow

**Preconditions:**
- All services running
- WebSocket connected
- Frontend subscribed to signal channels

**Steps:**
1. Create signal via API: `POST /api/trading/cycle`
2. Verify MongoDB storage
3. Verify Redis publish (intercept messages)
4. Verify WebSocket forwarding
5. Verify Redux state update
6. Verify UI display update

**Expected Results:**
- Signal appears in UI within 200ms
- All message formats correct
- No message loss

**Metrics:**
- End-to-end latency: <200ms
- Message delivery: 100%

#### TC-1.2: Real-time Signal Execution
**Objective:** Test signal trigger and trade execution flow

**Preconditions:**
- Active signal in SignalMonitor
- Market data flowing

**Steps:**
1. Send market tick that meets signal condition
2. Verify SignalMonitor evaluation
3. Verify trade execution
4. Verify status update publication
5. Verify UI execution feedback

**Expected Results:**
- Trade executed within 50ms of condition met
- UI shows execution confirmation within 100ms
- Signal status updated correctly

**Metrics:**
- Trigger latency: <50ms
- UI update latency: <100ms

#### TC-1.3: Market Data Streaming
**Objective:** Test high-frequency market data updates

**Preconditions:**
- Market data subscription active
- Historical replay running

**Steps:**
1. Start market data replay (100 ticks/sec)
2. Monitor WebSocket message rate
3. Verify UI tick updates (debounced)
4. Check for message drops or UI freezing

**Expected Results:**
- No message loss at 100 ticks/sec
- UI updates at 10 Hz max (debounced)
- No UI freezing or memory leaks

**Metrics:**
- Message delivery rate: >99.9%
- UI update frequency: 5-10 Hz
- Memory usage: stable

### 2. Failure Mode Tests

#### TC-2.1: WebSocket Connection Loss
**Objective:** Test reconnection and state recovery

**Preconditions:**
- WebSocket connected and subscribed

**Steps:**
1. Kill WebSocket gateway process
2. Verify frontend detects disconnection
3. Verify reconnection attempts (exponential backoff)
4. Restart gateway
5. Verify automatic resubscription
6. Verify message delivery resumes

**Expected Results:**
- Disconnection detected within 5s
- Reconnection successful within 30s
- All subscriptions restored
- No message loss during outage

**Metrics:**
- Detection time: <5s
- Reconnection time: <30s
- Message recovery: 100%

#### TC-2.2: Redis Pub/Sub Failure
**Objective:** Test Redis failure handling

**Preconditions:**
- All services connected to Redis

**Steps:**
1. Stop Redis server
2. Verify services handle disconnection gracefully
3. Verify message queuing during outage
4. Restart Redis
5. Verify message delivery resumes
6. Verify no data loss

**Expected Results:**
- No service crashes
- Messages queued (max 1000)
- Automatic reconnection
- All queued messages delivered

**Metrics:**
- Service stability: 100%
- Message queue depth: <1000
- Recovery time: <10s

#### TC-2.3: SignalMonitor Failure
**Objective:** Test signal processing failure handling

**Preconditions:**
- Active signals in monitor

**Steps:**
1. Inject exception in SignalMonitor.check_signals()
2. Verify processing continues (doesn't block)
3. Verify error logging
4. Verify service recovery
5. Verify signal processing resumes

**Expected Results:**
- No blocking of tick processing
- Errors logged appropriately
- Automatic recovery
- Signal processing resumes

**Metrics:**
- Processing continuity: 100%
- Error logging: complete
- Recovery time: <5s

#### TC-2.4: High Load Backpressure
**Objective:** Test system behavior under load

**Preconditions:**
- Multiple WebSocket clients connected

**Steps:**
1. Generate 2000 messages/second
2. Verify rate limiting activates
3. Verify message prioritization
4. Verify UI debouncing
5. Verify graceful degradation

**Expected Results:**
- Rate limiting prevents overload
- Critical messages prioritized
- UI remains responsive
- Clear load indicators shown

**Metrics:**
- Rate limiting accuracy: 100%
- UI responsiveness: maintained
- Message prioritization: correct

### 3. Performance Tests

#### TC-3.1: Latency Benchmarking
**Objective:** Measure end-to-end latency

**Preconditions:**
- All services optimized
- Network latency minimized

**Steps:**
1. Send timestamped signal creation request
2. Measure time to UI display
3. Repeat 1000 times
4. Calculate percentiles

**Expected Results:**
- 95th percentile: <500ms
- 99th percentile: <800ms
- Mean: <300ms

**Metrics:**
- P50, P95, P99 latencies
- Standard deviation

#### TC-3.2: Throughput Testing
**Objective:** Test maximum sustainable throughput

**Preconditions:**
- Load testing tools configured

**Steps:**
1. Gradually increase message rate
2. Monitor system resources
3. Find maximum sustainable rate
4. Test with multiple clients

**Expected Results:**
- Sustains 1000 messages/sec
- CPU usage <70%
- Memory usage <80%
- No message loss

**Metrics:**
- Maximum throughput
- Resource utilization
- Error rates

#### TC-3.3: Memory Leak Testing
**Objective:** Verify no memory leaks under sustained load

**Preconditions:**
- Monitoring tools active

**Steps:**
1. Run high-frequency updates for 1 hour
2. Monitor memory usage
3. Check for gradual increases
4. Verify cleanup on component unmount

**Expected Results:**
- Memory usage stable
- No gradual increases
- Proper cleanup verified

**Metrics:**
- Memory usage trend
- Garbage collection frequency
- Object allocation rates

### 4. Integration Tests

#### TC-4.1: Cross-Service Data Consistency
**Objective:** Verify data consistency across services

**Preconditions:**
- All services running

**Steps:**
1. Create signal via API
2. Verify MongoDB storage
3. Verify Redis publication
4. Verify WebSocket forwarding
5. Verify Redux state
6. Verify UI display
7. Check data consistency across all layers

**Expected Results:**
- All data consistent
- No data corruption
- Timestamps synchronized

**Metrics:**
- Data consistency: 100%
- Synchronization accuracy: <1ms

#### TC-4.2: Service Startup Sequence
**Objective:** Test proper service initialization order

**Preconditions:**
- All services stopped

**Steps:**
1. Start Redis
2. Start MongoDB
3. Start Engine Module
4. Start WS Gateway
5. Start Dashboard API
6. Start Frontend
7. Verify all connections establish
8. Verify message flow works

**Expected Results:**
- Clean startup sequence
- All services connect successfully
- Message flow operational

**Metrics:**
- Startup time: <30s
- Connection success rate: 100%

### 5. Browser Compatibility Tests

#### TC-5.1: WebSocket Support
**Objective:** Test WebSocket functionality across browsers

**Preconditions:**
- Multiple browser versions

**Steps:**
1. Test in Chrome, Firefox, Safari, Edge
2. Verify WebSocket connection
3. Test reconnection logic
4. Verify message handling

**Expected Results:**
- Works in all modern browsers
- Fallback mechanisms work
- No browser-specific issues

**Metrics:**
- Browser compatibility: 100%
- Fallback activation: correct

---

## Test Automation Strategy

### Unit Tests
```python
# WebSocket Gateway tests
def test_channel_acl():
def test_rate_limiting():
def test_message_forwarding():

# SignalMonitor tests  
def test_condition_evaluation():
def test_signal_lifecycle():

# Frontend tests
def test_websocket_reconnection():
def test_redux_updates():
```

### Integration Tests
```python
# End-to-end flow tests
async def test_signal_creation_flow():
async def test_realtime_execution_flow():
async def test_websocket_reconnection():
```

### Load Tests
```python
# Performance benchmarks
async def test_latency_distribution():
async def test_throughput_limits():
async def test_memory_usage():
```

### Monitoring Tests
```python
# Health check validation
def test_service_health_endpoints():
def test_websocket_connection_health():
def test_message_delivery_metrics():
```

---

## Test Data and Fixtures

### Mock Data Generators

**Signal Creation:**
```python
def create_test_signal(instrument="BANKNIFTY", action="BUY", confidence=0.8):
    return {
        "condition_id": f"test_{uuid.uuid4().hex[:8]}",
        "instrument": instrument,
        "action": action,
        "indicator": "rsi_14",
        "operator": "LESS_THAN", 
        "threshold": 30.0,
        "confidence": confidence,
        "created_at": datetime.now().isoformat()
    }
```

**Market Tick Generator:**
```python
def generate_market_ticks(instrument="BANKNIFTY", count=100, interval_ms=100):
    ticks = []
    base_price = 45000.0
    
    for i in range(count):
        tick = {
            "instrument": instrument,
            "last_price": base_price + (i * 0.1),  # Gradual price movement
            "timestamp": datetime.now().isoformat(),
            "volume": 1000000 + (i * 1000),
            "oi": 800000 + (i * 500)
        }
        ticks.append(tick)
        time.sleep(interval_ms / 1000)
    
    return ticks
```

### Test Scenarios

**Happy Path Scenarios:**
- Normal signal creation and execution
- Market data streaming
- WebSocket connection stability

**Edge Cases:**
- Empty signal lists
- Invalid message formats
- Network partitions
- Service restarts

**Failure Scenarios:**
- Redis connection loss
- WebSocket gateway crash
- SignalMonitor exceptions
- High load conditions

---

## Success Criteria Validation

### Latency Requirements
- [ ] 95th percentile end-to-end latency <500ms
- [ ] Signal trigger to execution <50ms
- [ ] UI update after execution <100ms

### Reliability Requirements  
- [ ] Message delivery rate >99.9%
- [ ] WebSocket reconnection within 30s
- [ ] Service availability >99.9%
- [ ] No data loss during failures

### Performance Requirements
- [ ] Sustains 1000 messages/second
- [ ] Memory usage stable under load
- [ ] CPU usage <70% at max load
- [ ] UI remains responsive

### Functional Requirements
- [ ] All message flows work correctly
- [ ] Error handling graceful
- [ ] Recovery automatic
- [ ] Monitoring comprehensive

---

## Test Execution Plan

### Phase 1: Unit Testing (Day 1-2)
- Run all unit tests
- Fix any failing tests
- Code coverage >90%

### Phase 2: Integration Testing (Day 3-4)  
- Test service interactions
- Validate message flows
- Performance benchmarking

### Phase 3: End-to-End Testing (Day 5-6)
- Full system tests
- Failure mode testing
- Load testing

### Phase 4: Production Validation (Day 7)
- Production environment testing
- Monitoring validation
- Sign-off and deployment

---

## Risk Assessment

### High Risk Areas
- **WebSocket reconnection logic** - Complex state management
- **Message ordering guarantees** - Sequence number handling
- **Backpressure under load** - Rate limiting accuracy

### Mitigation Strategies
- **Comprehensive testing** - Multiple test scenarios
- **Monitoring** - Detailed metrics and alerting
- **Gradual rollout** - Feature flags for new functionality
- **Rollback plan** - Quick reversion capability

### Contingency Plans
- **WebSocket fallback** - REST API polling if WS fails
- **Message persistence** - Redis-backed message queues
- **Circuit breakers** - Automatic degradation under load
- **Manual overrides** - Administrative controls for issues

---

*This test plan ensures comprehensive validation of the real-time integration system. All tests should be automated and run in CI/CD pipeline.*</content>
<parameter name="filePath">c:\code\zerodha\REALTIME_TEST_PLAN.md