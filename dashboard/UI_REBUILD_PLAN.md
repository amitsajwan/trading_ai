# UI Rebuild Plan - Step-by-Step Component-by-Component Approach

## Executive Summary

This document outlines a comprehensive plan to rebuild the UI with proper separation of concerns, loose coupling, and seamless data flow. The approach is incremental - one component at a time, verified and tested before moving to the next.

## Core Problems Identified

1. **Flickering UI**: When WebSocket disconnects, components switch to polling, causing visible UI flicker
2. **Tight Coupling**: Components directly manage WebSocket subscriptions, polling intervals, and fallback logic
3. **Mixed Concerns**: Data fetching, real-time updates, UI rendering, and state management are all intertwined
4. **No Data Abstraction**: Components directly call thunks, use WebSocket hooks, and manage their own polling
5. **Hard to Test**: Complex interdependencies make testing difficult

## Architecture Vision

### New Architecture: Data Layer + Presentation Layer

```
┌─────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                    │
│  (Pure React Components - No data fetching logic)       │
│  - MarketDataWidget, PortfolioWidget, etc.              │
│  - Only receives props, renders UI                      │
└─────────────────────────────────────────────────────────┘
                        ▲
                        │ Uses hooks (useMarketTick, usePortfolio, etc.)
                        │
┌─────────────────────────────────────────────────────────┐
│                    DATA LAYER                            │
│  (Custom Hooks - Abstract data source complexity)       │
│  - useMarketTick(instrument)                            │
│  - usePortfolio()                                       │
│  - useOptionsChain(instrument)                          │
│  - Seamlessly handles HTTP + WS + caching              │
│  - No flickering, smooth transitions                    │
└─────────────────────────────────────────────────────────┘
                        ▲
                        │ Uses
                        │
┌─────────────────────────────────────────────────────────┐
│                  DATA SERVICES                           │
│  - DataService (abstract interface)                     │
│  - HTTPDataService (fallback)                           │
│  - WebSocketDataService (real-time)                     │
│  - HybridDataService (HTTP + WS, seamless switching)    │
│  - DataCache (in-memory cache with TTL)                 │
└─────────────────────────────────────────────────────────┘
```

### Key Principles

1. **Separation of Concerns**: Data layer handles all data complexity, UI just renders
2. **Loose Coupling**: Data layer is backend-agnostic (HTTP, WS, or both)
3. **No Flickering**: Data layer maintains cached data during transitions
4. **Single Source of Truth**: One hook per data entity, components use that hook
5. **Testability**: Data layer can be tested independently, UI components are pure

## Component Grouping & Domains

### Group 1: Market Data (Real-time, high frequency)
- **LiveTickDataWidget** - Current price, volume, OI
- **MarketOverviewWidget** - Summary stats, 24h changes
- **TechnicalIndicatorsWidget** - RSI, MACD, ADX, etc.
- **OHLCWidget** (if exists) - Candlestick data

**Characteristics**: High frequency updates, real-time critical

### Group 2: Options Data (Real-time, moderate frequency)
- **OptionsChainWidget** - Strike prices, OI, IV
- **OptionsStrategyWidget** - Strategy analysis

**Characteristics**: Moderate frequency, large payloads

### Group 3: Trading & Portfolio (User actions + real-time)
- **PortfolioWidget** - Current positions, P&L
- **RecentTradesWidget** - Trade history
- **TradeExecutionWidget** - Execute trades (user action)
- **ActivePositionsWidget** - Open positions

**Characteristics**: User actions + real-time updates

### Group 4: Signals & Decisions (Event-driven)
- **CurrentSignalWidget** - Latest signal
- **ActiveSignalsWidget** - All active signals
- **AgentStatusWidget** - Agent decisions

**Characteristics**: Event-driven, lower frequency

### Group 5: Analytics & Risk (Computed, lower frequency)
- **ApprovalHistoryWidget** - Historical approvals
- **KellySizingWidget** - Risk calculations
- **PortfolioHeatWidget** - Heat map
- **RiskManagementWidget** - Risk metrics

**Characteristics**: Computed data, lower update frequency

## Implementation Plan

### Phase 0: Foundation - Data Layer Infrastructure (1-2 days)

**Goal**: Build the data layer abstraction that components will use

**Steps**:
1. Create `src/services/data/` directory structure
2. Implement `DataCache` - In-memory cache with TTL
3. Implement `DataService` interface
4. Implement `HTTPDataService` - Wraps HTTP calls
5. Implement `WebSocketDataService` - Wraps WebSocket
6. Implement `HybridDataService` - Seamlessly combines HTTP + WS
7. Create `useData` hook - Generic hook that uses HybridDataService

**Files to Create**:
```
src/services/data/
  ├── types.ts                 # Data service interfaces
  ├── DataCache.ts             # In-memory cache
  ├── HTTPDataService.ts       # HTTP implementation
  ├── WebSocketDataService.ts  # WS implementation
  ├── HybridDataService.ts     # Hybrid (HTTP + WS)
  └── useData.ts               # Generic hook
```

**Testing**: Unit tests for each service, verify cache behavior, verify seamless switching

---

### Phase 1: Group 1 - Market Data Components (3-4 days)

**Goal**: Rebuild market data components using new data layer

#### Step 1.1: LiveTickDataWidget (1 day)

**Current Issues**:
- Directly uses `fetchCurrentTick` thunk
- Manages own polling logic
- Uses `useWebSocket` directly
- Flickers when WS disconnects

**New Approach**:
1. Create `useMarketTick(instrument)` hook using data layer
2. Create new `LiveTickDataWidgetV2` component
3. Component only receives data from hook, no data logic
4. Hook handles HTTP + WS + caching seamlessly
5. Test: Verify no flickering, smooth transitions, real-time updates
6. Replace old component once verified

**Files**:
- `src/hooks/data/useMarketTick.ts` - New hook
- `src/components/widgets/market/LiveTickDataWidgetV2.tsx` - New component

**Verification Checklist**:
- [ ] Component renders without errors
- [ ] Initial data loads via HTTP
- [ ] Real-time updates work via WS
- [ ] WS disconnection: No flickering, continues with cached data
- [ ] WS reconnection: Smooth transition back to real-time
- [ ] Polling fallback works (but only when WS unavailable)
- [ ] No console errors
- [ ] Performance: No unnecessary re-renders

#### Step 1.2: MarketOverviewWidget (1 day)

Same approach as 1.1, create `useMarketOverview()` hook.

#### Step 1.3: TechnicalIndicatorsWidget (1 day)

Same approach, create `useTechnicalIndicators(instrument)` hook.

#### Step 1.4: Testing & Integration (1 day)

- Integration tests for Group 1 components
- Verify all work together
- Performance testing
- Document Group 1 completion

---

### Phase 2: Group 2 - Options Data Components (2-3 days)

**Goal**: Rebuild options components (handle large payloads)

#### Step 2.1: OptionsChainWidget (2 days)

**Special Considerations**:
- Large payloads (many strikes)
- Need efficient rendering (virtualization?)
- Diffs/patches might be needed

**Approach**:
1. Create `useOptionsChain(instrument)` hook
2. Implement payload optimization in data layer (if needed)
3. Create new component
4. Consider virtualization for large tables
5. Test with real data sizes

#### Step 2.2: OptionsStrategyWidget (1 day)

Similar approach.

---

### Phase 3: Group 3 - Trading & Portfolio (3-4 days)

**Goal**: Rebuild trading components (user actions + real-time)

#### Step 3.1: PortfolioWidget (1 day)

**Considerations**:
- User actions (mutations)
- Real-time updates
- Optimistic updates?

#### Step 3.2: RecentTradesWidget (1 day)

#### Step 3.3: TradeExecutionWidget (1 day)

**Considerations**:
- User actions (POST requests)
- Need mutation handling
- Error handling

#### Step 3.4: ActivePositionsWidget (1 day)

---

### Phase 4: Group 4 - Signals & Decisions (2-3 days)

**Goal**: Rebuild signal/decision components (event-driven)

#### Step 4.1: CurrentSignalWidget (1 day)

#### Step 4.2: ActiveSignalsWidget (1 day)

#### Step 4.3: AgentStatusWidget (1 day)

---

### Phase 5: Group 5 - Analytics & Risk (2-3 days)

**Goal**: Rebuild analytics components (computed data)

#### Step 5.1-5.4: Remaining widgets

Similar approach, but focus on computed/cached data.

---

### Phase 6: Cleanup & Documentation (1-2 days)

1. Remove old components
2. Update documentation
3. Final integration tests
4. Performance audit
5. Migration guide

---

## Data Layer Design Details

### DataCache Interface

```typescript
interface DataCache<T> {
  get(key: string): T | null
  set(key: string, value: T, ttl?: number): void
  invalidate(key: string): void
  clear(): void
}
```

**Purpose**: Maintains cached data during WS transitions to prevent flickering.

### HybridDataService Interface

```typescript
interface HybridDataService<T> {
  // Subscribe to data updates
  subscribe(
    key: string,
    callback: (data: T) => void,
    options?: SubscribeOptions
  ): () => void // Returns unsubscribe function
  
  // Get current cached value
  getCurrent(key: string): T | null
  
  // Get initial value (HTTP fetch)
  fetchInitial(key: string): Promise<T>
}
```

**Behavior**:
1. On subscribe: Immediately returns cached value (if exists)
2. Fetches initial data via HTTP (if not cached)
3. Subscribes to WS updates (if WS available)
4. On WS disconnect: Continues with cached data, no flicker
5. On WS reconnect: Smoothly transitions back to real-time

### useMarketTick Hook Example

```typescript
function useMarketTick(instrument: string) {
  const [data, setData] = useState<TickData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [isRealTime, setIsRealTime] = useState(false)
  
  useEffect(() => {
    const unsubscribe = hybridDataService.subscribe(
      `tick:${instrument}`,
      (tick) => {
        setData(tick)
        setLoading(false)
        setIsRealTime(true)
      },
      {
        fetchInitial: () => fetchTickHTTP(instrument),
        wsChannel: `market:tick:${instrument}`
      }
    )
    
    return unsubscribe
  }, [instrument])
  
  return { data, loading, error, isRealTime }
}
```

**Key Features**:
- Component doesn't know about HTTP vs WS
- No flickering (cache maintains data)
- `isRealTime` flag indicates WS status (optional UI indicator)
- Automatic fallback to HTTP if WS unavailable

---

## Backend Considerations

### If Backend Changes Needed

The data layer abstraction allows backend changes without component changes:

1. **Add new data source**: Implement new `DataService`
2. **Change API endpoints**: Update `HTTPDataService`
3. **Change WS protocol**: Update `WebSocketDataService`
4. **Components unchanged**: They use hooks, hooks use services

### Potential Backend Improvements

1. **WebSocket Authentication**: Add JWT/session auth
2. **WebSocket Reconnection**: Server-side session management
3. **Data Compression**: Compress large payloads (options chain)
4. **Diffs/Patches**: Send deltas instead of full payloads
5. **Rate Limiting**: Proper 429 handling

---

## Testing Strategy

### Unit Tests
- Data services (cache, HTTP, WS, hybrid)
- Custom hooks (useMarketTick, etc.)
- Pure component rendering (snapshot tests)

### Integration Tests
- Hook + Component integration
- Data flow: HTTP → WS transition
- WS disconnect/reconnect scenarios

### E2E Tests
- Full user flows
- WS failure scenarios
- Performance under load

---

## Migration Strategy

### Per-Component Migration

1. Create new component (WidgetV2)
2. Test thoroughly
3. Add feature flag or route parameter
4. Switch to new component
5. Remove old component
6. Document migration

### Rollback Plan

- Keep old components until new ones verified
- Feature flags for gradual rollout
- Monitor errors and performance

---

## Success Criteria

### Functional
- ✅ No UI flickering when WS disconnects/reconnects
- ✅ All components work with HTTP-only mode
- ✅ All components work with WS-enabled mode
- ✅ Smooth transitions between HTTP and WS
- ✅ User actions work correctly

### Technical
- ✅ Components are pure (no data fetching logic)
- ✅ Data layer is testable independently
- ✅ Loose coupling (backend can change without UI changes)
- ✅ Performance: No unnecessary re-renders
- ✅ Code organization: Clear separation of concerns

### User Experience
- ✅ Smooth, responsive UI
- ✅ Clear loading states
- ✅ Clear error states
- ✅ Optional: Real-time indicator (subtle)

---

## Timeline Estimate

- **Phase 0**: 1-2 days (Foundation)
- **Phase 1**: 3-4 days (Market Data - 3 components)
- **Phase 2**: 2-3 days (Options - 2 components)
- **Phase 3**: 3-4 days (Trading - 4 components)
- **Phase 4**: 2-3 days (Signals - 3 components)
- **Phase 5**: 2-3 days (Analytics - 4 components)
- **Phase 6**: 1-2 days (Cleanup)

**Total**: 14-21 days (2-3 weeks)

---

## Next Steps

1. Review and approve this plan
2. Start Phase 0 (Data Layer Foundation)
3. Implement Step 1.1 (LiveTickDataWidget) as proof of concept
4. Verify approach works
5. Continue step-by-step

---

## Questions & Decisions Needed

1. **Caching Strategy**: TTL per data type? How long to cache?
2. **WS Fallback**: Should we poll when WS disconnected, or just use cached data?
3. **Real-time Indicator**: Show WS status to user? Where? How subtle?
4. **Error Handling**: How to surface errors? Toast notifications? Inline errors?
5. **Loading States**: Skeleton loaders? Spinners? Per-component or global?
6. **Backend Changes**: Can we modify backend if needed, or must we work with existing API?

---

## Appendix: Component Inventory

### Current Components (18 total)

**Group 1 - Market Data** (4):
- LiveTickDataWidget ✅
- MarketOverviewWidget
- TechnicalIndicatorsWidget
- (OHLCWidget if exists)

**Group 2 - Options** (2):
- OptionsChainWidget ✅
- OptionsStrategyWidget

**Group 3 - Trading** (4):
- PortfolioWidget
- RecentTradesWidget
- TradeExecutionWidget
- ActivePositionsWidget

**Group 4 - Signals** (3):
- CurrentSignalWidget
- ActiveSignalsWidget
- AgentStatusWidget

**Group 5 - Analytics** (5):
- ApprovalHistoryWidget
- KellySizingWidget
- PortfolioHeatWidget
- RiskManagementWidget
- HistoricalDataWidget

---

**Ready to start? Let's begin with Phase 0: Data Layer Foundation!** 🚀
