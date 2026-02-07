# Dashboard Module Data Reference

## Complete Data Publishing and Consumption Specification

This document is the authoritative reference for all data structures, APIs, and real-time streams used by the Dashboard module. It serves as the single source of truth for the trading system web interface and its integration with backend services.

**Version:** 1.0.0
**Last Updated:** January 19, 2026
**Contact:** Dashboard Module Team

---

## 📊 Data Consumed by Dashboard Module

### Core Trading System Data (from Engine Module)

#### Trading Signals
**Source:** Redis pub/sub channels published by Engine Module
**Purpose:** Real-time trading signals for execution

| WebSocket Channel | Message Type | Description | Used By |
|-------------------|--------------|-------------|---------|
| `engine:signal:*` | `signal` | Individual trading signals | Signal widgets, TradingPage |
| `signals:*` | `signal` | Signal updates | ActiveSignalsWidget, SignalPage |
| `trading:signals:*` | `signal_batch` | Batch signal updates | OrchestratorDecisionsWidget |

**Signal Message Schema:**
```json
{
  "type": "signal",
  "signal_id": "sig_123456",
  "condition_id": "cond_789",
  "instrument": "BANKNIFTY",
  "action": "BUY",
  "confidence": 0.85,
  "timestamp": "2024-01-19T10:30:15.123456",
  "entry_price": 45250.75,
  "entry_price_source": "agent",
  "stop_loss": 45000.0,
  "take_profit": 45500.0,
  "reasoning": "Strong bullish momentum detected",
  "execution_mode": "CONDITIONAL",
  "parsed_conditions": [
    {"indicator": "rsi_14", "operator": ">", "threshold": 70}
  ]
}
```

#### Agent Analysis Results
**Source:** Redis pub/sub channels from Engine Module
**Purpose:** Agent decision analysis and reasoning

| WebSocket Channel | Message Type | Description | Used By |
|-------------------|--------------|-------------|---------|
| `engine:agent:*` | `agent_result` | Individual agent analysis | AgentStatusWidget, AgentDetailPage |
| `agent:*` | `agent_update` | Agent status updates | AgentResponsesWidget |

**Agent Result Schema:**
```json
{
  "type": "agent_result",
  "agent": "TechnicalAgent",
  "decision": "BUY",
  "confidence": 0.78,
  "details": {
    "thesis": "Strong uptrend with RSI momentum",
    "signals": ["uptrend_confirmed", "rsi_bullish"],
    "technical_signals": {
      "trend_direction": "UP",
      "rsi_level": 72.5
    }
  },
  "timestamp": "2024-01-19T10:30:15.123456"
}
```

#### Orchestrator Decisions
**Source:** Redis pub/sub channels from Engine Module
**Purpose:** Final trading decisions after agent consensus

| WebSocket Channel | Message Type | Description | Used By |
|-------------------|--------------|-------------|---------|
| `engine:decision` | `decision` | Final orchestrator decision | OrchestratorDecisionsWidget, TradingPage |
| `engine:orchestrator:*` | `decision_detail` | Detailed decision analysis | CurrentSignalWidget |

**Decision Schema:**
```json
{
  "type": "decision",
  "decision": "BUY",
  "confidence": 0.82,
  "reasoning": "Bullish consensus from 3/5 agents",
  "details": {
    "agent_results": [...],
    "consensus_score": 0.75,
    "risk_assessment": "moderate"
  },
  "timestamp": "2024-01-19T10:30:15.123456"
}
```

### Market Data (from Market Data Module)

#### Real-time Price Updates
**Source:** Redis pub/sub channels from Market Data Module
**Purpose:** Live price feeds for all widgets

| WebSocket Channel | Message Type | Description | Used By |
|-------------------|--------------|-------------|---------|
| `market:tick:*:INDEX` | `tick` | Index price updates | LiveTickDataWidget, MarketOverviewWidget |
| `market:tick:*:FUT` | `tick` | Futures price updates | LiveTickDataWidget |
| `market:tick:*:OPT` | `tick` | Options price updates | OptionsChainWidget |

**Tick Message Schema:**
```json
{
  "type": "tick",
  "instrument": "BANKNIFTY",
  "timestamp": "2024-01-19T10:30:15.123456",
  "last_price": 45250.75,
  "volume": 125000,
  "change": 125.50,
  "change_percent": 0.28
}
```

#### OHLC Chart Data
**Source:** Redis pub/sub channels from Market Data Module
**Purpose:** Candlestick charts and technical analysis

| WebSocket Channel | Message Type | Description | Used By |
|-------------------|--------------|-------------|---------|
| `market:ohlc:*` | `ohlc` | OHLC bar updates | AdvancedChartWidget, TechnicalIndicatorsWidget |

**OHLC Message Schema:**
```json
{
  "type": "ohlc",
  "instrument": "BANKNIFTY",
  "timeframe": "1min",
  "timestamp": "2024-01-19T10:30:00",
  "open": 45200,
  "high": 45300,
  "low": 45150,
  "close": 45250,
  "volume": 1000
}
```

#### Options Chain Data
**Source:** Redis pub/sub channels from Market Data Module
**Purpose:** Options analytics and strategy visualization

| WebSocket Channel | Message Type | Description | Used By |
|-------------------|--------------|-------------|---------|
| `market:options:*` | `options` | Options chain updates | OptionsChainWidget, OptionsStrategyWidget |

**Options Message Schema:**
```json
{
  "type": "options",
  "instrument": "BANKNIFTY",
  "expiry": "2024-01-30",
  "strikes": [
    {
      "strike": 45250,
      "CE": {
        "last_price": 125.5,
        "iv": 22.5,
        "delta": 0.65,
        "gamma": 0.02,
        "theta": -15.3,
        "vega": 8.7
      },
      "PE": {
        "last_price": 85.2,
        "iv": 21.8,
        "delta": -0.35
      }
    }
  ],
  "pcr": 1.15,
  "max_pain": 45250
}
```

#### Technical Indicators
**Source:** Redis pub/sub channels from Market Data Module
**Purpose:** Real-time technical analysis overlays

| WebSocket Channel | Message Type | Description | Used By |
|-------------------|--------------|-------------|---------|
| `indicators:*:INDEX` | `indicators` | Index indicators | TechnicalIndicatorsWidget |
| `indicators:*:FUT` | `indicators` | Futures indicators | TechnicalIndicatorsWidget |

**Indicators Message Schema:**
```json
{
  "type": "indicators",
  "instrument": "BANKNIFTY",
  "timestamp": "2024-01-19T10:30:15.123456",
  "indicators": {
    "rsi_14": 68.5,
    "macd_value": 125.75,
    "bollinger_upper": 45350.25,
    "trend_direction": "UP",
    "signal_strength": 75.2
  }
}
```

---

## 🌐 REST API Endpoints

**Base URL:** `http://localhost:8888/api/v1` (configurable)
**Authentication:** API key or JWT (configurable)

### Control API (`/api/control`)

#### GET `/api/control/status`
Get system control status.

**Response:**
```json
{
  "mode": "LIVE",
  "database": "connected",
  "balance": 1000000.0,
  "timestamp": "2024-01-19T10:30:15.123456"
}
```

#### GET `/api/control/mode/info`
Get execution mode information from Redis.

**Response:**
```json
{
  "mode": "LIVE",
  "run_id": "20240119_001",
  "instrument": "BANKNIFTY",
  "source": "redis"
}
```

#### POST `/api/control/mode/switch`
Switch between paper and live trading modes.

**Request:**
```json
{
  "mode": "paper",
  "confirm": true
}
```

**Response:**
```json
{
  "success": true,
  "mode": "paper",
  "confirmation_required": false
}
```

### Trading API (`/api/trading`)

#### GET `/api/trading/signals`
Get active trading signals.

**Parameters:**
- `instrument` (optional): Filter by instrument

**Response:**
```json
{
  "signals": [
    {
      "signal_id": "sig_123456",
      "instrument": "BANKNIFTY",
      "action": "BUY",
      "confidence": 0.85,
      "timestamp": "2024-01-19T10:30:15.123456",
      "entry_price": 45250.75,
      "stop_loss": 45000.0,
      "take_profit": 45500.0,
      "reasoning": "Strong bullish momentum",
      "execution_mode": "CONDITIONAL"
    }
  ]
}
```

#### GET `/api/trading/positions`
Get current portfolio positions.

**Response:**
```json
{
  "positions": [
    {
      "id": "pos_123",
      "instrument": "BANKNIFTY",
      "side": "BUY",
      "quantity": 25,
      "entry_price": 45000.0,
      "current_price": 45250.0,
      "pnl": 6250.0,
      "pnl_percent": 2.78,
      "timestamp": "2024-01-19T10:00:00.000000",
      "status": "open"
    }
  ]
}
```

#### POST `/api/trading/cycle`
Trigger manual trading cycle execution.

**Response:**
```json
{
  "success": true,
  "decision": "BUY",
  "confidence": 0.82,
  "error": null
}
```

### Market Data API (`/api/market`)

#### GET `/api/market/data/{instrument}`
Get market overview data for instrument.

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "current_price": 45250.75,
  "change_24h": 125.50,
  "change_percent_24h": 0.28,
  "volume_24h": 2500000,
  "high_24h": 45350.25,
  "low_24h": 44800.50,
  "vwap": 45125.30,
  "timestamp": "2024-01-19T10:30:15.123456",
  "status": "active"
}
```

#### GET `/api/market/ohlc/{instrument}`
Get OHLC candlestick data.

**Parameters:**
- `timeframe`: `1min`, `5min`, `15min`, `1h`, `daily` (default: `1min`)
- `limit`: Number of bars to return (default: 100)

**Response:**
```json
[
  {
    "instrument": "BANKNIFTY",
    "timeframe": "1min",
    "open": 45200,
    "high": 45300,
    "low": 45150,
    "close": 45250,
    "volume": 1000,
    "start_at": "2024-01-19T10:30:00"
  }
]
```

#### GET `/api/market/options/{instrument}`
Get complete options chain.

**Parameters:**
- `expiry`: Expiry date (YYYY-MM-DD)

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "expiry": "2024-01-30",
  "strikes": [...],
  "pcr": 1.15,
  "max_pain": 45250,
  "timestamp": "2024-01-19T10:30:15.123456"
}
```

### Risk Management API (`/api/risk`)

#### GET `/api/risk/portfolio-heat`
Get portfolio heat utilization summary.

**Response:**
```json
{
  "account_balance": 1000000.0,
  "active_positions": 3,
  "total_portfolio_heat": 25000.0,
  "max_portfolio_heat": 100000.0,
  "available_heat": 75000.0,
  "total_max_loss": -25000.0,
  "total_current_pnl": 7500.0,
  "daily_pnl": 1250.0,
  "weekly_pnl": 8750.0,
  "daily_loss_pct": -2.5,
  "weekly_loss_pct": -8.75,
  "can_trade": true
}
```

#### POST `/api/risk/approve-trade`
Request trade approval with Kelly sizing.

**Request:**
```json
{
  "instrument": "BANKNIFTY",
  "action": "BUY",
  "quantity": 50,
  "entry_price": 45250.0,
  "stop_loss": 44800.0,
  "take_profit": 45800.0,
  "confidence": 0.85
}
```

**Response:**
```json
{
  "decision": "approved",
  "reason": "Within risk limits",
  "approved_quantity": 35,
  "original_quantity": 50,
  "kelly_percentage": 70.0,
  "risk_amount": 20000.0,
  "portfolio_heat_used": 20000.0,
  "portfolio_heat_available": 55000.0,
  "timestamp": "2024-01-19T10:30:15.123456"
}
```

---

## ⚡ WebSocket Real-time Streams

**WebSocket URL:** `ws://localhost:8889/ws` (configurable via `VITE_WS_URL`)

### Connection Protocol

1. **Connect** to WebSocket endpoint
2. **Authenticate** (optional): Send `{"type": "auth", "token": "..."}`
3. **Subscribe** to channels: Send `{"type": "subscribe", "channels": ["channel1", "channel2"]}`
4. **Receive** real-time updates
5. **Unsubscribe** when done: Send `{"type": "unsubscribe", "channels": ["channel1"]}`

### Available Channels

#### Market Data Channels
- `market:tick:*:INDEX` - Index price ticks
- `market:tick:*:FUT` - Futures price ticks
- `market:tick:*:OPT` - Options price ticks
- `market:ohlc:*` - OHLC bar updates
- `market:options:*` - Options chain updates
- `indicators:*:INDEX` - Technical indicators

#### Trading System Channels
- `engine:signal:*` - Trading signals
- `engine:agent:*` - Agent analysis results
- `engine:decision` - Final orchestrator decisions
- `signals:*` - Signal updates
- `agent:*` - Agent status updates

### Message Format

All WebSocket messages follow this structure:

```json
{
  "type": "message_type",
  "channel": "channel_name",
  "data": {
    // Message-specific data
  },
  "timestamp": "2024-01-19T10:30:15.123456"
}
```

### Authentication & ACL

The WebSocket gateway enforces role-based access control:

```typescript
// User role channels
const userChannels = [
  "market:tick:*:INDEX",
  "market:tick:*:FUT",
  "market:tick:*:OPT",
  "indicators:*:INDEX",
  "indicators:*:FUT",
  "market:options:*",
  "market:depth:*",
  "engine:signal:*",
  "engine:agent:*",
  "engine:decision"
];

// Admin role (additional channels)
const adminChannels = [
  ...userChannels,
  "system:*",
  "admin:*"
];
```

---

## 🏪 Frontend State Management

### Redux Store Structure

The dashboard uses Redux for global state management with the following slices:

#### Market Data Slice
```typescript
interface MarketDataState {
  tickData: Record<string, TickData>;
  ohlcData: Record<string, OHLCData[]>;
  optionsChains: Record<string, OptionsChain>;
  marketOverview: MarketOverview | null;
  indicators: Record<string, IndicatorData>;
  loading: boolean;
  error: string | null;
}
```

#### Trading Slice
```typescript
interface TradingState {
  signals: TradingSignal[];
  positions: Position[];
  tradingStats: TradingStats | null;
  recentTrades: any[];
  activeSignal: TradingSignal | null;
  executionStatus: 'idle' | 'executing' | 'completed' | 'failed';
}
```

#### UI Slice
```typescript
interface UiState {
  theme: 'light' | 'dark';
  sidebarCollapsed: boolean;
  activePage: string;
  notifications: Notification[];
  modalState: ModalState;
}
```

### Data Services Architecture

The dashboard implements a multi-layered data services architecture:

```
Components (Presentation Layer)
    ↓ useData/useMarketTick hooks
Data Services Layer
    ├─ HybridDataService (HTTP + WS, seamless switching)
    │   ├─ HTTPDataService (REST API calls)
    │   ├─ WebSocketDataService (WS subscriptions)
    │   └─ DataCache (prevents flickering)
    └─ WebSocketMessageRouter (routes WS messages)
Redux Store (State Management)
    ↓ Redux slices for domain state
```

### Data Cache Strategy

To prevent UI flickering during data source transitions:

```typescript
interface DataCacheConfig {
  key: string;
  ttl: number; // Time-to-live in milliseconds
  maxSize: number; // Maximum cache entries
}

const cacheConfigs = {
  tickData: { ttl: 5 * 60 * 1000, maxSize: 100 }, // 5 minutes
  ohlcData: { ttl: 15 * 60 * 1000, maxSize: 50 },  // 15 minutes
  signals: { ttl: 2 * 60 * 1000, maxSize: 200 },   // 2 minutes
};
```

---

## ⚡ Performance Characteristics

### Latency Targets

| Operation | Target | Typical | Notes |
|-----------|--------|---------|-------|
| **WebSocket message delivery** | < 50ms | < 20ms | End-to-end from Redis pub/sub |
| **REST API response** | < 200ms | < 100ms | Including database queries |
| **UI re-render** | < 16ms | < 8ms | 60fps target |
| **Data cache hit** | < 1ms | < 0.5ms | In-memory cache access |
| **State update** | < 5ms | < 2ms | Redux state updates |

### Data Volume Estimates

| Data Type | Update Frequency | Peak Volume | Daily Volume |
|-----------|------------------|-------------|--------------|
| **Price ticks** | Per trade | 1000/sec | 86.4M ticks/day |
| **OHLC bars (1min)** | Per minute | 375 bars/hour | 9000 bars/day |
| **Trading signals** | Per cycle (15min) | 10-50 signals | 100-500 signals/day |
| **Agent updates** | Per analysis | 5-10 updates | 500-1000 updates/day |
| **Options chain** | Every 5min | 1MB | 288MB/day |

### WebSocket Throughput

| Channel Type | Sustained TPS | Peak TPS | Notes |
|-------------|---------------|----------|-------|
| **Market ticks** | 500 | 2000 | High-frequency data |
| **OHLC updates** | 50 | 200 | Time-based aggregation |
| **Signal updates** | 10 | 50 | Event-driven |
| **Agent results** | 20 | 100 | Analysis completion |

---

## 🚨 Error Handling

### HTTP Error Codes

- `200`: Success
- `400`: Bad Request (invalid parameters)
- `401`: Unauthorized (authentication required)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found (resource doesn't exist)
- `429`: Too Many Requests (rate limited)
- `500`: Internal Server Error
- `503`: Service Unavailable (Redis/MongoDB down)

### WebSocket Error Handling

**Connection failures:**
- Automatic reconnection (up to 10 attempts)
- Exponential backoff (1s, 2s, 4s, 8s, 16s, 32s...)
- Graceful degradation to HTTP polling

**Message errors:**
```json
{
  "type": "error",
  "code": "INVALID_CHANNEL",
  "message": "Channel 'invalid:channel' not allowed",
  "timestamp": "2024-01-19T10:30:15.123456"
}
```

**Rate limiting:**
```json
{
  "type": "error",
  "code": "RATE_LIMITED",
  "message": "Too many messages per second",
  "retry_after": 5
}
```

### Frontend Error Boundaries

The dashboard implements comprehensive error boundaries:

```typescript
// Component-level error boundary
class WidgetErrorBoundary extends React.Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} />;
    }
    return this.props.children;
  }
}

// Global error handler
window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason);
  // Log to monitoring service
});
```

---

## 💡 Integration Examples

### React Component with Real-time Data

```typescript
import React from 'react';
import { useData } from '../hooks/useData';

interface LiveTickWidgetProps {
  instrument: string;
}

const LiveTickWidget: React.FC<LiveTickWidgetProps> = ({ instrument }) => {
  const { data, loading, error, isRealTime } = useData({
    key: `tick:${instrument}`,
    fetchInitial: () => api.getTickData(instrument),
    wsChannel: `market:tick:${instrument}:INDEX`,
    cacheTTL: 5 * 60 * 1000, // 5 minutes
  });

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div className="tick-widget">
      <h3>{instrument}</h3>
      <div className="price">{data?.last_price}</div>
      <div className="change">{data?.change_percent}%</div>
      <div className="status">
        {isRealTime ? '🟢 Live' : '🟡 Cached'}
      </div>
    </div>
  );
};
```

### WebSocket Subscription Management

```typescript
import { WebSocketDataService } from '../services/data/WebSocketDataService';

class DashboardController {
  private wsService: WebSocketDataService;
  private subscriptions: Set<string> = new Set();

  constructor(wsService: WebSocketDataService) {
    this.wsService = wsService;
  }

  subscribeToInstrument(instrument: string) {
    const channels = [
      `market:tick:${instrument}:INDEX`,
      `indicators:${instrument}:INDEX`,
      `market:ohlc:${instrument}:1min`
    ];

    channels.forEach(channel => {
      if (!this.subscriptions.has(channel)) {
        this.wsService.subscribe(channel, this.handleMessage.bind(this));
        this.subscriptions.add(channel);
      }
    });
  }

  private handleMessage(channel: string, data: any) {
    // Route message to appropriate Redux action
    switch (channel.split(':')[0]) {
      case 'market':
        store.dispatch(updateMarketData({ channel, data }));
        break;
      case 'indicators':
        store.dispatch(updateIndicators({ channel, data }));
        break;
    }
  }
}
```

### API Client Usage

```typescript
import { TradingAPIClient } from '../api/types';

// Initialize client
const apiClient = new TradingAPIClient('http://localhost:8888/api/v1');

// Get trading signals
const signals = await apiClient.getSignals('BANKNIFTY');

// Execute trade
const result = await apiClient.runTradingCycle();

// Monitor positions
const positions = await apiClient.getPositions();
```

---

## 📊 Data Quality & Validation

### Data Validation Rules

**Real-time Data:**
- Price ticks must be positive numbers within ±50% of previous price
- Timestamps must be valid ISO 8601 and not in the future
- Volume must be non-negative integers

**Trading Data:**
- Signal confidence must be between 0.0 and 1.0
- Position quantities must be positive integers
- P&L calculations must be mathematically correct

**Options Data:**
- Strike prices must be positive
- Greeks must be within reasonable bounds (-2.0 to 2.0 for delta/gamma)
- Implied volatility must be between 1% and 500%

### Data Freshness Monitoring

**Critical Data Freshness:**
- Market prices: < 5 seconds old
- Trading signals: < 30 seconds old
- Agent results: < 1 minute old
- Options data: < 5 minutes old

**Stale Data Handling:**
```typescript
const DATA_FRESHNESS_THRESHOLDS = {
  tick: 5 * 1000,      // 5 seconds
  signal: 30 * 1000,   // 30 seconds
  agent: 60 * 1000,    // 1 minute
  options: 300 * 1000, // 5 minutes
};

function isDataStale(data: any, type: keyof typeof DATA_FRESHNESS_THRESHOLDS): boolean {
  const threshold = DATA_FRESHNESS_THRESHOLDS[type];
  const dataAge = Date.now() - new Date(data.timestamp).getTime();
  return dataAge > threshold;
}
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Dashboard Server
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8888

# WebSocket Gateway
VITE_WS_URL=ws://localhost:8889/ws

# Backend Services
REDIS_HOST=localhost
REDIS_PORT=6379
MONGODB_URI=mongodb://localhost:27017/zerodha_trading

# Authentication
REQUIRE_AUTH=false
API_KEY=your_api_key_here

# Data Cache
DATA_CACHE_TTL_TICK=300000      # 5 minutes
DATA_CACHE_TTL_OHLC=900000      # 15 minutes
DATA_CACHE_TTL_SIGNALS=120000   # 2 minutes

# WebSocket
WS_RECONNECT_ATTEMPTS=10
WS_RECONNECT_INTERVAL=1000      # 1 second base
WS_MAX_MESSAGE_RATE=1000        # messages per second
```

### Feature Flags

```typescript
const FEATURE_FLAGS = {
  ENABLE_REAL_TIME_UPDATES: true,
  ENABLE_DATA_CACHING: true,
  ENABLE_RISK_MANAGEMENT: true,
  ENABLE_PAPER_TRADING: true,
  ENABLE_SIGNAL_EXECUTION: false, // Use with caution
  ENABLE_DEBUG_LOGGING: process.env.NODE_ENV === 'development'
};
```

---

## 📞 Support & Contact

For questions about:
- **Data structures**: See this document
- **API integration**: Check `/api/types.ts` and `/api/dashboardApi.ts`
- **Real-time data**: Review WebSocket gateway configuration
- **UI components**: Check component documentation in `/src/components/`

**Health Endpoints:**
- Dashboard health: `GET /health`
- System health: `GET /api/v1/health`
- WebSocket health: Check gateway logs

**Monitoring:**
- Error logs: Check browser console and server logs
- Performance: Use browser dev tools network tab
- Data flow: Monitor WebSocket messages in dev tools

---

**This is the complete and authoritative reference for Dashboard module data structures and APIs. For implementation questions or data access requests, please contact the Dashboard module team.**