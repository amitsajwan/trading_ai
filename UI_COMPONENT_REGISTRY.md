# UI Component Registry - Layer 9 Task 9.1 Deliverable

## Overview
This registry documents the current UI architecture for the autonomous algorithmic trading platform. The UI is built with React + TypeScript + Vite + Tailwind, using Redux/RTK Query for state management and WebSocket for real-time updates.

## Architecture Summary

### Frontend Stack
- **Framework:** React 18 + TypeScript
- **Build Tool:** Vite
- **Styling:** Tailwind CSS
- **State Management:** Redux Toolkit + RTK Query
- **Real-time:** WebSocket (connects to redis_ws_gateway on port 8889)
- **Testing:** Playwright (E2E)

### Backend Integration
- **API:** FastAPI (dashboard/app.py)
- **Data Contracts:** ui_shell/contracts.py (DecisionDisplay, PortfolioSummary, etc.)
- **Data Providers:** ui_shell/providers.py (EngineDataProvider with mock interface)

---

## Component Inventory

### Pages (8 total)
Located in: `dashboard/modular_ui/src/pages/`

1. **DashboardPage** - Main dashboard with widget grid
2. **TradingPage** - Trading interface with signals and execution
3. **MarketDataPage** - Market data visualization (charts, options chain)
4. **PortfolioPage** - Portfolio management and P&L tracking
5. **SettingsPage** - System configuration and preferences
6. **LogsPage** - System logs and activity monitoring
7. **AnalyticsPage** - Performance analytics and reporting
8. **AgentMonitorPage** - Real-time agent status and monitoring

### Widgets (17 total)
Located in: `dashboard/modular_ui/src/components/widgets/`

1. **MarketOverviewWidget** - Key market indicators (NIFTY, BANKNIFTY prices)
2. **PortfolioWidget** - Portfolio summary (P&L, positions, balance)
3. **DecisionWidget** - Latest trading decision display
4. **SignalsWidget** - Active trading signals list
5. **AgentStatusWidget** - Agent health and status indicators
6. **TechnicalIndicatorsWidget** - Technical analysis charts
7. **OptionsChainWidget** - Options chain data and analysis
8. **OrderFlowWidget** - Order book and market depth
9. **RecentTradesWidget** - Recent trade history
10. **RiskMetricsWidget** - Risk management indicators
11. **PerformanceWidget** - Trading performance metrics
12. **NewsWidget** - Market news and sentiment
13. **StrategyWidget** - Active strategy monitoring
14. **AlertsWidget** - System alerts and notifications
15. **ChartWidget** - Price charts with indicators
16. **HeatmapWidget** - Market sector heatmaps
17. **CorrelationWidget** - Asset correlation analysis

### Store Slices (6 total)
Located in: `dashboard/modular_ui/src/store/slices/`

1. **marketDataSlice** - Market data state (ticks, OHLC, options chain)
2. **tradingSlice** - Trading state (decisions, portfolio, signals, trades)
3. **uiSlice** - UI state (notifications, theme, layout)
4. **agentSlice** - Agent monitoring state
5. **analyticsSlice** - Analytics and reporting data
6. **settingsSlice** - User preferences and configuration

### Hooks (2 total)
Located in: `dashboard/modular_ui/src/hooks/`

1. **useWebSocket** - WebSocket connection management and real-time updates
2. **useTheme** - Theme management (light/dark mode)

---

## API Integration Status

### Backend Endpoints (FastAPI)
Located in: `dashboard/api/`

#### Trading API (`/api/trading/*`)
- `POST /cycle` - Run trading cycle (proxies to engine API)
- `GET /signals` - Get trading signals (fetches from engine MongoDB)
- `GET /positions` - Get active positions (proxies to user API)
- `GET /stats` - Get trading statistics (proxies to user API)
- `GET /dashboard` - Trading dashboard summary
- `GET /conditions/{signal_id}` - Check signal execution conditions
- `POST /execute/{signal_id}` - Execute signal immediately
- `POST /execute-when-ready/{signal_id}` - Mark signal for conditional execution

#### Market API (`/api/*`)
- `GET /market-data` - Basic market data (mock implementation)
- `GET /market/data/{symbol}` - Market data by symbol (mock)

#### Control API (`/api/control/*`)
- `GET /status` - System status
- `GET /mode/info` - Current trading mode
- `GET /mode/auto-switch` - Auto-switch status
- `POST /mode/switch` - Switch trading mode
- `POST /mode/clear-override` - Clear mode override
- `GET /balance` - Get account balance
- `POST /balance/set` - Set account balance

### RTK Query API Layer
Located in: `dashboard/modular_ui/src/api/dashboardApi.ts`

Current endpoints (mostly mock/unimplemented):
- `getHealth` - System health check
- `getSystemHealth` - Extended health metrics
- `getLatestSignal` - Latest trading signal
- `getMarketData` - Market data by symbol
- `getRecentTrades` - Recent trade history
- `getAgentStatus` - Agent status information
- `getPortfolio` - Portfolio summary
- `getTechnicalIndicators` - Technical indicators

---

## Data Flow Architecture

### Initial Data Loading
1. Components use RTK Query hooks for initial data fetch
2. Data stored in Redux slices via async thunks
3. UI renders with initial state

### Real-time Updates
1. WebSocket connects to `redis_ws_gateway` (port 8889)
2. Messages processed by `useWebSocket` hook
3. Updates dispatched to Redux slices
4. Components re-render with new data

### WebSocket Channels
- `market:tick:*` - Real-time price updates
- `engine:signal:*` - Trading signal updates
- `engine:decision:*` - Agent decision updates
- `indicators:*` - Technical indicator updates
- `market:ohlc:*` - OHLC candle updates
- `market:options:*` - Options chain updates

### Data Contracts (ui_shell)
Located in: `dashboard/ui/ui_shell/contracts.py`

Key data structures:
- **DecisionDisplay** - Trading decisions for UI display
- **PortfolioSummary** - Portfolio data structure
- **MarketOverview** - Market status and key indicators
- **UserAction** classes - User override actions

---

## Current Implementation Gaps

### Mock Data Dependencies
- Most API endpoints return mock/static data
- EngineDataProvider uses MockEngineInterface
- Market data is synthetic, not real
- Portfolio data is hardcoded

### Missing Real-time Features
- WebSocket connection may fail if redis_ws_gateway not running
- Real-time data flow not fully tested
- Error handling for connection drops incomplete

### UI-Engine Integration
- ui_shell contracts defined but not fully connected to real engine
- Data providers are mock implementations
- Real engine integration pending

### Component Dependencies
- Many widgets expect data not yet available from APIs
- Error states not fully implemented
- Loading states may not handle all async scenarios

---

## Component-to-API Mapping

### Widget Data Requirements

| Widget | Primary API Endpoints | Real-time Channels | Mock Status |
|--------|----------------------|-------------------|-------------|
| MarketOverviewWidget | `/api/market-data` | `market:tick:*` | High |
| PortfolioWidget | `/api/trading/positions` | `engine:portfolio` | High |
| DecisionWidget | `/api/engine/decision/latest` | `engine:decision:*` | High |
| SignalsWidget | `/api/trading/signals` | `engine:signal:*` | Medium |
| AgentStatusWidget | `/api/engine/agents/status` | `engine:status` | High |
| TechnicalIndicatorsWidget | `/api/technical-indicators` | `indicators:*` | High |
| OptionsChainWidget | `/api/market-data/options/chain/*` | `market:options:*` | High |
| RecentTradesWidget | `/api/trading/stats` | `engine:trade:*` | Medium |

### Page Data Requirements

| Page | Key Widgets | Critical APIs | Real-time Needs |
|------|-------------|---------------|-----------------|
| DashboardPage | MarketOverview, Portfolio, Decision | Multiple | High |
| TradingPage | Signals, Portfolio, AgentStatus | Trading APIs | High |
| MarketDataPage | TechnicalIndicators, OptionsChain | Market APIs | High |
| PortfolioPage | Portfolio, RecentTrades, Performance | Trading APIs | Medium |
| AgentMonitorPage | AgentStatus, Decision, Signals | Engine APIs | High |

---

## Recommendations for Layer 9 Implementation

### Immediate Priorities (Task 9.2-9.7)
1. **Real-time Integration Plan** - Map WebSocket channels to UI updates
2. **Data Provider Migration** - Replace mocks with real engine connections
3. **Error Handling Enhancement** - Robust error states and fallbacks
4. **Performance Optimization** - Debouncing, memoization, lazy loading
5. **Testing Infrastructure** - Unit tests for components and integration tests
6. **Safety Controls** - User confirmation for trades, emergency stops

### Component Modernization Opportunities
1. **Responsive Design** - Mobile/tablet optimization
2. **Accessibility** - ARIA labels, keyboard navigation
3. **Dark Mode** - Complete theme system implementation
4. **Widget Customization** - Drag-drop layout, user preferences
5. **Advanced Charts** - Interactive charts with drawing tools
6. **Notification System** - Toast notifications, alert management

### Architecture Improvements
1. **State Management** - Consider Zustand or Jotai for simpler state
2. **Component Library** - Shared design system components
3. **API Layer** - GraphQL for more flexible data fetching
4. **Caching Strategy** - React Query for intelligent caching
5. **Bundle Optimization** - Code splitting, tree shaking

---

*This registry was generated as part of Layer 9 Task 9.1: UI Audit - Component Inventory and Gap Analysis*</content>
<parameter name="filePath">c:\code\zerodha\UI_COMPONENT_REGISTRY.md