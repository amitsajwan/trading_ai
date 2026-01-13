# UI Documentation & Testing Guide

**Last Updated:** 2026-01-10  
**Purpose:** Comprehensive documentation of all UI components, features, and testing procedures

---

## Table of Contents

1. [UI Architecture Overview](#ui-architecture-overview)
2. [Implemented Components](#implemented-components)
3. [Dashboard Pages](#dashboard-pages)
4. [API Endpoints](#api-endpoints)
5. [Widget Catalog](#widget-catalog)
6. [Layer 8 UI Features](#layer-8-ui-features)
7. [Testing Checklist](#testing-checklist)
8. [Playwright Test Plan](#playwright-test-plan)

---

## UI Architecture Overview

### Technology Stack
- **Frontend Framework:** React 18 + TypeScript
- **Build Tool:** Vite
- **State Management:** Redux Toolkit + RTK Query
- **Styling:** Tailwind CSS
- **Routing:** React Router (if used)
- **API Client:** RTK Query with axios base query

### Project Structure
```
dashboard/modular_ui/src/
├── api/                    # API client and types
│   ├── dashboardApi.ts     # RTK Query endpoints
│   ├── types.ts            # TypeScript type definitions
│   └── axiosBaseQuery.ts   # Axios base query
├── components/
│   └── widgets/            # Dashboard widgets
├── pages/                  # Page components
│   └── DashboardPage.tsx   # Main dashboard page
├── store/                  # Redux store
│   └── slices/             # Redux slices
└── App.tsx                 # Root component
```

---

## Dashboard Pages

### 1. Main Dashboard (`/`)
**File:** `dashboard/modular_ui/src/pages/DashboardPage.tsx`

**Description:** Main trading dashboard with all widgets

**Widgets Displayed:**
1. Market Overview Widget (xl:col-span-2)
2. Current Signal Widget (xl:col-span-1)
3. Options Strategy Widget (xl:col-span-2)
4. Portfolio Widget (xl:col-span-1)
5. Recent Trades Widget (xl:col-span-2)
6. Technical Indicators Widget (xl:col-span-3)
7. Agent Status Widget (xl:col-span-3)
8. **Portfolio Heat Widget (xl:col-span-2)** ⭐ Layer 8
9. **Risk Management Widget (xl:col-span-1)** ⭐ Layer 8
10. **Kelly Sizing Widget (xl:col-span-2)** ⭐ Layer 8
11. **Approval History Widget (xl:col-span-1)** ⭐ Layer 8

**Key Features:**
- Auto-refresh capability
- Real-time data updates
- Widget-based layout
- Responsive grid (lg:grid-cols-2 xl:grid-cols-3)

---

## Widget Catalog

### Core Trading Widgets

#### 1. Market Overview Widget
**File:** `dashboard/modular_ui/src/components/widgets/MarketOverviewWidget.tsx`
**API:** `useGetMarketDataQuery`
**Features:**
- Current price display
- 24h change percentage
- Volume and VWAP
- High/Low prices
- Market status indicator

**Test Points:**
- ✅ Displays current market data
- ✅ Shows price change (green/red)
- ✅ Updates on data refresh
- ✅ Handles loading state
- ✅ Handles error state

#### 2. Current Signal Widget
**File:** `dashboard/modular_ui/src/components/widgets/CurrentSignalWidget.tsx`
**API:** `useGetLatestSignalQuery`
**Features:**
- Latest trading signal
- Signal confidence
- Entry/exit prices
- Stop loss/take profit
- Reasoning display

**Test Points:**
- ✅ Displays latest signal
- ✅ Shows BUY/SELL/HOLD action
- ✅ Displays confidence score
- ✅ Shows technical reasoning
- ✅ Updates when new signal arrives

#### 3. Portfolio Widget
**File:** `dashboard/modular_ui/src/components/widgets/PortfolioWidget.tsx`
**API:** `useGetPortfolioQuery`, `useCalculateKellyMutation`
**Features:**
- Active positions list
- P&L per position
- Total portfolio value
- Kelly position sizing calculator ⭐ Layer 8

**Test Points:**
- ✅ Lists all active positions
- ✅ Shows P&L (green/red)
- ✅ Calculates Kelly sizing
- ✅ Displays position recommendations
- ✅ Shows risk/reward metrics

#### 4. Options Strategy Widget
**File:** `dashboard/modular_ui/src/components/widgets/OptionsStrategyWidget.tsx`
**Features:**
- Options strategy display
- Spread metrics
- Greeks display
- Strategy recommendations

#### 5. Recent Trades Widget
**File:** `dashboard/modular_ui/src/components/widgets/RecentTradesWidget.tsx`
**API:** `useGetRecentTradesQuery`
**Features:**
- Recent trade history
- Trade P&L
- Execution time
- Trade status

#### 6. Technical Indicators Widget
**File:** `dashboard/modular_ui/src/components/widgets/TechnicalIndicatorsWidget.tsx`
**API:** `useGetTechnicalIndicatorsQuery`
**Features:**
- RSI, MACD, ADX, SMA, EMA
- Bollinger Bands
- Volume indicators
- Multi-timeframe support

#### 7. Agent Status Widget
**File:** `dashboard/modular_ui/src/components/widgets/AgentStatusWidget.tsx`
**API:** `useGetAgentStatusQuery`
**Features:**
- Status of all 15 AI agents
- Agent signals and confidence
- Last update time
- Agent reasoning

---

### Layer 8 Risk Management Widgets ⭐

#### 8. Portfolio Heat Widget
**File:** `dashboard/modular_ui/src/components/widgets/PortfolioHeatWidget.tsx`
**API:** `useGetPortfolioHeatSummaryQuery`, `useGetHeatUtilizationQuery`
**Status:** ✅ **IMPLEMENTED**

**Features:**
- Portfolio heat utilization visualization
- Heat progress bar (color-coded: green/yellow/red)
- Total portfolio heat percentage
- Available heat calculation
- Daily P&L display
- Weekly P&L tracking
- Maximum loss amount
- Active positions count
- Account balance
- Risk status indicators (HIGH/MEDIUM/LOW)
- Trading restriction warnings

**Visual Elements:**
- Thermometer icon
- Progress bar with percentage
- Color-coded risk levels:
  - Green: < 50% heat (safe)
  - Yellow: 50-80% heat (moderate)
  - Red: > 80% heat (high)
- Status badges (can trade / trading restricted)

**Test Points:**
- ✅ Fetches portfolio heat summary
- ✅ Displays heat utilization bar
- ✅ Shows color-coded risk levels
- ✅ Displays daily/weekly P&L
- ✅ Shows active positions count
- ✅ Calculates available heat
- ✅ Displays risk warnings when heat is high
- ✅ Shows "Trading Restricted" when limits exceeded
- ✅ Handles loading state
- ✅ Handles error state (no data)

**API Endpoints Used:**
- `GET /api/risk/portfolio/summary`
- `GET /api/risk/portfolio/heat-utilization`

---

#### 9. Risk Management Widget
**File:** `dashboard/modular_ui/src/components/widgets/RiskManagementWidget.tsx`
**API:** `useGetPortfolioHeatSummaryQuery`, `useGetHeatUtilizationQuery`, `useGetApprovalStatsQuery`
**Status:** ✅ **ENHANCED** (Layer 8 integration added)

**Features:**
- Portfolio heat utilization display (integrated from Layer 8)
- Heat progress bar
- Approval statistics (integrated from Layer 8)
- Daily/weekly loss tracking
- Risk settings configuration
- Max position size
- Max daily loss
- Stop loss percentage
- Take profit percentage
- Auto stop loss toggle
- Auto take profit toggle

**Test Points:**
- ✅ Displays portfolio heat (Layer 8 integration)
- ✅ Shows approval statistics (Layer 8 integration)
- ✅ Displays risk settings form
- ✅ Saves risk settings to localStorage
- ✅ Shows saved confirmation
- ✅ Handles form validation
- ✅ Updates risk metrics in real-time

**API Endpoints Used:**
- `GET /api/risk/portfolio/summary`
- `GET /api/risk/portfolio/heat-utilization`
- `GET /api/risk/approval/stats`

---

#### 10. Kelly Sizing Widget
**File:** `dashboard/modular_ui/src/components/widgets/KellySizingWidget.tsx`
**API:** `useCalculateKellyMutation`
**Status:** ✅ **IMPLEMENTED** (Layer 8)

**Features:**
- Kelly position sizing calculator
- Manual mode (win probability, R:R inputs)
- Historical stats mode
- Kelly percentage display
- Recommended position size
- Risk amount calculation
- Historical statistics display:
  - Win rate
  - Average win
  - Average loss
  - Risk/Reward ratio
- Visual feedback (safe/risky indicators)
- Color-coded warnings:
  - Green: Safe position size (< 25% Kelly)
  - Yellow: Moderate risk (25-50% Kelly)
  - Red: Too risky (> 50% Kelly)
- Warning messages for high Kelly percentages

**Test Points:**
- ✅ Manual mode inputs (win prob, R:R sliders)
- ✅ Historical stats mode toggle
- ✅ Calculate Kelly button
- ✅ Displays Kelly percentage
- ✅ Shows recommended position size
- ✅ Calculates risk amount
- ✅ Displays historical statistics
- ✅ Shows color-coded risk indicators
- ✅ Displays warnings for high Kelly
- ✅ Handles loading state
- ✅ Handles error state

**API Endpoints Used:**
- `POST /api/risk/kelly/calculate`

---

#### 11. Approval History Widget
**File:** `dashboard/modular_ui/src/components/widgets/ApprovalHistoryWidget.tsx`
**API:** `useGetApprovalHistoryQuery`, `useGetApprovalStatsQuery`
**Status:** ✅ **IMPLEMENTED** (Layer 8)

**Features:**
- Recent approval decisions display
- Approval statistics summary
- Decision details:
  - Decision type (APPROVED/REJECTED/REDUCED)
  - Reason for decision
  - Approved quantity
  - Kelly percentage
  - Risk amount
  - Timestamp
- Visual indicators:
  - CheckCircle icon (approved - green)
  - XCircle icon (rejected - red)
  - AlertCircle icon (reduced - yellow)
- Approval statistics:
  - Total reviews count
  - Approval rate percentage
  - Rejection rate percentage
  - Reduction rate percentage

**Test Points:**
- ✅ Fetches approval history
- ✅ Displays recent decisions
- ✅ Shows decision icons (approved/rejected/reduced)
- ✅ Displays decision details (quantity, Kelly %, risk)
- ✅ Shows approval statistics
- ✅ Handles empty history
- ✅ Handles loading state
- ✅ Handles error state
- ✅ Formats timestamps correctly

**API Endpoints Used:**
- `GET /api/risk/approval/history?limit=10`
- `GET /api/risk/approval/stats`

---

## API Endpoints

### Risk Management API (Layer 8)

All endpoints are prefixed with `/api/risk`

#### 1. Portfolio Heat Summary
- **Endpoint:** `GET /api/risk/portfolio/summary`
- **Response:** `PortfolioHeatSummary`
- **Used By:** PortfolioHeatWidget, RiskManagementWidget

#### 2. Heat Utilization
- **Endpoint:** `GET /api/risk/portfolio/heat-utilization`
- **Response:** `HeatUtilization`
- **Used By:** PortfolioHeatWidget, RiskManagementWidget

#### 3. Can Open Position
- **Endpoint:** `POST /api/risk/portfolio/can-open-position`
- **Parameters:** `proposed_max_loss: float`
- **Response:** `{can_open: bool, reason: str}`

#### 4. Optimal Quantity
- **Endpoint:** `POST /api/risk/portfolio/optimal-quantity`
- **Parameters:** `max_loss_per_unit: float`
- **Response:** `{optimal_quantity: int}`

#### 5. Calculate Kelly
- **Endpoint:** `POST /api/risk/kelly/calculate`
- **Body:** 
  ```typescript
  {
    account_balance: number
    max_loss_per_unit: number
    win_probability?: number
    risk_reward_ratio?: number
    trade_history?: Array<Record<string, any>>
    strategy_type?: string
  }
  ```
- **Response:** `KellyCalculation`
- **Used By:** KellySizingWidget

#### 6. Historical Stats
- **Endpoint:** `POST /api/risk/kelly/historical-stats`
- **Body:** `trade_history: Array<Record<string, any>>`
- **Response:** Historical statistics

#### 7. Review and Approve
- **Endpoint:** `POST /api/risk/approval/review`
- **Body:**
  ```typescript
  {
    trading_decision: Record<string, any>
    proposed_quantity: number
    proposed_max_loss: float
    current_positions?: Array<Record<string, any>>
  }
  ```
- **Response:** `ApprovalResult`
- **Used By:** (Future integration)

#### 8. Approval History
- **Endpoint:** `GET /api/risk/approval/history?limit=10`
- **Response:** `ApprovalHistory`
- **Used By:** ApprovalHistoryWidget

#### 9. Approval Statistics
- **Endpoint:** `GET /api/risk/approval/stats`
- **Response:** `ApprovalStats`
- **Used By:** ApprovalHistoryWidget, RiskManagementWidget

---

## Layer 8 UI Features Summary

### ✅ Completed Features

| Feature | Widget | API Endpoint | Status |
|---------|--------|--------------|--------|
| Portfolio Heat Visualization | PortfolioHeatWidget | `/api/risk/portfolio/summary` | ✅ Complete |
| Heat Utilization Breakdown | PortfolioHeatWidget | `/api/risk/portfolio/heat-utilization` | ✅ Complete |
| Kelly Position Sizing | KellySizingWidget | `/api/risk/kelly/calculate` | ✅ Complete |
| Approval History | ApprovalHistoryWidget | `/api/risk/approval/history` | ✅ Complete |
| Approval Statistics | ApprovalHistoryWidget, RiskManagementWidget | `/api/risk/approval/stats` | ✅ Complete |
| Risk Settings | RiskManagementWidget | (localStorage) | ✅ Complete |
| Enhanced Portfolio Widget | PortfolioWidget | `useCalculateKellyMutation` | ✅ Complete |

### ⏳ Pending Features (Future Tasks)

| Feature | Task | Status |
|---------|------|--------|
| Real-time WebSocket Updates | Task 9.9 | ⏳ Pending |
| Trade Approval UI | Task 9.13 | ⏳ Pending |
| Live Trade Safety Controls | Task 9.8 | ⏳ Research |

---

## Testing Checklist

### Manual Testing Checklist

#### Core Trading Widgets
- [ ] Market Overview Widget displays current price
- [ ] Current Signal Widget shows latest signal
- [ ] Portfolio Widget lists positions
- [ ] Options Strategy Widget displays strategies
- [ ] Recent Trades Widget shows trade history
- [ ] Technical Indicators Widget displays indicators
- [ ] Agent Status Widget shows all agents

#### Layer 8 Risk Widgets
- [ ] **Portfolio Heat Widget:**
  - [ ] Displays heat utilization bar
  - [ ] Shows color-coded risk levels (green/yellow/red)
  - [ ] Displays daily/weekly P&L
  - [ ] Shows active positions count
  - [ ] Displays risk warnings when heat is high
  - [ ] Shows "Trading Restricted" when limits exceeded

- [ ] **Risk Management Widget:**
  - [ ] Displays portfolio heat (Layer 8 integration)
  - [ ] Shows approval statistics
  - [ ] Saves risk settings
  - [ ] Updates risk metrics

- [ ] **Kelly Sizing Widget:**
  - [ ] Manual mode inputs work
  - [ ] Historical stats mode toggle works
  - [ ] Calculate button triggers calculation
  - [ ] Displays Kelly percentage
  - [ ] Shows recommended position size
  - [ ] Displays warnings for high Kelly

- [ ] **Approval History Widget:**
  - [ ] Displays approval history
  - [ ] Shows decision icons correctly
  - [ ] Displays approval statistics
  - [ ] Handles empty history gracefully

#### API Integration
- [ ] All API endpoints return data
- [ ] Error handling works correctly
- [ ] Loading states display properly
- [ ] Data updates in real-time (when applicable)

---

## Playwright Test Plan

See `dashboard/tests/playwright/` for automated test suite.

### Test Structure

```
dashboard/tests/playwright/
├── tests/
│   ├── dashboard.spec.ts          # Dashboard page tests
│   ├── widgets/
│   │   ├── portfolio-heat.spec.ts      # Portfolio Heat Widget
│   │   ├── kelly-sizing.spec.ts        # Kelly Sizing Widget
│   │   ├── approval-history.spec.ts    # Approval History Widget
│   │   ├── risk-management.spec.ts     # Risk Management Widget
│   │   └── portfolio.spec.ts           # Portfolio Widget
│   └── api/
│       └── risk-api.spec.ts            # Risk API endpoints
└── playwright.config.ts           # Playwright configuration
```

### Test Execution

```bash
# Install Playwright
npm install -D @playwright/test
npx playwright install

# Run all tests
npx playwright test

# Run specific test file
npx playwright test tests/widgets/portfolio-heat.spec.ts

# Run in headed mode (see browser)
npx playwright test --headed

# Run with UI mode (interactive)
npx playwright test --ui
```

---

## Next Steps

1. **Create Playwright Test Suite** (this document + tests)
2. **Run Manual Testing** using this checklist
3. **Fix any issues** found during testing
4. **Document edge cases** and error handling
5. **Add E2E test coverage** for critical user flows

---

**Ready for Testing!** 🧪

Use this documentation to systematically test all UI components and verify Layer 8 integration is working correctly.
