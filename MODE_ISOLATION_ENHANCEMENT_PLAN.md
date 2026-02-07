# Mode Isolation Enhancement Plan

**Date:** February 5, 2026  
**Goal:** Close mode isolation gaps to ensure 100% data separation between LIVE and HISTORICAL modes

---

## 1. AUDIT FINDINGS

### ✅ Services Using redis_key_manager (Compliant)
- ✅ `ohlc_aggregator_service.py` - Uses `get_redis_key()` for OHLC storage
- ✅ `multi_timeframe_aggregator.py` - Mode-aware aggregation
- ✅ `api_service.py` - All API endpoints use key manager
- ✅ `ltp_collector.py` - Imports `get_redis_key`
- ✅ `volume_enhancer.py` - Uses key prefixing
- ✅ Mock data publishers - Follow key conventions

### ⚠️ Services with Direct Redis Access (Needs Review)
- ⚠️ `websocket_tick_collector.py` - Direct `redis.Redis()` instantiation
- ⚠️ `historical_tick_replayer.py` - Direct access for virtual time system
- ⚠️ `data_storage_manager.py` - Generic redis_client parameter
- ⚠️ `runner.py` - Creates Redis clients directly
- ⚠️ `strategy/runner.py` - Direct Redis instantiation
- ⚠️ `sources/depth.py` - Direct Redis client
- ⚠️ `verify_modes.py` - Utility script (intentional bypass)

### 📊 Gap Analysis Summary
| Category | Status | Count | Risk Level |
|----------|--------|-------|------------|
| Using redis_key_manager | ✅ Compliant | 6+ files | Low |
| Direct Redis access | ⚠️ Review needed | 7+ files | Medium |
| Test files | ℹ️ Intentional | 10+ files | None |
| System utilities | ℹ️ Intentional | 3 files | None |

**Key Insight:** Most core data flow services are compliant. Direct access is mainly in:
1. Initialization/setup code (runners)
2. System utilities (verify_modes.py)
3. Special systems (virtual time, historical replay)

---

## 2. ARCHITECTURE DESIGN

### 2.1 Mode Visibility Layer
```
┌─────────────────────────────────────────────┐
│          User Interface (Dashboard)          │
│  ┌──────────────────────────────────────┐   │
│  │  Mode Badge: [LIVE] or [HISTORICAL]  │   │
│  │  Timestamp: Current/Virtual Time     │   │
│  │  Visual Theme: Green=Live, Blue=Hist │   │
│  └──────────────────────────────────────┘   │
└──────────────────▲──────────────────────────┘
                   │
                   │ GET /api/v1/system/mode
                   │
┌──────────────────┴──────────────────────────┐
│         Market Data API (Backend)           │
│  ┌──────────────────────────────────────┐   │
│  │  Mode Detection Service              │   │
│  │  - Read EXECUTION_MODE env           │   │
│  │  - Check virtual_time:enabled        │   │
│  │  - Return mode + timestamp           │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### 2.2 Validation Layer
```
Service Startup
      ↓
┌─────────────────────────────┐
│  Mode Consistency Validator │
│                             │
│  1. Check EXECUTION_MODE    │
│  2. Check Redis mode keys   │
│  3. Validate no conflicts   │
│  4. Log mode clearly        │
└─────────────────────────────┘
      ↓
   Proceed or FAIL FAST
```

### 2.3 Service Standardization Pattern
```python
# BEFORE (Direct access - bypass risk)
redis_client = redis.Redis(host=..., port=...)
redis_client.set("ohlc:BNF:1min", data)  # No mode prefix!

# AFTER (Standardized pattern)
from redis_key_manager import get_redis_key

redis_client = redis.Redis(host=..., port=...)
key = get_redis_key("ohlc:BNF:1min")  # Auto-prefixed: "live:ohlc:BNF:1min"
redis_client.set(key, data)
```

---

## 3. IMPLEMENTATION PLAN

### Phase 1: Visibility (High Value, Low Risk)
**Goal:** Users can see current mode at a glance

#### Task 1.1: Backend Mode API
**File:** `market_data/src/market_data/api_service.py`
```python
@app.get("/api/v1/system/mode")
async def get_system_mode():
    """Get current execution mode and virtual time status."""
    mode = get_execution_mode()
    virtual_time_enabled = redis_client.get("system:virtual_time:enabled") == "1"
    virtual_time_current = redis_client.get("system:virtual_time:current")
    
    return {
        "mode": mode,
        "virtual_time_enabled": virtual_time_enabled,
        "virtual_time": virtual_time_current,
        "system_time": datetime.now(IST).isoformat(),
        "effective_time": virtual_time_current if virtual_time_enabled else datetime.now(IST).isoformat()
    }
```

**Effort:** 15 minutes  
**Testing:** `curl http://localhost:8004/api/v1/system/mode`

#### Task 1.2: UI Mode Badge
**File:** `market_data_dashboard/templates/index.html`
```javascript
// Add to header section
async function updateModeIndicator() {
    try {
        const response = await fetch('/api/v1/system/mode');
        const data = await response.json();
        
        const badge = document.getElementById('mode-badge');
        const isLive = data.mode === 'live' && !data.virtual_time_enabled;
        
        badge.innerHTML = `
            <span class="badge ${isLive ? 'bg-success' : 'bg-info'}">
                <i class="bi ${isLive ? 'bi-broadcast-pin' : 'bi-clock-history'}"></i>
                ${data.mode.toUpperCase()}
                ${data.virtual_time ? `(${data.virtual_time.split('T')[0]})` : ''}
            </span>
        `;
        
        // Update timestamp display
        document.getElementById('current-time').textContent = data.effective_time;
    } catch (err) {
        console.error('Failed to fetch mode:', err);
    }
}

// Call every 5 seconds
setInterval(updateModeIndicator, 5000);
updateModeIndicator();
```

**Effort:** 30 minutes  
**Testing:** Visual verification in browser

---

### Phase 2: Validation (Medium Risk, High Impact)
**Goal:** Prevent mode conflicts at startup

#### Task 2.1: Startup Validator
**File:** `market_data/src/market_data/mode_validator.py` (NEW)
```python
"""Mode isolation startup validator."""
import os
import redis
import logging
from redis_key_manager import get_execution_mode

logger = logging.getLogger(__name__)

class ModeValidationError(Exception):
    """Raised when mode configuration is inconsistent."""
    pass

def validate_mode_consistency(redis_client: redis.Redis) -> dict:
    """
    Validate that execution mode is consistent across environment and Redis.
    
    Returns:
        dict: Validation results with mode, warnings, and status
        
    Raises:
        ModeValidationError: If critical inconsistency detected
    """
    env_mode = get_execution_mode()
    redis_mode = redis_client.get("system:execution_mode")
    virtual_time_enabled = redis_client.get("system:virtual_time:enabled") == "1"
    
    warnings = []
    
    # Check 1: Environment vs Redis mode
    if redis_mode and redis_mode.decode() != env_mode:
        warnings.append(
            f"Mode mismatch: EXECUTION_MODE={env_mode}, "
            f"Redis system:execution_mode={redis_mode.decode()}"
        )
    
    # Check 2: Virtual time implies historical mode
    if virtual_time_enabled and env_mode == "live":
        raise ModeValidationError(
            "CRITICAL: Virtual time is enabled but EXECUTION_MODE=live. "
            "This creates timestamp confusion. Set EXECUTION_MODE=historical."
        )
    
    # Check 3: Redis data freshness
    sample_keys = redis_client.keys(f"{env_mode}:*")[:5]
    if len(sample_keys) == 0:
        warnings.append(f"No {env_mode}-prefixed keys found in Redis. Is this intentional?")
    
    # Check 4: Orphaned keys from other mode
    other_mode = "historical" if env_mode == "live" else "live"
    other_keys = redis_client.keys(f"{other_mode}:*")
    if len(other_keys) > 0:
        warnings.append(
            f"Found {len(other_keys)} keys from {other_mode.upper()} mode. "
            f"Use clear_mode_data() to clean."
        )
    
    result = {
        "mode": env_mode,
        "virtual_time_enabled": virtual_time_enabled,
        "redis_mode": redis_mode.decode() if redis_mode else None,
        "warnings": warnings,
        "status": "error" if len(warnings) > 0 else "ok"
    }
    
    # Log results
    logger.info(f"Mode validation: {env_mode.upper()}")
    if virtual_time_enabled:
        logger.info("Virtual time: ENABLED")
    for warning in warnings:
        logger.warning(warning)
    
    return result
```

**Effort:** 1 hour  
**Testing:** Unit tests with different mode combinations

#### Task 2.2: Integrate Validator in Service Startup
**Files:** `api_service.py`, `runner.py`, `ohlc_aggregator_service.py`
```python
# Add to startup sequence
from market_data.mode_validator import validate_mode_consistency

@app.on_event("startup")
async def startup_validation():
    try:
        result = validate_mode_consistency(redis_client)
        logger.info(f"Mode validation: {result}")
        if result['status'] == 'error':
            logger.error("Mode validation warnings detected - review configuration")
    except ModeValidationError as e:
        logger.critical(f"STARTUP FAILED: {e}")
        raise
```

**Effort:** 30 minutes per service (3 services = 1.5 hours)  
**Testing:** Start services in different modes, verify logs

---

### Phase 3: Service Standardization (Medium Risk, Medium Effort)
**Goal:** Ensure all services use redis_key_manager consistently

#### Task 3.1: Audit and Refactor Direct Redis Access
**Target Files:**
1. `websocket_tick_collector.py` - Add `get_redis_key()` to tick storage
2. `data_storage_manager.py` - Wrap all key operations
3. `strategy/runner.py` - Use key manager for signal storage

**Pattern:**
```python
# Find all lines like:
redis_client.set("tick:BNF:123456", data)
redis_client.get("ohlc:BNF:1min")

# Replace with:
from redis_key_manager import get_redis_key
redis_client.set(get_redis_key("tick:BNF:123456"), data)
redis_client.get(get_redis_key("ohlc:BNF:1min"))
```

**Effort:** 30 minutes per file × 3 files = 1.5 hours  
**Testing:** E2E test with both modes, verify key prefixing

#### Task 3.2: Create Redis Client Factory
**File:** `market_data/src/market_data/redis_factory.py` (NEW)
```python
"""Centralized Redis client factory with mode awareness."""
import redis
import os
from redis_key_manager import get_execution_mode
import logging

logger = logging.getLogger(__name__)

def create_redis_client(
    host: str = None,
    port: int = None,
    decode_responses: bool = True,
    log_mode: bool = True
) -> redis.Redis:
    """
    Create Redis client with mode logging.
    
    Args:
        host: Redis host (default from env)
        port: Redis port (default from env)
        decode_responses: Whether to decode responses
        log_mode: Whether to log execution mode
        
    Returns:
        redis.Redis: Configured client
    """
    host = host or os.getenv("REDIS_HOST", "localhost")
    port = port or int(os.getenv("REDIS_PORT", "6379"))
    
    client = redis.Redis(
        host=host,
        port=port,
        db=0,
        decode_responses=decode_responses
    )
    
    if log_mode:
        mode = get_execution_mode()
        logger.info(f"Redis client created: {host}:{port} (mode={mode.upper()})")
    
    return client
```

**Effort:** 1 hour  
**Testing:** Replace direct Redis() calls, verify logs

---

### Phase 4: Documentation (Low Risk, High Value)
**Goal:** Clear guide for mode switching and troubleshooting

#### Task 4.1: Create Mode Switching Guide
**File:** `docs/MODE_SWITCHING_GUIDE.md`

**Contents:**
1. **Understanding Modes**
   - LIVE mode: Real-time trading, current timestamps
   - HISTORICAL mode: Backtesting, virtual time
   
2. **How to Switch Modes**
   ```bash
   # Switch to LIVE
   export EXECUTION_MODE=live
   docker-compose up -d
   
   # Switch to HISTORICAL
   export EXECUTION_MODE=historical
   docker-compose -f docker-compose.yml -f docker-compose.historical.yml up -d
   ```

3. **Verify Current Mode**
   ```bash
   # Check environment
   echo $EXECUTION_MODE
   
   # Check Redis
   redis-cli GET system:execution_mode
   
   # Check API
   curl http://localhost:8004/api/v1/system/mode
   ```

4. **Clean Mode Data**
   ```python
   from redis_key_manager import clear_mode_data
   import redis
   
   r = redis.Redis()
   clear_mode_data(r, "historical")  # Remove all historical:* keys
   ```

5. **Troubleshooting**
   - Mode mismatch errors
   - Timestamp confusion
   - Missing data after mode switch

**Effort:** 2 hours  
**Review:** Get user feedback on clarity

---

## 4. QA STRATEGY

### 4.1 Unit Tests
**File:** `market_data/tests/test_mode_validation.py` (NEW)
```python
def test_mode_consistency_valid():
    """Test validator passes with consistent config."""
    os.environ["EXECUTION_MODE"] = "live"
    redis_client.set("system:execution_mode", "live")
    result = validate_mode_consistency(redis_client)
    assert result['status'] == 'ok'

def test_mode_consistency_virtual_time_conflict():
    """Test validator fails when virtual time enabled in live mode."""
    os.environ["EXECUTION_MODE"] = "live"
    redis_client.set("system:virtual_time:enabled", "1")
    with pytest.raises(ModeValidationError):
        validate_mode_consistency(redis_client)

def test_mode_badge_ui():
    """Test UI fetches mode correctly."""
    # Selenium test: verify badge color and text
```

**Effort:** 2 hours  
**Target:** 90%+ coverage of validation logic

### 4.2 Integration Tests
1. **Mode Switch Test**
   - Start in LIVE mode
   - Publish tick data, verify `live:` prefix
   - Stop services
   - Start in HISTORICAL mode
   - Publish tick data, verify `historical:` prefix
   - Verify live data still exists, not overwritten

2. **UI Indicator Test**
   - Start dashboard
   - Verify badge shows correct mode
   - Switch mode (restart)
   - Verify badge updates within 5 seconds

**Effort:** 3 hours  
**Automation:** Add to CI/CD pipeline

### 4.3 Manual Testing Checklist
- [ ] Start system in LIVE mode, check badge shows "LIVE" green
- [ ] Publish tick, verify `redis-cli KEYS "live:*"` shows data
- [ ] Check dashboard timestamp shows current time (not virtual)
- [ ] Restart in HISTORICAL mode with virtual time
- [ ] Check badge shows "HISTORICAL" blue with date
- [ ] Publish historical tick, verify `redis-cli KEYS "historical:*"` shows data
- [ ] Verify live data still exists separately
- [ ] Check logs show "Mode validation: HISTORICAL"
- [ ] Test API endpoint `/api/v1/system/mode` returns correct info
- [ ] Simulate mode mismatch, verify startup error

---

## 5. EFFORT ESTIMATION

| Phase | Tasks | Effort | Priority | Risk |
|-------|-------|--------|----------|------|
| Phase 1: Visibility | 2 | 45 min | HIGH | LOW |
| Phase 2: Validation | 2 | 2.5 hrs | HIGH | MEDIUM |
| Phase 3: Standardization | 2 | 2.5 hrs | MEDIUM | MEDIUM |
| Phase 4: Documentation | 1 | 2 hrs | MEDIUM | LOW |
| QA | 3 | 5 hrs | HIGH | - |
| **TOTAL** | **10** | **12.5 hrs** | - | - |

**Recommendation:** Implement in order (1 → 2 → 3 → 4) over 2-3 work sessions

---

## 6. RISK MITIGATION

### Risk 1: Breaking Existing Services
**Mitigation:**
- Test each change in isolated environment
- Keep backward compatibility (optional mode parameter)
- Roll out service-by-service, not all at once

### Risk 2: Performance Impact (Validation Overhead)
**Mitigation:**
- Validation only at startup, not per-request
- Mode detection cached in memory
- < 10ms overhead per service startup

### Risk 3: User Confusion (Too Many Warnings)
**Mitigation:**
- Log at INFO level for normal operation
- WARNING only for actual issues
- Clear documentation with examples

### Risk 4: Incomplete Coverage (Missed Services)
**Mitigation:**
- Comprehensive grep audit (completed)
- Add validation to detect unprefixed keys
- CI/CD check: fail if direct Redis keys detected without mode prefix

---

## 7. SUCCESS CRITERIA

### Must Have (MVP)
- ✅ UI shows mode badge (LIVE/HISTORICAL)
- ✅ Startup validation prevents mode conflicts
- ✅ API endpoint `/api/v1/system/mode` works
- ✅ Documentation exists for mode switching

### Should Have (Complete)
- ✅ All core services use redis_key_manager
- ✅ Integration tests pass in both modes
- ✅ Logs clearly indicate mode at startup

### Nice to Have (Enhanced)
- ⚡ Auto-detection of mode from Redis data
- ⚡ UI warning banner for historical mode
- ⚡ Mode switching without restart (hot-swap)
- ⚡ Metrics dashboard showing mode history

---

## 8. ROLLOUT PLAN

### Week 1: Foundation
- Day 1: Implement Phase 1 (Visibility)
- Day 2: Implement Phase 2 (Validation)
- Day 3: Test and fix issues

### Week 2: Hardening
- Day 4: Implement Phase 3 (Standardization)
- Day 5: Write documentation (Phase 4)
- Day 6: QA testing

### Week 3: Production
- Day 7: Deploy to staging
- Day 8: Monitor, fix bugs
- Day 9: Deploy to production
- Day 10: Post-launch review

---

## 9. NEXT STEPS (After This Plan)

**Immediate:**
1. Review this plan with user - get approval on approach
2. Decide: Full implementation or phased rollout?
3. Set up test environment with both mode configurations

**Questions for Discussion:**
1. **Priority:** Implement all phases or Phase 1 (Visibility) first?
2. **Scope:** Fix all 7 services with direct Redis access or just critical 3?
3. **Testing:** Need automated E2E tests or manual verification OK?
4. **Timeline:** Implement over 1 day (intensive) or 3 days (careful)?

**My Recommendation:**
Start with **Phase 1 + Phase 2** (Visibility + Validation) today. This gives you:
- Immediate UI feedback on mode
- Protection against startup errors
- **Total effort: 3 hours**

Then Phase 3 + 4 can be done later when needed.

What do you think? Ready to proceed or want to discuss the approach first?
