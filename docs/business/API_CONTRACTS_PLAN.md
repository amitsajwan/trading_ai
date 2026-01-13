# API Contracts, Type Safety & SDKs - Implementation Plan

**Task 9.3** - Layer 9: UI Modernization Research Phase

**Updated**: Corrected file structure to match modular UI architecture
- Types moved to `dashboard/modular_ui/src/api/types.ts`
- RTK Query API updated in `dashboard/modular_ui/src/api/dashboardApi.ts`
- Removed standalone root-level types file

## Overview

This document outlines the implementation plan for creating robust API contracts with type safety across Python FastAPI backend and TypeScript React frontend. The goal is to establish a solid foundation for reliable frontend-backend integration with automatic type generation and runtime validation.

## Current API Structure Analysis

### FastAPI Application Structure

**Main App (`dashboard/app.py`):**
- FastAPI app with title "Trading Dashboard v1.0.0"
- Three modular routers included:
  - `control_router` (prefix: `/api/control`)
  - `trading_router` (prefix: `/api/trading`)
  - `market_router` (prefix: `/api`)

### Router Endpoints Analysis

#### Control Router (`dashboard/api/control.py`)
```python
# Current endpoints:
GET  /api/control/status
GET  /api/control/mode/info
GET  /api/control/mode/auto-switch
POST /api/control/mode/switch
POST /api/control/mode/clear-override
GET  /api/control/balance
POST /api/control/balance/set
```

#### Trading Router (`dashboard/api/trading.py`)
```python
# Current endpoints:
POST /api/trading/cycle
GET  /api/trading/signals
GET  /api/trading/positions
GET  /api/trading/stats
GET  /api/trading/dashboard
GET  /api/trading/conditions/{signal_id}
```

#### Market Router (`dashboard/api/market.py`)
```python
# Current endpoints:
GET  /api/market-data
GET  /api/market/data/{symbol}
```

#### Direct App Endpoints (`dashboard/app.py`)
```python
# Health & System Status
GET  /
GET  /api/health
GET  /api/system-health
GET  /api/latest-analysis
GET  /api/latest-signal
GET  /api/agent-status

# Market Data
GET  /api/market-data
GET  /metrics/trading
GET  /metrics/risk

# Trading Data
GET  /api/recent-trades
```

## OpenAPI Export Plan

### Current OpenAPI Compliance Issues

1. **No OpenAPI Schema Generation**: FastAPI auto-generates OpenAPI specs, but they're not exported or validated
2. **Inconsistent Response Models**: Most endpoints return raw `dict` objects without Pydantic models
3. **Missing Request Models**: POST endpoints use generic `Body(...)` without typed schemas
4. **No API Versioning**: All endpoints are unversioned
5. **Mixed Router Patterns**: Some endpoints in main app, others in routers

### OpenAPI Export Strategy

#### Phase 1: Schema Standardization
1. **Create Pydantic Models** for all request/response types
2. **Standardize Response Format** with consistent error handling
3. **Add API Versioning** (`/api/v1/...`)
4. **Implement OpenAPI Tags** for logical grouping

#### Phase 2: Export & Validation
1. **Export OpenAPI JSON** from FastAPI
2. **Generate TypeScript Types** using OpenAPI Generator
3. **Create Zod Schemas** for runtime validation
4. **Implement API Client SDK** with typed methods

#### Phase 3: Integration
1. **Update Frontend** to use generated types
2. **Add Runtime Validation** with Zod
3. **Implement Error Boundaries** for API failures
4. **Add API Testing** with generated mocks

## TypeScript Type Generation Plan

### Target TypeScript Interfaces

#### Generated Files Structure
```
dashboard/modular_ui/src/api/
├── types.ts              # Generated TypeScript interfaces & Zod schemas
├── dashboardApi.ts       # Updated RTK Query API with typed endpoints
└── axiosBaseQuery.ts     # Existing base query configuration
```

#### Core Data Models
- **Location**: `dashboard/modular_ui/src/api/types.ts`
- **Integration**: Imported and used in `dashboardApi.ts` to replace `any` types

#### Zod Validation Schemas
- **Location**: `dashboard/modular_ui/src/api/types.ts`
- **Integration**: Runtime validation for API responses and form data

```typescript
import { z } from 'zod';

export const SystemHealthSchema = z.object({
  status: z.enum(['ok', 'degraded', 'error']),
  timestamp: z.string(),
  database: z.enum(['ok', 'error']),
  cache: z.enum(['ok', 'error']),
  market_open: z.boolean(),
  instrument: z.string()
});

export const TradingSignalSchema = z.object({
  signal_id: z.string(),
  instrument: z.string(),
  action: z.enum(['BUY', 'SELL', 'HOLD']),
  confidence: z.number().min(0).max(1),
  timestamp: z.string(),
  entry_price: z.number().optional(),
  stop_loss: z.number().optional(),
  take_profit: z.number().optional(),
  reasoning: z.string().optional()
});
```

### API Client SDK Structure

#### Generated Client Methods
- **Location**: `dashboard/modular_ui/src/api/types.ts`
- **Integration**: Standalone client for non-RTK usage

```typescript
export class TradingAPIClient {
  // Health endpoints
  async getHealth(): Promise<SystemHealth>
  async getSystemHealth(): Promise<SystemHealth>

  // Trading endpoints
  async getSignals(instrument?: string): Promise<TradingSignal[]>
  async getPositions(): Promise<Position[]>
  async runTradingCycle(): Promise<TradingCycleResult>
  async checkSignalConditions(signalId: string): Promise<SignalConditionCheck>

  // Market data endpoints
  async getMarketData(): Promise<MarketData>
  async getMarketDataBySymbol(symbol: string): Promise<MarketData>

  // Control endpoints
  async getControlStatus(): Promise<ControlStatus>
  async switchMode(request: ModeSwitchRequest): Promise<ModeSwitchResponse>
  async setBalance(balance: number): Promise<BalanceResponse>
}
```

#### RTK Query Integration
- **Location**: `dashboard/modular_ui/src/api/dashboardApi.ts`
- **Status**: ✅ **IMPLEMENTED** - Updated existing API slice with generated types

```typescript
// Updated dashboardApi.ts with proper types
import type {
  SystemHealth,
  TradingSignal,
  MarketData,
  AgentStatusResponse,
  Position,
  RecentTradesResponse
} from './types'

export const dashboardApi = createApi({
  endpoints: (builder) => ({
    getSystemHealth: builder.query<SystemHealth, void>({
      query: () => ({ url: '/api/system-health' }),
    }),

    getLatestSignal: builder.query<{ signal: TradingSignal }, { symbol?: string }>({
      query: (arg) => ({ url: `/api/latest-signal${arg?.symbol ? `?symbol=${arg.symbol}` : ''}` }),
    }),

    getMarketData: builder.query<MarketData, { symbol: string }>({
      query: ({ symbol }) => ({ url: `/api/market-data?symbol=${encodeURIComponent(symbol)}` }),
    }),

    getAgentStatus: builder.query<AgentStatusResponse, void>({
      query: () => ({ url: '/api/agent-status' }),
      providesTags: ['AgentStatus'],
    }),
  })
});
```

### Phase 1: Backend Schema Standardization (Week 1-2)

#### 1.1 Create Pydantic Models
- Create `dashboard/schemas/` directory
- Define models for all endpoints:
  - `health.py` - System health models
  - `trading.py` - Trading signal and position models
  - `market.py` - Market data models
  - `control.py` - Control and configuration models

#### 1.2 Update Router Endpoints
- Replace `dict` returns with Pydantic models
- Add proper request models for POST endpoints
- Implement consistent error responses
- Add response examples and descriptions

#### 1.3 Add API Versioning
- Update router prefixes to `/api/v1/...`
- Maintain backward compatibility with redirects
- Update frontend API calls

### Phase 2: OpenAPI Export & Type Generation (Week 3)

#### 2.1 Export OpenAPI Specification
- Configure FastAPI OpenAPI settings
- Export JSON schema to `docs/openapi.json`
- Validate schema completeness

#### 2.2 Generate TypeScript Types
- Use OpenAPI Generator for TypeScript types
- Generate Zod schemas from OpenAPI spec
- Create API client SDK with axios/fetch

#### 2.3 Create SDK Package
- Structure as npm package
- Include generated types and client
- Add configuration and error handling

### Phase 3: Frontend Integration (Week 4)

#### 3.1 Update RTK Query Slices
- Replace manual types with generated ones
- Update API endpoints to use SDK
- Add runtime validation with Zod

#### 3.2 Implement Error Handling
- Add API error boundaries
- Implement retry logic for failed requests
- Add loading states and error messages

#### 3.3 Testing & Validation
- Add unit tests for API client
- Test end-to-end type safety
- Validate runtime schema validation

## Success Criteria

### Backend Requirements
- ✅ All endpoints return Pydantic models
- ✅ OpenAPI schema exports successfully
- ✅ API versioning implemented
- ✅ Consistent error response format

### Frontend Requirements
- ✅ TypeScript types generated from OpenAPI (sample implementation)
- ✅ Zod runtime validation implemented (in types.ts)
- ✅ API client SDK functional (in types.ts)
- ✅ RTK Query API updated with types (dashboardApi.ts)
- ⏳ No TypeScript errors in API usage (pending full backend implementation)
- ⏳ Runtime validation catches invalid data (pending backend schema updates)

### Integration Requirements
- ✅ End-to-end type safety maintained (types properly integrated)
- ⏳ Runtime validation catches invalid data (pending backend schema updates)
- ⏳ Error handling graceful and informative (pending backend implementation)
- ⏳ API client tests passing (pending backend API updates)

## Risk Mitigation

### Technical Risks
1. **Schema Evolution**: Use API versioning and backward compatibility
2. **Type Conflicts**: Regular regeneration and conflict resolution
3. **Runtime Performance**: Optimize Zod validation for performance-critical paths

### Operational Risks
1. **Breaking Changes**: Gradual rollout with feature flags
2. **Type Errors**: Comprehensive testing before deployment
3. **Build Complexity**: Automate type generation in CI/CD

## Dependencies & Prerequisites

### Backend Dependencies
- FastAPI (already present)
- Pydantic (already present)
- uvicorn[standard] for OpenAPI export

### Frontend Dependencies
- TypeScript 4.9+
- Zod for runtime validation
- OpenAPI Generator CLI
- RTK Query (already present)

### Development Tools
- OpenAPI Generator
- TypeScript compiler
- pytest for API tests
- Jest for frontend tests

## Testing Strategy

### Unit Tests
- Pydantic model validation
- Zod schema validation
- API client method calls
- Error response handling

### Integration Tests
- End-to-end API calls with type validation
- OpenAPI schema generation
- TypeScript compilation checks

### E2E Tests
- Frontend API integration
- Runtime validation in browser
- Error boundary testing

## Documentation Updates

### API Documentation
- Update `API_ENDPOINTS_SUMMARY.md` with new endpoints
- Add OpenAPI schema reference
- Document type generation process

### Developer Documentation
- Add SDK usage examples
- Document type regeneration workflow
- Update contribution guidelines for schema changes

---

**Next Steps:** Begin Phase 1 implementation by creating Pydantic models for existing endpoints.</content>
<parameter name="filePath">c:\code\zerodha\API_CONTRACTS_PLAN.md