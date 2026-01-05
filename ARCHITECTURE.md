# Trading AI System Architecture

## Overview

This trading system is split into independent domain modules with clear contracts, enabling delegation to specialized agents and parallel development.

## Module Structure

Each module follows the pattern:
```
module_name/
├── src/module_name/
│   ├── __init__.py
│   ├── contracts.py       # Protocol-based contracts
│   ├── api.py             # Public facade (build_* factories)
│   ├── adapters/          # Legacy wrappers, external integrations
│   └── ...
└── tests/
    ├── conftest.py
    ├── test_*.py          # Unit tests
    └── integration/       # Integration tests (@pytest.mark.integration)
```

### 1. data_niftybank

**Purpose**: Market data ingestion and storage for NIFTY/BANKNIFTY  
**Contracts**: `MarketStore`, `MarketIngestion`, `OptionsData`  
**Key Components**:
- `InMemoryMarketStore`: In-memory tick/OHLC storage (tests, dev)
- `RedisMarketStore`: Production Redis-backed storage
- `ZerodhaOptionsChainAdapter`: Wraps legacy `options_chain_fetcher.py`

**API Facade** ([data_niftybank/src/data_niftybank/api.py](data_niftybank/src/data_niftybank/api.py)):
```python
from data_niftybank.api import build_store, build_options_client

store = build_store(redis_client=None)  # in-memory
chain = build_options_client(kite, fetcher)
```

**Dependencies**: Redis (optional), Kite API  
**Test Layers**:
- Unit: `test_store.py`, `test_aliases.py`
- Integration: `test_redis_roundtrip.py`, `test_options_fakekite.py`

---

### 2. genai_module

**Purpose**: Complete LLM intelligence layer with provider orchestration and prompt management
**Contracts**: `LLMClient`, `PromptStore`, `LLMProviderManager`
**Key Components**:
- `LLMProviderManager`: Full multi-provider orchestration with single-provider optimization
- `ProviderManagerClient`: Protocol adapter for LLMClient interface
- `FilePromptStore`: File-based prompt versioning
- `PromptManagerStore`: MongoDB-backed prompt management
- **Single Provider Mode**: Optimized performance with intelligent failover

**API Facade** ([genai_module/src/genai_module/api.py](genai_module/src/genai_module/api.py)):
```python
from genai_module.api import build_llm_client, build_prompt_store
from genai_module import LLMProviderManager

# Direct provider management (recommended)
manager = LLMProviderManager()  # Auto-configured with single provider mode
response = manager.call_llm("system prompt", "user message")

# Protocol-based client (for engine integration)
client = build_llm_client(manager)
response = await client.generate(LLMRequest(prompt="Analyze trend"))

# Prompt management
store = build_prompt_store(file_root="./prompts")
```

**Dependencies**: OpenAI/Groq/Google/Cohere/AI21/HuggingFace APIs, MongoDB (optional)
**Test Layers**:
- Unit: Provider orchestration, protocol adapters, prompt management
- Integration: `scripts/test_api_keys.py` for all provider validation

---

### 3. engine_module

**Purpose**: Trading orchestration and agent coordination  
**Contracts**: `Orchestrator`, `Agent`, `AnalysisResult`  
**Key Components**:
- `TradingOrchestrator`: Coordinates data fetch, agent analysis, LLM decision
- Agents: Technical, Sentiment, Macro (contracts only, implementations pending)

**API Facade** ([engine_module/src/engine_module/api.py](engine_module/src/engine_module/api.py)):
```python
from engine_module.api import build_orchestrator
from data_niftybank.api import build_store, build_options_client
from genai_module.api import build_llm_client

orchestrator = build_orchestrator(
    llm_client=llm,
    market_store=store,
    options_data=chain,
    agents=[...]  # agent list
)

result = await orchestrator.run_cycle({"instrument": "NIFTY"})
```

**Dependencies**: `data_niftybank`, `genai_module`  
**Test Layers**:
- Unit: `test_api_stub.py` (mocked dependencies)
- Integration: Pending (end-to-end cycle with real data)

---

### 4. core_kernel

**Purpose**: Dependency injection and service lifecycle  
**Contracts**: `ServiceContainer`, `ComponentFactory`  
**Status**: Contracts scaffolded, no implementations yet

**Planned Usage**:
```python
container = ServiceContainer()
container.register("llm_client", build_llm_client(...))
container.register("market_store", build_store(...))

orchestrator = container.resolve("orchestrator")
```

---

### 5. ui_shell

**Purpose**: UI boundary for dashboard/CLI  
**Contracts**: `UIDataProvider`, `UIDispatcher`  
**Status**: Contracts scaffolded, no implementations yet

**Planned Flow**:
- Dashboard queries `UIDataProvider.get_latest_decision()` → Engine state
- User action → `UIDispatcher.submit_override()` → Engine override

---

### 6. user_module

**Purpose**: User account management, portfolio tracking, and risk-managed trade execution
**Contracts**: `UserAccount`, `RiskProfile`, `Position`, `Trade`, `TradeExecutionRequest`, `TradeResult`, `UserStore`, `PortfolioStore`, `TradeStore`, `RiskManager`, `TradeExecutor`, `PnLAnalytics`
**Key Components**:
- `MongoUserStore`: User accounts and risk profiles in MongoDB
- `MongoPortfolioStore`: Position and balance tracking
- `MongoTradeStore`: Complete trade history
- `PortfolioRiskManager`: Pre-trade risk validation and position sizing
- `MockBrokerTradeExecutor`: Risk-aware trade execution (mock broker)
- `PnLCalculator`: Performance analytics and reporting

**API Facade** ([user_module/src/user_module/api.py](user_module/src/user_module/api.py)):
```python
from user_module.api import build_user_module, create_user_account, execute_user_trade

user_service = build_user_module(mongo_client=mongo_client)
user = await create_user_account(email="user@example.com", risk_profile=risk_profile)
result = await execute_user_trade(user_id=user.user_id, instrument="BANKNIFTY", action="BUY", quantity=25)
```

**Dependencies**: MongoDB
**Test Layers**:
- Unit: `test_user_module.py` (user creation, risk validation, trade execution)
- Integration: Pending (MongoDB roundtrip tests)

---

## Data Flow

```
┌─────────────┐
│   UI Shell  │ (Dashboard, CLI)
└──────┬──────┘
       │ UIDataProvider.get_latest_decision()
       ▼
┌──────────────────┐
│ Engine Module    │ (Orchestrator, Agents)
│  ┌─────────────┐ │
│  │ run_cycle() │ │
│  └──────┬──────┘ │
└─────────┼────────┘
          │
    ┌─────┼──────┐
    │     │      │
    ▼     ▼      ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│ Data    │ │ GenAI   │ │ User    │
│ Module  │ │ Module  │ │ Module  │
│ Market  │ │ LLM     │ │ Portfolio│
│ Store   │ │ Client  │ │ Trading │
└────┬────┘ └────┬────┘ └────┬────┘
     │           │           │
     ▼           ▼           ▼
  Redis      OpenAI/Groq    MongoDB
  Kite API
```

### Execution Flow (One Trading Cycle)

1. **Trigger**: Timer or manual trigger calls `orchestrator.run_cycle(context)`
2. **Data Fetch**:
   - `market_store.get_latest_ticks(instrument)` → NIFTY/BANKNIFTY ticks
   - `options_data.fetch_chain(instrument, expiry)` → Options chain
3. **Agent Analysis**:
   - Technical Agent: Analyzes ticks/OHLC for patterns
   - Sentiment Agent: Analyzes news sentiment
   - Macro Agent: Analyzes inflation/RBI data
   - Each returns `AnalysisResult(decision, confidence, reasoning)`
4. **Aggregation**: Orchestrator aggregates agent results
5. **LLM Decision**:
   - Build prompt from aggregated data
   - `llm_client.request(LLMRequest(...))` → Final decision
6. **Return**: `AnalysisResult` with BUY/SELL/HOLD, confidence, reasoning
7. **UI Update**: Dashboard polls `UIDataProvider` for latest result

---

## Dependency Injection Points

| Module | Injected Dependency | Source | Lifecycle |
|--------|---------------------|--------|-----------|
| Engine | `llm_client: LLMClient` | `genai_module.api.build_llm_client()` | Singleton |
| Engine | `market_store: MarketStore` | `data_niftybank.api.build_store()` | Singleton |
| Engine | `options_data: OptionsData` | `data_niftybank.api.build_options_client()` | Singleton |
| Engine | `agents: list[Agent]` | Agent factories (pending) | Per-orchestrator |
| GenAI | `legacy_manager: LLMProviderManager` | Legacy codebase | Singleton |
| GenAI | `prompt_manager: PromptManager` | Legacy codebase (optional) | Singleton |
| Data | `redis_client: redis.Redis` | External service | Singleton |
| Data | `kite: KiteConnect` | Zerodha SDK | Singleton |
| User | `mongo_client: MongoClient` | External service | Singleton |
| User | `user_store: UserStore` | `user_module.stores.MongoUserStore` | Singleton |
| User | `portfolio_store: PortfolioStore` | `user_module.stores.MongoPortfolioStore` | Singleton |
| User | `trade_store: TradeStore` | `user_module.stores.MongoTradeStore` | Singleton |

**Wiring Example** (Full Stack):
```python
# 1. External dependencies
import redis
from kiteconnect import KiteConnect

redis_client = redis.Redis(host="localhost", port=6379, db=0)
kite = KiteConnect(api_key="...")

# 2. Legacy adapters
from genai_module import LLMProviderManager
from data.options_chain_fetcher import OptionsChainFetcher

legacy_llm = LLMProviderManager()
legacy_fetcher = OptionsChainFetcher()

# 3. Module factories
from data_niftybank.api import build_store, build_options_client
from genai_module.api import build_llm_client
from engine_module.api import build_orchestrator

market_store = build_store(redis_client=redis_client)
options_data = build_options_client(kite=kite, fetcher=legacy_fetcher)
llm_client = build_llm_client(legacy_manager=legacy_llm)

# 4. Orchestrator
orchestrator = build_orchestrator(
    llm_client=llm_client,
    market_store=market_store,
    options_data=options_data,
)

# 5. Run cycle
result = await orchestrator.run_cycle({"instrument": "NIFTY"})
print(result.decision, result.confidence)
```

---

## Test Layers

### Unit Tests
- **Scope**: Single module, no external services
- **Markers**: None (default pytest execution)
- **Examples**:
  - `data_niftybank/tests/test_store.py`: InMemoryMarketStore logic
  - `genai_module/tests/test_provider_adapter.py`: ProviderManagerClient wrapper
  - `engine_module/tests/test_api_stub.py`: Orchestrator with mocked deps
  - `user_module/tests/test_user_module.py`: User account creation and risk validation

**Run**: `pytest` (runs all unit tests)

### Integration Tests
- **Scope**: Module + external service (Redis, MongoDB, Kite API)
- **Markers**: `@pytest.mark.integration`, `@pytest.mark.data_integration`, `@pytest.mark.genai_integration`
- **Examples**:
  - `data_niftybank/tests/integration/test_redis_roundtrip.py`: Redis tick/OHLC storage
  - `data_niftybank/tests/integration/test_options_fakekite.py`: Zerodha adapter with FakeKite

**Run**: `pytest -m integration` (requires services via `docker-compose.data.yml`)

---

## Environment & Services

| Service | Purpose | Module | Integration Test Dependency |
|---------|---------|--------|------------------------------|
| Redis | Tick/OHLC storage | data_niftybank | Yes (`test_redis_roundtrip.py`) |
| MongoDB | Prompt storage (optional) | genai_module | No (uses FilePromptStore) |
| MongoDB | User accounts & portfolios | user_module | Yes (planned integration tests) |
| Zerodha Kite API | Live/historical data | data_niftybank | Yes (uses FakeKite in tests) |
| OpenAI/Groq API | LLM inference | genai_module | No (mocked in tests) |

**Docker Compose** ([docker-compose.data.yml](docker-compose.data.yml)):
- Redis: `localhost:6379`
- MongoDB: `localhost:27017`

**Start Services**: `docker-compose -f docker-compose.data.yml up -d`  
**Stop Services**: `docker-compose -f docker-compose.data.yml down`

---

## Migration Strategy

### Phase 1: Module Scaffolding ✅
- Create contracts, adapters, API facades
- Wrap legacy code without modification
- Add unit tests for new code

### Phase 2: Integration ✅ (Current)
- Add integration tests for adapters
- Wire modules together (Engine → Data, GenAI)
- Orchestrator stub with TODOs

### Phase 3: Agent Implementation (Next)
- Implement Technical/Sentiment/Macro agents
- Add agent-specific tests
- Wire agents into Orchestrator

### Phase 4: End-to-End Testing
- Full cycle integration tests
- Performance benchmarks
- Dashboard wiring via UIDataProvider

### Phase 5: Legacy Replacement
- Gradually replace legacy `agents/`, `data/`, `services/` with module equivalents
- Deprecate old imports
- Remove unused legacy code

---

## Key Principles

1. **Contracts First**: All modules define Protocol-based contracts before implementation
2. **Dependency Injection**: No module instantiates its own dependencies; use factories
3. **Adapter Pattern**: Wrap legacy code via adapters; never modify legacy files
4. **Test Isolation**: Unit tests use mocks; integration tests use real services
5. **Stable APIs**: Consumers import from `module.api`, never from `module.adapters` directly
6. **Incremental Migration**: New features use modules; old code remains until replaced

---

## Quick Start

### Run All Tests
```bash
# Unit tests only (no external services)
pytest

# With integration tests (requires docker-compose.data.yml)
docker-compose -f docker-compose.data.yml up -d
pytest -m integration
```

### Wire Full Stack (Minimal Example)
```python
from data_niftybank.api import build_store
from genai_module.api import build_llm_client
from engine_module.api import build_orchestrator
from genai_module import LLMProviderManager

# In-memory store (no Redis)
store = build_store()

# LLM client with legacy provider
llm = build_llm_client(legacy_manager=LLMProviderManager())

# Orchestrator (stub implementation)
orchestrator = build_orchestrator(
    llm_client=llm,
    market_store=store,
    options_data=None,  # Optional
)

# Run stub cycle
result = await orchestrator.run_cycle({"instrument": "NIFTY"})
print(result.decision)  # "HOLD" (stub)
```

---

## References

- Module READMEs:
  - [data_niftybank/README.md](data_niftybank/README.md)
  - [genai_module/README.md](genai_module/README.md)
  - [engine_module/README.md](engine_module/README.md)
- Legacy Code:
  - [agents/llm_provider_manager.py](agents/llm_provider_manager.py) (1290 LOC)
  - [data/options_chain_fetcher.py](data/options_chain_fetcher.py)
  - [config/prompt_manager.py](config/prompt_manager.py)
- Docker: [docker-compose.data.yml](docker-compose.data.yml)
- CI: [pytest.ini](pytest.ini) (integration markers)
