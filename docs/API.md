# API Reference

API documentation for the GenAI Trading System components.

## Monitoring Dashboard API

The monitoring dashboard exposes a FastAPI-based REST API.

### Base URL

```
http://localhost:8888
```

### Endpoints

#### GET `/health`

System health check.

**Response**:
```json
{
    "status": "healthy",
    "mongodb": "connected",
    "redis": "connected",
    "data_feed": "receiving_data",
    "agents": "active"
}
```

#### GET `/api/system-status`

Get comprehensive system status.

**Response**:
```json
{
    "mongodb": {
        "status": "healthy",
        "connected": true,
        "trades_count": 10,
        "ohlc_count": 1000
    },
    "redis": {
        "status": "healthy",
        "connected": true,
        "ticks_count": 500,
        "ohlc_count": 100
    },
    "market_data": {
        "status": "healthy",
        "current_price": 60123.45,
        "data_source": "Zerodha"
    },
    "agents": {
        "status": "healthy",
        "count": 12,
        "llm_provider": "groq"
    },
    "data_feed": {
        "status": "healthy",
        "source": "Zerodha",
        "receiving_data": true
    }
}
```

#### GET `/api/market-data`

Get current market data.

**Response**:
```json
{
    "current_price": 60123.45,
    "data_source": "Zerodha",
    "market_open": true,
    "redis_available": true,
    "timestamp": "2024-01-15T10:30:00"
}
```

#### GET `/api/latest-analysis`

Get latest agent analysis.

**Response**:
```json
{
    "timestamp": "2024-01-15T10:30:00",
    "final_signal": "HOLD",
    "current_price": 60123.45,
    "agents": {
        "technical": {
            "rsi": 77.12,
            "rsi_status": "OVERBOUGHT",
            "macd": 3.25,
            "macd_status": "BULLISH",
            "trend_direction": "UP",
            "confidence_score": 0.85
        },
        "fundamental": {
            "sector_strength": "MODERATE",
            "bullish_probability": 0.55,
            "bearish_probability": 0.45
        },
        "sentiment": {
            "retail_sentiment": 0.0,
            "institutional_sentiment": 0.0,
            "sentiment_divergence": "NONE"
        },
        "macro": {
            "macro_regime": "MIXED",
            "rbi_cycle": "NEUTRAL",
            "sector_headwind_score": 0.0
        }
    },
    "agent_explanations": [
        "[technical]: Technical analysis: UP trend, RSI OVERBOUGHT, confidence 0.85",
        "[fundamental]: Fundamental analysis: MODERATE sector, bullish prob: 0.55"
    ]
}
```

#### GET `/api/trades`

Get recent trades.

**Query Parameters**:
- `limit` (optional): Number of trades to return (default: 10)

**Response**:
```json
{
    "trades": [
        {
            "trade_id": "trade_123",
            "signal": "BUY",
            "entry_price": 60000.0,
            "exit_price": 60300.0,
            "quantity": 15,
            "pnl": 4500.0,
            "timestamp": "2024-01-15T10:00:00"
        }
    ],
    "total": 10
}
```

## Data Collection APIs

### News Collector

**Component**: `data/news_collector.py`

**Methods**:
- `fetch_news(query: str, max_results: int) -> List[Dict]`: Fetch news from NewsAPI
- `collect_and_store()`: Collect and store news
- `run_continuous()`: Run continuous collection loop

### Macro Collector

**Component**: `data/macro_collector.py`

**Methods**:
- `store_rbi_rate(rate: float, announcement_date: datetime, notes: str)`: Store RBI repo rate
- `store_inflation_data(cpi: float, wpi: Optional[float], date: Optional[datetime])`: Store inflation data
- `store_npa_data(npa_ratio: float, date: Optional[datetime])`: Store NPA ratio
- `get_latest_macro_context() -> Dict`: Get latest macro context

## Market Memory API

**Component**: `data/market_memory.py`

**Methods**:
- `store_tick(instrument: str, tick_data: Dict)`: Store tick data
- `store_ohlc(instrument: str, timeframe: str, ohlc_data: Dict)`: Store OHLC candle
- `get_current_price(instrument: str) -> Optional[float]`: Get current price
- `get_recent_ohlc(instrument: str, timeframe: str, count: int) -> List[Dict]`: Get recent OHLC candles
- `store_sentiment_score(score: float, source: str)`: Store sentiment score
- `get_latest_sentiment(source: str) -> Optional[float]`: Get latest sentiment score

## Trading Service API

**Component**: `services/trading_service.py`

**Methods**:
- `initialize()`: Initialize all components
- `start()`: Start trading service
- `stop()`: Stop trading service gracefully

**Usage**:
```python
from services.trading_service import TradingService
from kiteconnect import KiteConnect

kite = KiteConnect(api_key="...")
kite.set_access_token("...")

service = TradingService(kite=kite)
await service.start()
```

## Trading Graph API

**Component**: `trading_orchestration/trading_graph.py`

**Methods**:
- `arun()`: Run trading graph (async)
- `run()`: Run trading graph (sync)

**Usage**:
```python
from trading_orchestration.trading_graph import TradingGraph
from data.market_memory import MarketMemory

market_memory = MarketMemory()
graph = TradingGraph(kite=kite, market_memory=market_memory)

result = await graph.arun()
```

## State Manager API

**Component**: `trading_orchestration/state_manager.py`

**Methods**:
- `initialize_state() -> AgentState`: Initialize state from market data
- `update_state_from_market(state: AgentState) -> AgentState`: Update state with latest data

**Usage**:
```python
from trading_orchestration.state_manager import StateManager
from data.market_memory import MarketMemory

market_memory = MarketMemory()
state_manager = StateManager(market_memory)

state = state_manager.initialize_state()
```

## Agent API

All agents inherit from `BaseAgent` and implement:

**Methods**:
- `process(state: AgentState) -> AgentState`: Process state and return updated state

**Usage**:
```python
from agents.technical_agent import TechnicalAnalysisAgent
from agents.state import AgentState

agent = TechnicalAnalysisAgent()
state = AgentState(...)
updated_state = agent.process(state)
```

## MongoDB Collections

### Collections

- `ohlc_history`: Historical OHLC data
- `market_events`: News articles and macro events
- `strategy_parameters`: Macro context and strategy parameters
- `trades`: Executed trades
- `agent_decisions`: Agent analysis outputs

### Query Examples

**Get Latest OHLC**:
```python
from mongodb_schema import get_mongo_client, get_collection

client = get_mongo_client()
db = client["zerodha_trading"]
ohlc_collection = get_collection(db, "ohlc_history")

latest = ohlc_collection.find_one(
    {"instrument": "BANKNIFTY"},
    sort=[("timestamp", -1)]
)
```

**Get Recent Trades**:
```python
trades_collection = get_collection(db, "trades")
recent_trades = trades_collection.find().sort("timestamp", -1).limit(10)
```

**Get Latest Agent Analysis**:
```python
decisions_collection = get_collection(db, "agent_decisions")
latest_analysis = decisions_collection.find_one(
    sort=[("timestamp", -1)]
)
```

## Redis Keys

### Key Patterns

- `tick:{instrument}:{timestamp}`: Individual tick data
- `ohlc:{instrument}:{timeframe}:{timestamp}`: OHLC candle data
- `ohlc_sorted:{instrument}:{timeframe}`: Sorted set for time-series queries
- `price:{instrument}:latest`: Latest price (5-min TTL)
- `sentiment:{source}:{timestamp}`: Sentiment scores

### Access Examples

```python
import redis
import json

r = redis.Redis(host='localhost', port=6379, db=0)

# Get latest price
price = r.get("price:BANKNIFTY:latest")

# Get recent OHLC candles
candles = r.zrange("ohlc_sorted:BANKNIFTY:1min", -60, -1)
```

## Error Handling

All APIs include error handling:

- **Connection Errors**: Retry logic with exponential backoff
- **API Errors**: Logged and returned in response
- **Validation Errors**: Returned with error details

## Rate Limiting

- **LLM APIs**: Rate limits vary by provider
- **Zerodha API**: Rate limits apply (check Zerodha documentation)
- **News API**: Rate limits apply (check NewsAPI documentation)

## Authentication

- **Zerodha**: OAuth2 flow via `auto_login.py`
- **LLM Providers**: API keys in `.env` file
- **MongoDB**: Connection string in `.env`
- **Redis**: No authentication by default (configure if needed)

## WebSocket APIs

### Zerodha WebSocket

**Component**: `data/ingestion_service.py`

**Connection**: Established automatically by `DataIngestionService`

**Subscriptions**: Bank Nifty instrument token

**Messages**: Tick data in real-time

## Integration Examples

### Custom Agent

```python
from agents.base_agent import BaseAgent
from agents.state import AgentState

class CustomAgent(BaseAgent):
    def __init__(self):
        super().__init__("custom", "Your prompt")
    
    def process(self, state: AgentState) -> AgentState:
        # Your logic
        return state
```

### Custom Data Collector

```python
from data.market_memory import MarketMemory

class CustomCollector:
    def __init__(self, market_memory: MarketMemory):
        self.market_memory = market_memory
    
    def collect_data(self):
        # Your collection logic
        self.market_memory.store_tick("BANKNIFTY", tick_data)
```

