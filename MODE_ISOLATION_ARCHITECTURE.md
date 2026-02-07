# Mode Isolation - Technical Architecture

## Current State Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      EXECUTION_MODE (ENV VAR)                    │
│                    "live" or "historical"                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Read by all services
                             ▼
         ┌───────────────────────────────────────┐
         │     redis_key_manager.py              │
         │  ┌─────────────────────────────────┐  │
         │  │ get_execution_mode()            │  │
         │  │    → Returns: "live"/"historical" │  │
         │  └─────────────────────────────────┘  │
         │  ┌─────────────────────────────────┐  │
         │  │ get_redis_key(base_key)         │  │
         │  │    → Returns: "mode:base_key"   │  │
         │  │    Example: "live:ohlc:BNF:1min"│  │
         │  └─────────────────────────────────┘  │
         └───────────────────┬───────────────────┘
                             │
                             │ Used by
                             ▼
     ┌───────────────────────────────────────────────┐
     │           Redis (Port 6379)                   │
     │                                                │
     │  LIVE MODE DATA:                              │
     │  ├─ live:ohlc:BNF:1min                        │
     │  ├─ live:tick:BNF:123456                      │
     │  ├─ live:options:BANKNIFTY:chain              │
     │  └─ live:indicators:RSI                       │
     │                                                │
     │  HISTORICAL MODE DATA:                        │
     │  ├─ historical:ohlc:BNF:1min                  │
     │  ├─ historical:tick:BNF:123456                │
     │  └─ historical:indicators:RSI                 │
     │                                                │
     │  SYSTEM KEYS (no prefix):                     │
     │  ├─ system:execution_mode → "live"            │
     │  ├─ system:virtual_time:enabled → "1"         │
     │  └─ system:virtual_time:current → ISO timestamp│
     └───────────────────────────────────────────────┘
```

## Service Compliance Matrix

### ✅ COMPLIANT Services (Using redis_key_manager)
```
Service                    │ Import Pattern                      │ Status
───────────────────────────┼─────────────────────────────────────┼────────
api_service.py             │ from redis_key_manager import *     │ ✅
ohlc_aggregator_service.py │ from redis_key_manager import *     │ ✅
multi_timeframe_aggregator │ from redis_key_manager import *     │ ✅
ltp_collector.py           │ from redis_key_manager import *     │ ✅
volume_enhancer.py         │ from redis_key_manager import *     │ ✅
mock_data_publisher.py     │ from redis_key_manager import *     │ ✅
```

### ⚠️ DIRECT ACCESS Services (Needs Review)
```
Service                    │ Redis Access Pattern                │ Risk
───────────────────────────┼─────────────────────────────────────┼─────────
websocket_tick_collector   │ redis.Redis() direct                │ MEDIUM
historical_tick_replayer   │ redis.Redis() for virtual time      │ LOW
data_storage_manager       │ Accepts redis_client param          │ LOW
runner.py                  │ Creates Redis client, passes down   │ MEDIUM
strategy/runner.py         │ redis.Redis() direct                │ MEDIUM
sources/depth.py           │ redis.Redis() direct                │ LOW
verify_modes.py            │ redis.Redis() (utility script)      │ NONE
```

## Proposed Enhancement Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                       USER INTERFACE                                │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Header: [🔴 LIVE] or [🔵 HISTORICAL (2026-01-15)]          │  │
│  │  Current Time: 2026-02-05 09:15:30 IST (Real or Virtual)    │  │
│  │  Auto-refresh every 5 seconds                                │  │
│  └──────────────────────────────────────────────────────────────┘  │
│           ▲                                                         │
│           │ Fetch every 5s                                          │
│           │ GET /api/v1/system/mode                                 │
└───────────┼─────────────────────────────────────────────────────────┘
            │
┌───────────┴─────────────────────────────────────────────────────────┐
│                    MARKET DATA API                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  NEW ENDPOINT: /api/v1/system/mode                           │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │ def get_system_mode():                                  │  │   │
│  │  │   mode = get_execution_mode()  # "live" or "historical"│  │   │
│  │  │   vt_enabled = redis.get("system:virtual_time:enabled")│  │   │
│  │  │   vt_current = redis.get("system:virtual_time:current")│  │   │
│  │  │   return {                                              │  │   │
│  │  │     "mode": mode,                                       │  │   │
│  │  │     "virtual_time_enabled": vt_enabled,                │  │   │
│  │  │     "virtual_time": vt_current,                        │  │   │
│  │  │     "system_time": datetime.now(IST),                  │  │   │
│  │  │     "effective_time": vt_current or now                │  │   │
│  │  │   }                                                     │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  STARTUP VALIDATION: @app.on_event("startup")               │   │
│  │  ┌────────────────────────────────────────────────────────┐ │   │
│  │  │ validate_mode_consistency(redis_client)                │ │   │
│  │  │   ✓ Check EXECUTION_MODE matches Redis                 │ │   │
│  │  │   ✓ Verify virtual_time not enabled in live mode       │ │   │
│  │  │   ✓ Check for orphaned keys from other mode            │ │   │
│  │  │   ✗ FAIL FAST if critical mismatch                     │ │   │
│  │  └────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                   NEW: mode_validator.py                             │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ class ModeValidationError(Exception): pass                     │  │
│  │                                                                 │  │
│  │ def validate_mode_consistency(redis_client) -> dict:           │  │
│  │   env_mode = get_execution_mode()                              │  │
│  │   redis_mode = redis_client.get("system:execution_mode")       │  │
│  │   vt_enabled = redis_client.get("system:virtual_time:enabled") │  │
│  │                                                                 │  │
│  │   # CRITICAL CHECK: Virtual time in live mode = ERROR          │  │
│  │   if vt_enabled and env_mode == "live":                        │  │
│  │     raise ModeValidationError("Virtual time enabled in live")  │  │
│  │                                                                 │  │
│  │   # WARNING: Mode mismatch                                     │  │
│  │   if redis_mode != env_mode:                                   │  │
│  │     warnings.append("Mode mismatch detected")                  │  │
│  │                                                                 │  │
│  │   return {"mode": env_mode, "warnings": [...], "status": "ok"} │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                  NEW: redis_factory.py (Optional)                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ def create_redis_client(host, port, log_mode=True):            │  │
│  │   client = redis.Redis(host=host, port=port)                   │  │
│  │   if log_mode:                                                  │  │
│  │     mode = get_execution_mode()                                 │  │
│  │     logger.info(f"Redis client: {host}:{port} (mode={mode})")  │  │
│  │   return client                                                 │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  Usage: Replace `redis.Redis()` with `create_redis_client()`         │
└──────────────────────────────────────────────────────────────────────┘
```

## Data Flow: LIVE Mode

```
Zerodha WebSocket Tick
        │
        ▼
┌───────────────────┐
│ WebSocket Tick    │
│ Collector         │
└────────┬──────────┘
         │ Stores with get_redis_key()
         ▼
   Redis: "live:tick:BNF:123456"
         │
         ├─────────────────┐
         │                 │
         ▼                 ▼
┌─────────────┐   ┌─────────────────┐
│ OHLC        │   │ Indicators      │
│ Aggregator  │   │ Calculator      │
└──────┬──────┘   └────────┬────────┘
       │                   │
       ▼                   ▼
 live:ohlc:BNF:1min   live:indicators:RSI
       │                   │
       └──────┬────────────┘
              │
              ▼
       ┌────────────┐
       │ Dashboard  │
       │ API        │
       └────────────┘
              │
              ▼
         User UI: [🔴 LIVE]
```

## Data Flow: HISTORICAL Mode

```
Historical CSV File
        │
        ▼
┌───────────────────┐
│ Historical Tick   │
│ Replayer          │
│ (Virtual Time)    │
└────────┬──────────┘
         │ Sets: system:virtual_time:current = "2026-01-15T09:15:00"
         │ Stores with get_redis_key()
         ▼
   Redis: "historical:tick:BNF:123456"
         │
         ├─────────────────┐
         │                 │
         ▼                 ▼
┌─────────────┐   ┌─────────────────┐
│ OHLC        │   │ Indicators      │
│ Aggregator  │   │ Calculator      │
└──────┬──────┘   └────────┬────────┘
       │                   │
       ▼                   ▼
 historical:ohlc:BNF:1min  historical:indicators:RSI
       │                   │
       └──────┬────────────┘
              │
              ▼
       ┌────────────┐
       │ Dashboard  │
       │ API        │
       └────────────┘
              │
              ▼
    User UI: [🔵 HISTORICAL (2026-01-15)]
```

## Key Isolation Mechanisms

### 1. Environment Variable
```bash
# Docker Compose
services:
  market-data-api:
    environment:
      - EXECUTION_MODE=live  # or historical
```

### 2. Redis Key Prefixing
```python
# Automatic prefixing
get_redis_key("ohlc:BNF:1min")
# Returns: "live:ohlc:BNF:1min" or "historical:ohlc:BNF:1min"
```

### 3. Virtual Time System
```python
# Historical mode uses virtual time
if mode == "historical":
    redis.set("system:virtual_time:enabled", "1")
    redis.set("system:virtual_time:current", "2026-01-15T09:15:00+05:30")
    # All services read this instead of datetime.now()
```

### 4. Startup Validation
```python
# Prevents conflicts at boot
@app.on_event("startup")
async def validate():
    if virtual_time_enabled and mode == "live":
        raise ModeValidationError("CRITICAL: Invalid configuration")
```

## Mode Switching Flow

### Clean Switch (Recommended)
```
1. Stop all services
   └─ docker-compose down

2. Clear Redis data for old mode (optional)
   └─ redis-cli FLUSHDB
   └─ OR: clear_mode_data(redis_client, "live")

3. Set environment variable
   └─ export EXECUTION_MODE=historical

4. Start services with new mode
   └─ docker-compose up -d

5. Verify mode in UI
   └─ Check badge shows [🔵 HISTORICAL]

6. Verify Redis keys
   └─ redis-cli KEYS "historical:*"
```

### Hot Switch (Advanced - Not Yet Implemented)
```
Future enhancement: Allow mode switching without restart
- Services subscribe to "system:execution_mode" changes
- On change event, reload mode and reconnect
- Requires careful state management
```

## Error Scenarios

### Scenario 1: Mode Mismatch
```
EXECUTION_MODE=live
Redis: system:execution_mode = "historical"

RESULT: Warning logged, service uses EXECUTION_MODE value
```

### Scenario 2: Virtual Time in Live Mode
```
EXECUTION_MODE=live
Redis: system:virtual_time:enabled = "1"

RESULT: ModeValidationError raised, service fails to start
REASON: Prevents timestamp confusion (real time vs virtual time)
```

### Scenario 3: Orphaned Keys
```
EXECUTION_MODE=historical
Redis: 1000 keys with "live:*" prefix

RESULT: Warning logged
RECOMMENDATION: Run clear_mode_data(redis_client, "live")
```

## Testing Strategy

### Unit Tests
```python
test_mode_validator.py:
  ✓ test_valid_live_mode()
  ✓ test_valid_historical_mode()
  ✓ test_virtual_time_in_live_raises_error()
  ✓ test_mode_mismatch_warning()
  ✓ test_orphaned_keys_detection()
```

### Integration Tests
```python
test_mode_isolation_e2e.py:
  ✓ test_live_data_not_overwritten_by_historical()
  ✓ test_historical_data_not_overwritten_by_live()
  ✓ test_ui_mode_badge_updates()
  ✓ test_api_returns_correct_mode()
```

### Manual Testing
```
Checklist:
  □ Start in LIVE mode, verify green badge
  □ Publish tick, verify "live:*" keys in Redis
  □ Stop services
  □ Start in HISTORICAL mode, verify blue badge
  □ Publish tick, verify "historical:*" keys in Redis
  □ Verify live data still exists
  □ Check logs for "Mode validation: HISTORICAL"
```

## Rollback Plan

If issues arise after implementation:

1. **Phase 1 (UI) Rollback**
   - Remove mode badge from UI
   - No backend changes needed
   - Risk: LOW

2. **Phase 2 (Validation) Rollback**
   - Comment out validation in startup
   - Services start without checks
   - Risk: MEDIUM

3. **Phase 3 (Standardization) Rollback**
   - Revert to direct Redis access
   - Use git to restore previous versions
   - Risk: HIGH (requires testing)

**Best Practice:** Deploy phases incrementally, test thoroughly before next phase

## Monitoring & Observability

### Metrics to Track
```
- Mode switch count (daily)
- Mode mismatch errors (should be 0)
- Virtual time lag (historical mode only)
- Orphaned key count
- API response time for /api/v1/system/mode
```

### Logs to Monitor
```
INFO: "Mode validation: LIVE" (startup)
WARNING: "Mode mismatch detected: ENV=live, Redis=historical"
ERROR: "CRITICAL: Virtual time enabled in live mode"
INFO: "Redis client created: localhost:6379 (mode=LIVE)"
```

### Alerts to Configure
```
CRITICAL: Mode validation error on startup
WARNING: Mode mismatch detected for >5 minutes
INFO: Mode switched (LIVE → HISTORICAL or vice versa)
```

---

**Summary:**
This architecture provides comprehensive mode isolation with:
- ✅ Visual feedback (UI badge)
- ✅ Startup validation (fail-fast on errors)
- ✅ Consistent key management (redis_key_manager)
- ✅ Clear documentation (switching guide)
- ✅ Testing strategy (unit + integration + manual)

**Total Effort:** 12.5 hours over 2-3 sessions
**Risk Level:** LOW (existing system already 90% compliant)
**Value:** HIGH (prevents production incidents from mode confusion)
