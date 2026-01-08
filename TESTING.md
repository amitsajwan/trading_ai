# Testing Guide

Comprehensive testing documentation for the Trading AI System.

## Quick Start

```bash
# Run core functionality tests
python test_verify_core.py

# Run time synchronization tests  
python test_time_synchronization.py

# Run market hours tests
python test_market_hours.py
```

## Test Suite Overview

### Core Tests (Run These First)

| Test File | Purpose | Pass Rate | Runtime |
|-----------|---------|-----------|---------|
| `test_verify_core.py` | Core functionality verification | 83%+ | ~10s |
| `test_time_synchronization.py` | Virtual time system | 75%* | ~5s |
| `test_market_hours.py` | Market hours boundary checks | 100% | ~3s |
| `test_signal_monitor.py` | Signal triggering logic | 100% | ~8s |
| `test_technical_indicators_integration.py` | Indicator calculations | 100% | ~5s |

*Redis test requires Docker containers running

### Specialized Tests

| Test File | Purpose |
|-----------|---------|
| `test_mode_switching.py` | Trading mode transitions |
| `test_realtime_signal_system.py` | End-to-end signal flow |
| `test_enhanced_system.py` | Multi-agent integration |
| `test_banknifty.py` | BANKNIFTY-specific logic |

## Test Categories

### 1. Time Synchronization Tests

**Purpose**: Verify virtual time system for historical replay

```bash
python test_time_synchronization.py
```

**What it tests**:
- ✅ TimeService virtual/real time switching
- ✅ Market hours with virtual time
- ✅ Orchestrator market hours integration
- ✅ Redis time synchronization (requires Docker)

**Virtual Time Usage**:
```python
from core_kernel.src.core_kernel.time_service import (
    now as get_system_time,
    set_virtual_time,
    clear_virtual_time,
    is_virtual_time
)

# Enable virtual time
set_virtual_time(datetime(2026, 1, 6, 10, 0, 0))

# All system components now use this time
current = get_system_time()  # Returns 2026-01-06 10:00:00

# Clear virtual time
clear_virtual_time()
```

### 2. Market Hours Tests

**Purpose**: Verify market open/close boundary logic

```bash
python test_market_hours.py
```

**Boundary Cases Tested**:
- ✅ 9:15:00 AM → Market OPEN (inclusive)
- ✅ 9:14:59 AM → Market CLOSED (pre-market)
- ✅ 3:29:59 PM → Market OPEN (still trading)
- ✅ 3:30:00 PM → Market CLOSED (< not <=)
- ✅ Weekends → Market CLOSED

**Key Fix**: Market close uses `<` not `<=` so 3:30 PM exactly is closed.

### 3. Signal Monitoring Tests

**Purpose**: Verify real-time signal triggering

```bash
python test_signal_monitor.py
```

**Test Scenarios**:
- Signal creation and registration
- GREATER_THAN operator
- CROSSES_ABOVE operator (detects crossing, not just being above)
- Multi-condition signals (AND logic)
- Signal auto-removal after trigger

**Example**:
```python
# Create signal
condition = TradingCondition(
    condition_id="test_001",
    instrument="BANKNIFTY",
    indicator="rsi_14",
    operator=ConditionOperator.GREATER_THAN,
    threshold=50.0,
    action="BUY"
)

# Register with monitor
monitor.add_signal(condition)

# On every tick, monitor checks if RSI > 50
events = await monitor.check_signals("BANKNIFTY")
if events:
    # Signal triggered! Execute trade
    execute_trade(events[0])
```

### 4. Technical Indicators Tests

**Purpose**: Verify indicator calculations

```bash
python test_technical_indicators_integration.py
```

**Coverage**:
- Service initialization
- Candle warm-up (50+ candles)
- Tick-by-tick updates
- RSI, SMA, MACD calculations
- Agent perspective analysis
- Complete integration flow

### 5. Core Functionality Tests

**Purpose**: End-to-end verification

```bash
python test_verify_core.py
```

**Components Tested**:
1. TechnicalIndicatorsService
2. SignalMonitor
3. RealtimeSignalProcessor
4. EnhancedTechnicalAgent
5. Multi-agent consensus

## Virtual Time System

### Architecture

```
Redis (Source of Truth)
  ├─ system:virtual_time:enabled = 1
  └─ system:virtual_time:current = 2026-01-06T10:00:00+05:30
       │
       ├────────────────┬───────────────┬──────────────┐
       ▼                ▼               ▼              ▼
  Dashboard      Orchestrator     HistReplay     Test Suite
  TimeService    TimeService      TimeService    get_system_time()
```

### Benefits

1. **Historical Simulation**: Run system on past dates
2. **Reproducibility**: Fixed time → consistent results
3. **Market Hours Testing**: Test boundary conditions
4. **Time Travel**: Test future/past scenarios
5. **Consistency**: All components synchronized

### Test Updates for Virtual Time

All test files now use `get_system_time()` instead of `datetime.now()`:

```python
# OLD (doesn't work with virtual time)
timestamp = datetime.now().isoformat()

# NEW (works with virtual and real time)
timestamp = get_system_time().isoformat()
```

**Updated Test Files**:
- test_market_hours.py
- test_mode_switching.py
- test_verify_core.py
- test_signal_monitor.py
- test_technical_indicators_integration.py
- test_realtime_signal_system.py

## Running Tests with Docker

### Start Test Environment

```bash
# Start all services
docker-compose up -d

# Check services
docker-compose ps
```

### Run Tests in Container

```bash
# Run specific test
docker exec zerodha-orchestrator-service python test_verify_core.py

# Run with virtual time
docker exec zerodha-orchestrator-service python -c "
from core_kernel.src.core_kernel.time_service import set_virtual_time
from datetime import datetime
set_virtual_time(datetime(2026, 1, 6, 10, 0, 0))
"
```

### View Test Logs

```bash
# Dashboard logs
docker logs zerodha-dashboard-service

# Orchestrator logs
docker logs zerodha-orchestrator-service
```

## Test Data

### Creating Test Ticks

```python
def create_test_tick(price: float, volume: int = 1500):
    return {
        "last_price": price,
        "volume": volume,
        "timestamp": get_system_time().isoformat()
    }
```

### Creating Test Candles

```python
def create_test_candle(close: float):
    return {
        "timestamp": get_system_time().isoformat(),
        "open": close - 10,
        "high": close + 20,
        "low": close - 20,
        "close": close,
        "volume": 1500
    }
```

### Warm-Up Pattern

Most tests require 50+ candles for indicator calculation:

```python
# Warm up technical service
service = get_technical_service()
for i in range(50):
    service.update_candle("BANKNIFTY", create_test_candle(45000 + i))
```

## Troubleshooting

### Tests Failing with "datetime has no attribute now"

**Cause**: Circular import or missing TimeService import

**Fix**: Add fallback import:
```python
try:
    from core_kernel.src.core_kernel.time_service import now as get_system_time
except ImportError:
    def get_system_time():
        return datetime.now()
```

### Market Hours Tests Failing

**Cause**: Wrong timezone or boundary logic

**Fix**: Ensure using IST and `<` for close:
```python
# Correct
market_open <= current_time < market_close

# Wrong
market_open <= current_time <= market_close  # 3:30 shows as open
```

### Redis Connection Errors

**Cause**: Redis container not running

**Fix**:
```bash
docker-compose up -d redis
# Or run test without Redis (uses fallback)
```

### Signal Not Triggering

**Cause**: Indicators not warmed up or threshold not met

**Debug**:
```python
# Check indicators
indicators = service.get_indicators("BANKNIFTY")
print(f"RSI: {indicators.rsi_14}")

# Check signal
active = monitor.get_active_signals("BANKNIFTY")
print(f"Active signals: {len(active)}")
```

## Best Practices

1. **Always warm up indicators** - Need 50+ candles for accurate RSI/MACD
2. **Use get_system_time()** - Never use datetime.now() in tests
3. **Test with virtual time** - Verify historical replay compatibility
4. **Check market hours** - Many operations blocked when market closed
5. **Clear virtual time** - Always clear after tests
6. **Verify Redis** - Time sync tests require Redis running

## Quick Reference

### Essential Commands

```bash
# Run all core tests
python test_verify_core.py
python test_time_synchronization.py
python test_market_hours.py

# Enable virtual time
python -c "from core_kernel.src.core_kernel.time_service import set_virtual_time; from datetime import datetime; set_virtual_time(datetime(2026,1,6,10,0,0))"

# Clear virtual time
python -c "from core_kernel.src.core_kernel.time_service import clear_virtual_time; clear_virtual_time()"

# Check virtual time status
python -c "from core_kernel.src.core_kernel.time_service import is_virtual_time, now; print(f'Virtual: {is_virtual_time()}, Time: {now()}')"
```

### Market Hours

- **Open**: Monday-Friday 9:15 AM IST (inclusive)
- **Close**: Monday-Friday 3:30 PM IST (exclusive, < not <=)
- **Timezone**: IST (UTC+5:30)

### Pass Rate Targets

- Core tests: 80%+ passing
- Market hours: 100% passing
- Signal monitoring: 100% passing
- Time synchronization: 75%+ (Redis optional)

