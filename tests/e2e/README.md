# End-to-End Testing Framework

Comprehensive automated testing framework for the critical trading system.

## Overview

This test suite validates all components, APIs, and workflows to ensure the trading system works correctly before any live trading occurs.

## Test Structure

```
tests/e2e/
├── __init__.py
├── conftest.py              # Test fixtures and configuration
├── README.md                # This file
├── utils/                   # Test utilities
│   ├── __init__.py
│   └── test_helpers.py      # Helper functions
├── test_data_layer.py       # Data layer tests
├── test_engine_layer.py     # Engine layer tests
├── test_execution_layer.py  # Execution layer tests
├── test_dashboard_api.py    # Dashboard API tests
├── test_trading_api.py      # Trading API tests
├── test_control_api.py      # Control API tests
├── test_trading_workflow.py # End-to-end workflow tests
├── test_signal_to_trade.py  # Signal-to-trade conversion tests
├── test_multi_agent_consensus.py # Multi-agent tests
├── test_mode_isolation.py   # Mode switching tests
├── test_historical_replay.py # Historical replay tests
├── test_paper_mode_safety.py # Paper mode safety tests
├── test_risk_management.py  # Risk management tests
├── test_error_handling.py   # Error handling tests
├── test_edge_cases.py       # Edge case tests
└── test_performance.py      # Performance tests
```

## Running Tests

### Run All E2E Tests
```bash
pytest tests/e2e/ -v
```

### Run Specific Test Category
```bash
# API tests only
pytest tests/e2e/test_*_api.py -v

# Workflow tests only
pytest tests/e2e/test_trading_workflow.py -v

# Safety tests only
pytest tests/e2e/test_paper_mode_safety.py -v
```

### Run with Coverage
```bash
pytest tests/e2e/ -v --cov=dashboard --cov=engine_module --cov=data_niftybank --cov-report=html
```

### Run Fast Tests Only
```bash
pytest tests/e2e/ -v -m "not slow"
```

## Test Categories

### 1. Component Tests
- **Data Layer**: Market data ingestion, storage, historical replay
- **Engine Layer**: Indicators, agents, signal monitoring
- **Execution Layer**: Risk management, trade execution, position tracking

### 2. API Tests
- **Dashboard API**: Health, market data, analysis endpoints
- **Trading API**: Signal generation, execution, position management
- **Control API**: Mode switching, Zerodha auth, system control

### 3. Workflow Tests
- **Complete Trading Workflow**: Signal → Execution → Position → P&L
- **Signal-to-Trade Conversion**: Conditional signal triggering
- **Multi-Agent Consensus**: Agent voting and signal aggregation

### 4. Safety Tests
- **Paper Mode Validation**: Ensures no live trading in paper mode
- **Mode Isolation**: Database and data isolation between modes
- **Risk Management**: Position limits, daily loss limits

### 5. Integration Tests
- **Historical Replay**: Testing with historical data
- **Mode Switching**: Switching between live/paper modes
- **Error Handling**: System behavior on errors

## Prerequisites

### Required Services
- **MongoDB**: Running on localhost:27017 (or set TEST_MONGODB_URI)
- **Redis**: Running on localhost:6379 (or set TEST_REDIS_HOST/PORT)

### Environment Variables
```bash
TEST_MONGODB_URI=mongodb://localhost:27017/
TEST_REDIS_HOST=localhost
TEST_REDIS_PORT=6379
```

### Dependencies
All dependencies are in `requirements.txt`. Key testing dependencies:
- pytest
- pytest-asyncio
- pytest-cov
- httpx

## Test Fixtures

### Database Fixtures
- `test_mongo_client`: MongoDB client with isolated test database
- `test_redis_client`: Redis client with isolated test database

### Mock Fixtures
- `mock_kite`: Mocked Zerodha Kite API client
- `paper_broker`: Paper trading broker instance
- `mock_market_store`: In-memory market data store

### Data Fixtures
- `sample_market_tick`: Sample tick data
- `sample_ohlc_bar`: Sample OHLC bar data
- `sample_trading_signal`: Sample trading signal
- `historical_data_generator`: Historical data generator

### API Fixtures
- `api_client`: Synchronous FastAPI test client
- `async_api_client`: Asynchronous FastAPI test client

## Test Execution Strategy

### Daily Smoke Tests
Run quick validation tests:
```bash
pytest tests/e2e/test_dashboard_api.py tests/e2e/test_control_api.py -v
```

### Pre-Deployment Tests
Run full test suite:
```bash
pytest tests/e2e/ -v --cov --cov-report=html
```

### CI/CD Integration
Tests run automatically on:
- Every commit
- Pull requests
- Pre-deployment

## Success Criteria

### Critical Tests (Must Pass)
- ✅ All API endpoints respond correctly
- ✅ Paper mode prevents live trading
- ✅ Signal generation works correctly
- ✅ Trade execution in paper mode
- ✅ Mode switching maintains isolation
- ✅ Risk limits enforced

### Coverage Goals
- **API Coverage**: 100% of endpoints
- **Component Coverage**: 90%+ of critical paths
- **Workflow Coverage**: All major workflows

## Troubleshooting

### MongoDB Connection Issues
```bash
# Check if MongoDB is running
mongosh --eval "db.adminCommand('ping')"
```

### Redis Connection Issues
```bash
# Check if Redis is running
redis-cli ping
```

### Test Isolation Issues
Each test gets a unique database name to prevent conflicts. If you see database conflicts, check:
1. Test cleanup is working
2. Database names are unique
3. No tests are sharing state

## Contributing

When adding new tests:
1. Follow existing test structure
2. Use fixtures from `conftest.py`
3. Add appropriate markers (slow, integration, etc.)
4. Update this README if adding new test categories


