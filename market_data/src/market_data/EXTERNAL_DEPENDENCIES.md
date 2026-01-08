# External Dependencies

This document outlines the external dependencies required by the `market_data` module adapters.

## Overview

The `market_data` module is designed to be **protocol-based and independent** for testing, but certain adapters integrate with external services that may not be available in all environments. All external dependencies are imported **dynamically** within adapter methods to allow the module to function even when these dependencies are unavailable.

## External Dependencies

### Zerodha Integration

The following adapters require Zerodha KiteConnect and related services:

#### 1. `adapters/zerodha_ingestion.py`
**External Module**: `data.ingestion_service.DataIngestionService`

**Purpose**: Real-time market data ingestion via Zerodha WebSocket

**Import Location**: Dynamically imported in `start()` method
```python
from data.ingestion_service import DataIngestionService
```

**Requirements**:
- `KiteConnect` instance with valid access token
- `MarketMemory` instance for caching
- Market hours for live data

**Fallback**: Module can function without this adapter for historical/offline testing

---

#### 2. `adapters/zerodha_options_chain.py`
**External Module**: `data.options_chain_fetcher.OptionsChainFetcher`

**Purpose**: Options chain data from Zerodha

**Import Location**: No direct import - wraps externally provided fetcher instance

**Requirements**:
- `KiteConnect` instance
- `OptionsChainFetcher` instance (created externally)
- Options market access

**Fallback**: Module provides protocol contract; actual implementation depends on external fetcher

---

#### 3. `adapters/historical_replay.py` (LTPDataAdapter)
**External Module**: `data.ltp_data_collector.LTPDataCollector`

**Purpose**: REST API-based LTP data collection

**Import Location**: Dynamically imported in `start()` method
```python
from data.ltp_data_collector import LTPDataCollector
```

**Requirements**:
- `KiteConnect` instance with valid access token
- `MarketMemory` instance

**Fallback**: Historical replay works with CSV/synthetic data without this

---

### API Documentation References

The `api.py` file contains examples that reference external modules:

- `data.options_chain_fetcher.OptionsChainFetcher` - used in `build_options_client()` docstring
- `data.market_memory.MarketMemory` - used in multiple factory function docstrings

These are **documentation only** - actual imports happen dynamically in adapters.

---

## Design Principles

1. **Dynamic Imports**: All external dependencies are imported only when needed, allowing the module to load without them
2. **Protocol-Based**: Core contracts (`MarketStore`, `MarketIngestion`, etc.) don't depend on external services
3. **Graceful Degradation**: Adapters handle missing dependencies gracefully with appropriate logging
4. **Testing Independence**: Unit tests can run without any external dependencies

## Testing Without External Dependencies

The module is fully testable without external dependencies:

- Use `InMemoryMarketStore` instead of `RedisMarketStore`
- Use `HistoricalDataReplay` with synthetic data instead of `ZerodhaIngestionAdapter`
- Use mock `OptionsData` implementations instead of `ZerodhaOptionsChainAdapter`

## Migration Notes

If external dependencies need to be removed or replaced:

1. All external imports are isolated to adapter files
2. Protocol contracts remain unchanged
3. New adapters can be created following the same protocol interfaces
4. Existing tests validate protocol compliance, not implementation details

