# Trading System Monitoring Module

Production hardening and monitoring capabilities for the automated trading system.

## Features

### 🚀 Performance Monitoring
- Function execution timing
- System resource monitoring (CPU, memory, disk)
- Real-time performance metrics
- Automated performance reporting

### 📊 Metrics Collection
- Counter metrics (request counts, errors)
- Gauge metrics (current values like temperature, queue size)
- Timer metrics (operation durations)
- Custom metric aggregation and reporting

### ❤️ Health Checking
- Service health monitoring
- Infrastructure dependency checks (Redis, MongoDB)
- Automated health status reporting
- Continuous health monitoring

### 🛡️ Error Handling
- Circuit breaker pattern implementation
- Exponential backoff retry logic
- Graceful error recovery
- Comprehensive error logging and reporting

### 🚦 Rate Limiting
- Token bucket algorithm implementation
- Configurable rate limits per resource
- API rate limiting
- External service call throttling

## Installation

```bash
cd monitoring
pip install -e .
```

## Usage

### Basic Setup

```python
from monitoring import (
    get_performance_monitor, get_metrics_collector,
    get_health_checker, get_error_handler, get_rate_limiter
)

# Get monitoring instances
perf_monitor = get_performance_monitor()
metrics = get_metrics_collector()
health = get_health_checker()
errors = get_error_handler()
rate_limiter = get_rate_limiter()
```

### Performance Monitoring

```python
@perf_monitor.time_function("my_function")
def my_function():
    # Your code here
    return "result"

# Manual metric recording
perf_monitor.record_metric("custom_metric", 42.0)
```

### Error Handling

```python
# Execute with circuit breaker protection
try:
    result = errors.execute_with_protection("api_call", make_api_call, arg1, arg2)
except CircuitBreakerOpenException:
    logger.warning("Circuit breaker is open, skipping call")
```

### Rate Limiting

```python
# Check rate limit before operation
if rate_limiter.allow("api_requests"):
    make_api_call()
else:
    logger.warning("Rate limit exceeded")
```

### Health Checking

```python
# Check all services
health_report = await health.check_all_services()
if not health.is_system_healthy():
    alert_admin("System health degraded")
```

## Configuration

Configure monitoring through environment variables:

```bash
# Performance monitoring
ENABLE_PERFORMANCE_MONITORING=true
PERFORMANCE_LOG_INTERVAL=300

# Error handling
MAX_RETRIES=3
RETRY_DELAY=1.0

# Rate limiting
API_RATE_LIMIT=100
LLM_RATE_LIMIT=10

# Logging
LOG_LEVEL=INFO
ENABLE_JSON_LOGGING=false
```

## Integration

The monitoring module integrates with the main trading system through:

1. **Centralized Configuration**: Uses the main `config.py` for settings
2. **Logging Integration**: Extends the centralized logging system
3. **Service Health**: Monitors all trading system services
4. **Performance Tracking**: Monitors critical trading operations

## Monitoring Dashboard

The monitoring data can be accessed through the main dashboard UI and API endpoints for:
- Real-time performance metrics
- Health status of all services
- Error rates and circuit breaker status
- Rate limiting utilization

## Examples

See `examples/monitoring_demo.py` for comprehensive usage examples.

## Architecture

```
monitoring/
├── performance_monitor.py    # Performance tracking
├── metrics_collector.py      # Metrics aggregation
├── health_checker.py         # Service health monitoring
├── error_handler.py          # Error recovery mechanisms
├── rate_limiter.py           # Rate limiting implementation
└── examples/                 # Usage examples
```