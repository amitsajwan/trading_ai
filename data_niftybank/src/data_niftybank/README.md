# data_niftybank

NIFTY/BANKNIFTY-focused data mini-module. It is standalone (no external services) and defines:
- Canonical instrument aliasing and validation
- Minimal contracts for market data ingestion/storage
- An in-memory market store suitable for unit tests

## Goals
- Keep the data surface independent of the rest of the repo
- Provide clear contracts before wiring Zerodha/Binance or Redis/Mongo
- Ship fast, deterministic unit tests

## Contents
- `aliases.py` — canonical symbols and helpers
- `contracts.py` — lightweight data models and interfaces
- `store.py` — in-memory implementation of `MarketStore`
- `adapters/redis_store.py` — Redis-backed `MarketStore` without global settings
- `adapters/zerodha_options_chain.py` — adapter around legacy Zerodha options fetcher
- `tests/data_niftybank` — unit tests for aliases, store, redis adapter, and options adapter

## Usage
```python
from data_niftybank.aliases import normalize_instrument
from data_niftybank.store import InMemoryMarketStore

symbol = normalize_instrument("Nifty Bank")  # -> "BANKNIFTY"
store = InMemoryMarketStore()
```

## Next steps
- Add real ingestion adapters (Zerodha/Binance) behind the `MarketIngestion` protocol
- Add Redis-backed `MarketStore` implementation
- Wire orchestration/services to depend only on these contracts
