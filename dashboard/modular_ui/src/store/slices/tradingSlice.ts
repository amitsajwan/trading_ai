import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import axios from 'axios'

export interface Decision {
  instrument: string
  signal: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  reasoning: string
  timestamp: string
  technical_indicators?: any
  sentiment_score?: number
  macro_factors?: any
  entry_price?: number
  stop_loss?: number
  take_profit?: number
}

export interface PortfolioPosition {
  instrument: string
  quantity: number
  entry_price: number
  current_price: number
  unrealized_pnl: number
  pnl_percentage: number
  market_value: number
}

export interface PortfolioSummary {
  total_value: number
  cash_balance: number
  positions: Record<string, PortfolioPosition>
  pnl_today: number
  total_pnl: number
  timestamp: string
}

export interface Trade {
  id: string
  timestamp: string
  instrument: string
  side: 'BUY' | 'SELL'
  quantity: number
  price: number
  pnl: number
  status: 'open' | 'closed'
  exit_price?: number
  exit_timestamp?: string
  // Optional signal id that caused this trade (if applicable)
  signal_id?: string
}

export interface AgentStatus {
  name: string
  status: 'active' | 'inactive' | 'error'
  last_update: string
  signal?: string
  confidence?: number
  summary?: any
  technical_indicators?: any
  reasoning?: string
  cycle_info?: any
}

export interface AgentResponse {
  agent: string
  decision: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  timestamp: string
  details: {
    reasoning?: string
    indicators?: any
    perspectives?: any
    entry_price?: number
    stop_loss?: number
    take_profit?: number
    [key: string]: any
  }
  input_data?: {
    [key: string]: any
  }
  structured_report?: any
}

export interface OrchestratorDecision {
  decision_id: string
  timestamp: string
  instrument: string
  final_decision: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  agent_responses: AgentResponse[]
  reasoning: string
  signal_created?: boolean
  signal_id?: string
}

export interface StrategyRecommendation {
  available: boolean
  instrument: string
  expiry?: string
  recommendation?: {
    side: string
    option_type?: string
    strike?: number
    premium?: number
    quantity: number
    stop_loss_price?: number
    take_profit_price?: number
    reasoning: string
  }
  timestamp: string
}

export interface OptionsLeg {
  strike_price: number
  option_type: 'CE' | 'PE'
  position: 'BUY' | 'SELL'
  quantity: number
  premium?: number
}

export interface OptionsStrategy {
  available: boolean
  timestamp: string
  strategy_type: string
  underlying: string
  expiry: string
  confidence: number
  agent: string
  legs: OptionsLeg[]
  risk_analysis: {
    max_profit: number
    max_loss: number
    breakeven_points: number[]
    risk_reward_ratio: number
    margin_required: number
  }
  reasoning: string
}

export interface ExecutedOptionsStrategy {
  success: boolean
  strategy_type: string
  executed_legs: Array<{
    leg_id: string
    instrument: string
    side: string
    quantity: number
    price: number
    trade_id: string
  }>
  net_premium: number
  total_margin: number
  risk_analysis: any
  timestamp: string
  error?: string
}

export interface OptionsStrategyHistory {
  strategies: Array<{
    strategy_id: string
    strategy_type: string
    timestamp: string
    legs: Array<{
      instrument: string
      side: string
      quantity: number
      price: number
      leg_info: any
    }>
    total_margin: number
    net_premium: number
  }>
  count: number
}

export interface TradingSignal {
  signal_id: string
  condition_id?: string
  instrument: string
  action: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  reasoning: string
  timestamp: string
  status?: 'pending' | 'triggered' | 'executed' | 'expired' | 'cancelled' | 'monitoring'
  indicator?: string
  operator?: string
  threshold?: number
  current_value?: number
  conditions_met?: boolean
  stop_loss?: number
  take_profit?: number
  strategy_type?: string
  expires_at?: string
  execution_mode?: string
  parsed_conditions?: Array<{
    indicator: string
    operator: string
    threshold: number | number[]
    source?: string
    current_value?: number
  }>
  metadata?: any
}

interface TradingState {
  latestDecision: Decision | null
  portfolio: PortfolioSummary | null
  recentTrades: Trade[]
  agentStatuses: AgentStatus[]
  agentResponses: AgentResponse[]
  orchestratorDecisions: OrchestratorDecision[]
  strategyRecommendation: StrategyRecommendation | null
  optionsStrategy: OptionsStrategy | null
  optionsAlgoActive: boolean
  signals: TradingSignal[]
  loading: {
    decision: boolean
    portfolio: boolean
    trades: boolean
    agents: boolean
    agentResponses: boolean
    orchestrator: boolean
    strategy: boolean
    signals: boolean
    optionsStrategy: boolean
    executeOptions: boolean
  }
  error: string | null
  lastUpdated: string | null
}

const initialState: TradingState = {
  latestDecision: null,
  portfolio: null,
  recentTrades: [],
  agentStatuses: [],
  agentResponses: [],
  orchestratorDecisions: [],
  strategyRecommendation: null,
  optionsStrategy: null,
  optionsAlgoActive: false,
  signals: [],
  loading: {
    decision: false,
    portfolio: false,
    trades: false,
    agents: false,
    agentResponses: false,
    orchestrator: false,
    strategy: false,
    signals: false,
    optionsStrategy: false,
    executeOptions: false,
  },
  error: null,
  lastUpdated: null,
}

// Async thunks for API calls
export const fetchLatestDecision = createAsyncThunk(
  'trading/fetchLatestDecision',
  async () => {
    const response = await axios.get('/api/engine/decision/latest')
    return response.data
  }
)

export const fetchPortfolio = createAsyncThunk(
  'trading/fetchPortfolio',
  async () => {
    const response = await axios.get('/api/engine/portfolio')
    return response.data
  }
)

export const fetchRecentTrades = createAsyncThunk(
  'trading/fetchRecentTrades',
  async (limit: number = 20) => {
    const response = await axios.get(`${ENGINE_BASE}/api/engine/trades`, { params: { limit } })
    return response.data
  }
)

export const fetchAgentStatuses = createAsyncThunk(
  'trading/fetchAgentStatuses',
  async () => {
    const response = await axios.get(`${DASHBOARD_BASE}/api/agent-status`)
    const data = response.data

    // Transform the data to match the expected AgentStatus format
    if (data.agents) {
      return Object.values(data.agents).map((agent: any) => ({
        name: agent.name,
        status: agent.status,
        last_update: agent.last_update,
        signal: agent.signal,
        confidence: agent.confidence,
        summary: agent.summary
      }))
    }
    return []
  }
)

// New thunks for agent inspection (details, history, memory)
export interface AgentDetails {
  agent_name: string
  latest_decision?: any
  config?: any
}

export interface AgentMemoryItem {
  document: string
  metadata: any
  similarity?: number
}

const ENGINE_BASE = (import.meta.env.VITE_ENGINE_API_URL as string) || ''
const DASHBOARD_BASE = (import.meta.env.VITE_DASHBOARD_API_URL as string) || ''

export const fetchAgentDetails = createAsyncThunk(
  'trading/fetchAgentDetails',
  async (agentName: string, { rejectWithValue }) => {
    try {
      const response = await axios.get(`${ENGINE_BASE}/api/engine/agents/${encodeURIComponent(agentName)}/details`)
      return response.data as AgentDetails
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.detail || err.message || 'Failed to fetch agent details')
    }
  }
)

export const fetchAgentHistory = createAsyncThunk(
  'trading/fetchAgentHistory',
  async ({ agentName, limit = 50 }: { agentName: string; limit?: number }, { rejectWithValue }) => {
    try {
      const response = await axios.get(`${ENGINE_BASE}/api/engine/agents/${encodeURIComponent(agentName)}/history`, { params: { limit } })
      return response.data as any[]
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.detail || err.message || 'Failed to fetch agent history')
    }
  }
)

export const fetchAgentMemory = createAsyncThunk(
  'trading/fetchAgentMemory',
  async ({ agentName, q, limit = 10 }: { agentName: string; q?: string; limit?: number }, { rejectWithValue }) => {
    try {
      const params: any = { limit }
      if (q) params.q = q
      const response = await axios.get(`${ENGINE_BASE}/api/engine/agents/${encodeURIComponent(agentName)}/memory`, { params })
      return response.data as AgentMemoryItem[]
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.detail || err.message || 'Failed to fetch agent memory')
    }
  }
)

export const fetchAgentResponse = createAsyncThunk(
  'trading/fetchAgentResponse',
  async ({ agentName, responseId }: { agentName: string; responseId: string }, { rejectWithValue }) => {
    try {
      const response = await axios.get(`${ENGINE_BASE}/api/engine/agents/${encodeURIComponent(agentName)}/responses/${encodeURIComponent(responseId)}`)
      return response.data as any
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.detail || err.message || 'Failed to fetch agent response')
    }
  }
)

export const fetchAgentDependencies = createAsyncThunk(
  'trading/fetchAgentDependencies',
  async (_, { rejectWithValue }) => {
    try {
      const response = await axios.get(`${ENGINE_BASE}/api/engine/agents/dependencies`)
      return response.data as any
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.detail || err.message || 'Failed to fetch agent dependencies')
    }
  }
)

export const updateAgentConfig = createAsyncThunk(
  'trading/updateAgentConfig',
  async ({ agentName, config }: { agentName: string; config: any }, { rejectWithValue }) => {
    try {
      const response = await axios.post(`/api/engine/agents/${encodeURIComponent(agentName)}/config`, config)
      return response.data as any
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.detail || err.message || 'Failed to update agent config')
    }
  }
)

export const fetchStrategyRecommendation = createAsyncThunk(
  'trading/fetchStrategyRecommendation',
  async () => {
    const response = await axios.get(`${ENGINE_BASE}/api/engine/strategy/recommendation`)
    return response.data
  }
)

export const executeTrade = createAsyncThunk(
  'trading/executeTrade',
  async (tradeData: any, { rejectWithValue }) => {
    try {
      // Use User API for trade execution (supports Options, Futures, Spot)
      const response = await axios.post('/api/trading/execute', {
        ...tradeData,
        // Map frontend field names to backend expected names
        order_type: tradeData.order_type || tradeData.orderType,
        stop_loss: tradeData.stop_loss || tradeData.stopLoss,
        take_profit: tradeData.take_profit || tradeData.takeProfit,
        strike_price: tradeData.strike_price || tradeData.strike,
        expiry_date: tradeData.expiry_date || tradeData.expiry,
        option_type: tradeData.option_type || tradeData.optionType,
        instrument_type: tradeData.instrument_type || tradeData.instrumentType,
        strategy_type: tradeData.strategy_type || tradeData.strategyType,
      })
      return response.data
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.detail || err.response?.data?.error || err.message || 'Failed to execute trade')
    }
  }
)

export const toggleOptionsAlgo = createAsyncThunk(
  'trading/toggleOptionsAlgo',
  async (active: boolean) => {
    const response = await axios.post('/api/engine/options-algo/state', { active })
    return response.data
  }
)

export const fetchSignals = createAsyncThunk(
  'trading/fetchSignals',
  async (instrument: string = import.meta.env.VITE_INSTRUMENT_SYMBOL || 'BANKNIFTY26JANFUT', { rejectWithValue }) => {
    try {
      const response = await axios.get(`${ENGINE_BASE}/api/v1/signals/${instrument}`)
      // Transform the data to match expected format
      const signals = Array.isArray(response.data) ? response.data : []
      return signals.map((signal: any) => ({
        id: signal._id || signal.signal_id,
        signal_id: signal.signal_id,
        strategy: signal.action || signal.strategy || 'unknown', // Use action field for strategy
        instrument: signal.instrument,
        entry_price: signal.entry_price,
        stop_loss: signal.stop_loss,
        take_profit: signal.take_profit,
        confidence: signal.confidence || 0,
        status: signal.status || 'pending',
        timestamp: signal.timestamp,
        conditions: signal.conditions || [],
        reasoning: signal.reasoning || '',
        execution_mode: signal.execution_mode,
        parsed_conditions: signal.parsed_conditions,
        metadata: signal.metadata
      }))
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to fetch signals')
    }
  }
)

export const executeSignal = createAsyncThunk(
  'trading/executeSignal',
  async (signalId: string, { rejectWithValue }) => {
    try {
      const response = await axios.post(`/api/trading/execute/${signalId}`)
      return { signalId, result: response.data }
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to execute signal')
    }
  }
)

export const checkSignalConditions = createAsyncThunk(
  'trading/checkSignalConditions',
  async (signalId: string, { rejectWithValue }) => {
    try {
      const response = await axios.get(`/api/trading/conditions/${signalId}`)
      return { signalId, ...response.data }
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to check signal conditions')
    }
  }
)

export const executeSignalWhenReady = createAsyncThunk(
  'trading/executeSignalWhenReady',
  async (signalId: string, { rejectWithValue }) => {
    try {
      const response = await axios.post(`/api/trading/execute-when-ready/${signalId}`)
      return { signalId, ...response.data }
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to execute signal when ready')
    }
  }
)

export const fetchOptionsStrategy = createAsyncThunk(
  'trading/fetchOptionsStrategy',
  async (_, { rejectWithValue }) => {
    try {
      const response = await axios.get(`${ENGINE_BASE}/api/options-strategy-agent`)
      return response.data
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to fetch options strategy')
    }
  }
)

export const executeOptionsStrategy = createAsyncThunk(
  'trading/executeOptionsStrategy',
  async (strategyData?: any, { rejectWithValue }) => {
    try {
      const response = await axios.post(`${ENGINE_BASE}/api/options-strategy-execute`, strategyData || {})
      return response.data
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to execute options strategy')
    }
  }
)

export const fetchOptionsStrategyHistory = createAsyncThunk(
  'trading/fetchOptionsStrategyHistory',
  async (limit: number = 10, { rejectWithValue }) => {
    try {
      const response = await axios.get(`/api/options-strategy-history?limit=${limit}`)
      return response.data
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to fetch options strategy history')
    }
  }
)

export const fetchOrchestratorAnalysis = createAsyncThunk(
  'trading/fetchOrchestratorAnalysis',
  async ({ instrument, context }: { instrument: string; context?: any }, { rejectWithValue }) => {
    try {
      const response = await axios.post(`${ENGINE_BASE}/api/v1/analyze`)
      return response.data
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to run orchestrator analysis')
    }
  }
)

export const fetchOrchestratorDecisions = createAsyncThunk(
  'trading/fetchOrchestratorDecisions',
  async (limit: number = 20, { rejectWithValue }) => {
    try {
      const response = await axios.get('/api/orchestrator-decisions', { params: { limit } })
      return response.data.decisions || []
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to fetch orchestrator decisions')
    }
  }
)

const tradingSlice = createSlice({
  name: 'trading',
  initialState,
  reducers: {
    updateDecision: (state, action: PayloadAction<Decision>) => {
      // Normalize incoming decision data: prefer explicit 'direction' (BUY/SELL/HOLD) when present
      const payload = action.payload as any
      const normalizedSignal = payload.direction ?? payload.signal ?? 'HOLD'
      
      // Only update if the decision actually changed (prevent unnecessary re-renders)
      const newDecision = {
        ...payload,
        signal: normalizedSignal
      }
      
      // Compare key fields to avoid updates if nothing meaningful changed
      const current = state.latestDecision
      if (current && 
          current.signal === newDecision.signal &&
          current.confidence === newDecision.confidence &&
          current.entry_price === newDecision.entry_price &&
          current.stop_loss === newDecision.stop_loss &&
          current.take_profit === newDecision.take_profit &&
          current.instrument === newDecision.instrument) {
        // Decision hasn't meaningfully changed, skip update
        return
      }
      
      state.latestDecision = newDecision
      state.lastUpdated = new Date().toISOString()
    },
    updatePortfolio: (state, action: PayloadAction<PortfolioSummary>) => {
      state.portfolio = action.payload
      state.lastUpdated = new Date().toISOString()
    },
    addTrade: (state, action: PayloadAction<Trade>) => {
      state.recentTrades.unshift(action.payload)
      state.recentTrades = state.recentTrades.slice(0, 100) // Keep only last 100 trades
    },
    // Add or update a single signal in the signals array
    addOrUpdateSignal: (state, action: PayloadAction<Partial<TradingSignal>>) => {
      const incoming = action.payload as TradingSignal
      const existingIndex = state.signals.findIndex(s => s.signal_id === incoming.signal_id || s.condition_id === (incoming.condition_id as any))
      if (existingIndex >= 0) {
        // Merge fields
        state.signals[existingIndex] = {
          ...state.signals[existingIndex],
          ...incoming
        }
      } else {
        // Prepend new signal
        state.signals.unshift(incoming as TradingSignal)
        // Limit to 200 signals
        if (state.signals.length > 200) state.signals = state.signals.slice(0, 200)
      }
      state.lastUpdated = new Date().toISOString()
    },
    setSignals: (state, action: PayloadAction<TradingSignal[]>) => {
      state.signals = action.payload
      state.lastUpdated = new Date().toISOString()
    },
    updateAgentResponse: (state, action: PayloadAction<AgentResponse>) => {
      const response = action.payload
      const existingIndex = state.agentResponses.findIndex(r => r.agent === response.agent)
      if (existingIndex >= 0) {
        state.agentResponses[existingIndex] = response
      } else {
        state.agentResponses.push(response)
        // Keep only last 50 responses per agent
        state.agentResponses = state.agentResponses.slice(-50)
      }
      state.lastUpdated = new Date().toISOString()
    },
    updateAgentStatus: (state, action: PayloadAction<AgentStatus>) => {
      const status = action.payload
      const existingIndex = state.agentStatuses.findIndex(s => s.name === status.name)
      if (existingIndex >= 0) {
        state.agentStatuses[existingIndex] = status
      } else {
        state.agentStatuses.push(status)
        // Keep only last 20 agent statuses
        if (state.agentStatuses.length > 20) state.agentStatuses = state.agentStatuses.slice(-20)
      }
      state.lastUpdated = new Date().toISOString()
    },
    updateOrchestratorDecision: (state, action: PayloadAction<OrchestratorDecision>) => {
      const decision = action.payload
      state.orchestratorDecisions.unshift(decision)
      // Keep only last 20 decisions
      if (state.orchestratorDecisions.length > 20) {
        state.orchestratorDecisions = state.orchestratorDecisions.slice(0, 20)
      }
      state.lastUpdated = new Date().toISOString()
    },
    clearError: (state) => {
      state.error = null
    },
  },
  extraReducers: (builder) => {
    // Latest Decision
    builder
      .addCase(fetchLatestDecision.pending, (state) => {
        state.loading.decision = true
        state.error = null
      })
      .addCase(fetchLatestDecision.fulfilled, (state, action) => {
        state.loading.decision = false
        state.latestDecision = action.payload
        state.lastUpdated = new Date().toISOString()
      })
      .addCase(fetchLatestDecision.rejected, (state, action) => {
        state.loading.decision = false
        state.error = action.error.message || 'Failed to fetch latest decision'
      })

    // Portfolio
    builder
      .addCase(fetchPortfolio.pending, (state) => {
        state.loading.portfolio = true
      })
      .addCase(fetchPortfolio.fulfilled, (state, action) => {
        state.loading.portfolio = false
        state.portfolio = action.payload
      })
      .addCase(fetchPortfolio.rejected, (state, action) => {
        state.loading.portfolio = false
        state.error = action.error.message || 'Failed to fetch portfolio'
      })

    // Recent Trades
    builder
      .addCase(fetchRecentTrades.pending, (state) => {
        state.loading.trades = true
      })
      .addCase(fetchRecentTrades.fulfilled, (state, action) => {
        state.loading.trades = false
        state.recentTrades = action.payload
      })
      .addCase(fetchRecentTrades.rejected, (state, action) => {
        state.loading.trades = false
        state.error = action.error.message || 'Failed to fetch recent trades'
      })

    // Agent Statuses
    builder
      .addCase(fetchAgentStatuses.pending, (state) => {
        state.loading.agents = true
      })
      .addCase(fetchAgentStatuses.fulfilled, (state, action) => {
        state.loading.agents = false
        state.agentStatuses = action.payload || []
      })
      .addCase(fetchAgentStatuses.rejected, (state, action) => {
        state.loading.agents = false
        state.error = action.error.message || 'Failed to fetch agent statuses'
      })

    // Agent details / history / memory
    builder
      .addCase(fetchAgentDetails.pending, (state) => {
        state.loading.agents = true
        state.error = null
      })
      .addCase(fetchAgentDetails.fulfilled, (state, action: PayloadAction<AgentDetails>) => {
        state.loading.agents = false
        ;(state as any).agentDetails = action.payload
      })
      .addCase(fetchAgentDetails.rejected, (state, action) => {
        state.loading.agents = false
        state.error = String(action.payload || action.error?.message || 'Failed to fetch agent details')
      })

    builder
      .addCase(fetchAgentHistory.pending, (state) => {
        state.loading.agentResponses = true
        state.error = null
      })
      .addCase(fetchAgentHistory.fulfilled, (state, action: PayloadAction<any[]>) => {
        state.loading.agentResponses = false
        ;(state as any).agentHistory = action.payload
      })
      .addCase(fetchAgentHistory.rejected, (state, action) => {
        state.loading.agentResponses = false
        state.error = String(action.payload || action.error?.message || 'Failed to fetch agent history')
      })

    builder
      .addCase(fetchAgentMemory.pending, (state) => {
        state.loading.agentResponses = true
      })
      .addCase(fetchAgentMemory.fulfilled, (state, action: PayloadAction<AgentMemoryItem[]>) => {
        state.loading.agentResponses = false
        ;(state as any).agentMemory = action.payload
      })
      .addCase(fetchAgentMemory.rejected, (state, action) => {
        state.loading.agentResponses = false
        state.error = String(action.payload || action.error?.message || 'Failed to fetch agent memory')
      })

    // Single agent response
    builder
      .addCase(fetchAgentResponse.pending, (state) => {
        state.loading.agentResponses = true
      })
      .addCase(fetchAgentResponse.fulfilled, (state, action: PayloadAction<any>) => {
        state.loading.agentResponses = false
        ;(state as any).agentFullResponse = action.payload
      })
      .addCase(fetchAgentResponse.rejected, (state, action) => {
        state.loading.agentResponses = false
        state.error = String(action.payload || action.error?.message || 'Failed to fetch agent response')
      })

    // Agent dependencies and config update
    builder
      .addCase(fetchAgentDependencies.pending, (state) => {
        ;(state as any).loadingDependencies = true
      })
      .addCase(fetchAgentDependencies.fulfilled, (state, action: PayloadAction<any>) => {
        ;(state as any).loadingDependencies = false
        ;(state as any).agentDependencies = action.payload
      })
      .addCase(fetchAgentDependencies.rejected, (state, action) => {
        ;(state as any).loadingDependencies = false
        state.error = String(action.payload || action.error?.message || 'Failed to fetch agent dependencies')
      })

    builder
      .addCase(updateAgentConfig.pending, (state) => {
        ;(state as any).updatingConfig = true
      })
      .addCase(updateAgentConfig.fulfilled, (state, action: PayloadAction<any>) => {
        ;(state as any).updatingConfig = false
        ;(state as any).lastConfigUpdate = action.payload
      })
      .addCase(updateAgentConfig.rejected, (state, action) => {
        ;(state as any).updatingConfig = false
        state.error = String(action.payload || action.error?.message || 'Failed to update agent config')
      })

    // Orchestrator analysis (manual Run Analysis from UI)
    builder
      .addCase(fetchOrchestratorAnalysis.pending, (state) => {
        state.loading.orchestrator = true
        state.error = null
      })
      .addCase(fetchOrchestratorAnalysis.fulfilled, (state, action: any) => {
        state.loading.orchestrator = false
        // Normalize engine response into OrchestratorDecision
        const payload = action.payload || {}
        const arg = (action.meta && (action.meta.arg as any)) || {}
        const instrument = arg.instrument || payload.instrument || 'UNKNOWN'
        const newDecision: OrchestratorDecision = {
          decision_id: String(Date.now()),
          timestamp: new Date().toISOString(),
          instrument,
          final_decision: (payload.decision || 'HOLD') as any,
          confidence: payload.confidence || 0,
          agent_responses: payload.agent_responses || [],
          reasoning: payload.message || '',
          signal_created: false
        }
        state.orchestratorDecisions.unshift(newDecision)
        if (state.orchestratorDecisions.length > 20) {
          state.orchestratorDecisions = state.orchestratorDecisions.slice(0, 20)
        }
        state.lastUpdated = new Date().toISOString()
      })
      .addCase(fetchOrchestratorAnalysis.rejected, (state, action) => {
        state.loading.orchestrator = false
        state.error = String(action.payload || action.error?.message || 'Failed to run orchestrator analysis')
      })

    // Fetch Orchestrator Decisions (load existing decisions)
    builder
      .addCase(fetchOrchestratorDecisions.pending, (state) => {
        state.loading.orchestrator = true
        state.error = null
      })
      .addCase(fetchOrchestratorDecisions.fulfilled, (state, action: any) => {
        state.loading.orchestrator = false
        // Load existing decisions from API (don't duplicate with WebSocket updates)
        const decisions = action.payload || []
        // Only add decisions that don't already exist
        decisions.forEach((decision: OrchestratorDecision) => {
          const exists = state.orchestratorDecisions.some(d => d.decision_id === decision.decision_id)
          if (!exists) {
            state.orchestratorDecisions.unshift(decision)
          }
        })
        // Sort by timestamp (most recent first)
        state.orchestratorDecisions.sort((a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        )
        // Keep only last 20
        if (state.orchestratorDecisions.length > 20) {
          state.orchestratorDecisions = state.orchestratorDecisions.slice(0, 20)
        }
        state.lastUpdated = new Date().toISOString()
      })
      .addCase(fetchOrchestratorDecisions.rejected, (state, action) => {
        state.loading.orchestrator = false
        state.error = String(action.payload || action.error?.message || 'Failed to fetch orchestrator decisions')
      })

    // Strategy Recommendation
    builder
      .addCase(fetchStrategyRecommendation.pending, (state) => {
        state.loading.strategy = true
      })
      .addCase(fetchStrategyRecommendation.fulfilled, (state, action) => {
        state.loading.strategy = false
        state.strategyRecommendation = action.payload
      })
      .addCase(fetchStrategyRecommendation.rejected, (state, action) => {
        state.loading.strategy = false
        state.error = action.error.message || 'Failed to fetch strategy recommendation'
      })

    // Execute Trade
    builder
      .addCase(executeTrade.pending, (state) => {
        state.error = null
      })
      .addCase(executeTrade.fulfilled, (state, action) => {
        // Add new trade to recent trades
        if (action.payload.trade) {
          state.recentTrades.unshift(action.payload.trade)
          state.recentTrades = state.recentTrades.slice(0, 100)
        }
      })
      .addCase(executeTrade.rejected, (state, action) => {
        state.error = action.error.message || 'Failed to execute trade'
      })

    // Toggle Options Algo
    builder
      .addCase(toggleOptionsAlgo.pending, (state) => {
        state.error = null
      })
      .addCase(toggleOptionsAlgo.fulfilled, (state, action) => {
        state.optionsAlgoActive = action.payload.active
      })
      .addCase(toggleOptionsAlgo.rejected, (state, action) => {
        state.error = action.error.message || 'Failed to toggle options algo'
      })

    // Fetch Signals
    builder
      .addCase(fetchSignals.pending, (state) => {
        state.loading.signals = true
        state.error = null
      })
      .addCase(fetchSignals.fulfilled, (state, action) => {
        state.loading.signals = false
        state.signals = action.payload
        state.lastUpdated = new Date().toISOString()
      })
      .addCase(fetchSignals.rejected, (state, action) => {
        state.loading.signals = false
        state.error = action.error.message || 'Failed to fetch signals'
      })

    // Check Signal Conditions
    builder
      .addCase(checkSignalConditions.fulfilled, (state, action) => {
        const { signalId, conditions_met, can_execute } = action.payload
        const signal = state.signals.find(s => s.signal_id === signalId || s.condition_id === signalId)
        if (signal) {
          signal.conditions_met = conditions_met
          signal.status = can_execute ? 'triggered' : signal.status
        }
      })

    // Execute Signal When Ready
    builder
      .addCase(executeSignalWhenReady.fulfilled, (state, action) => {
        const { signalId, monitoring } = action.payload
        const signal = state.signals.find(s => s.signal_id === signalId || s.condition_id === signalId)
        if (signal) {
          signal.status = monitoring ? 'pending' : signal.status
        }
      })
      .addCase(executeSignalWhenReady.rejected, (state, action) => {
        state.error = action.error.message || 'Failed to execute signal when ready'
      })

    // Execute Signal Immediately
    builder
      .addCase(executeSignal.pending, (state) => {
        state.error = null
      })
      .addCase(executeSignal.fulfilled, (state, action) => {
        const { signalId } = action.payload
        const signal = state.signals.find(s => s.signal_id === signalId || s.condition_id === signalId)
        if (signal) {
          signal.status = 'executed'
        }
      })
      .addCase(executeSignal.rejected, (state, action) => {
        state.error = action.error.message || 'Failed to execute signal'
      })

    // Fetch Options Strategy
    builder
      .addCase(fetchOptionsStrategy.pending, (state) => {
        state.loading.optionsStrategy = true
        state.error = null
      })
      .addCase(fetchOptionsStrategy.fulfilled, (state, action) => {
        state.loading.optionsStrategy = false
        state.optionsStrategy = action.payload
        state.lastUpdated = new Date().toISOString()
      })
      .addCase(fetchOptionsStrategy.rejected, (state, action) => {
        state.loading.optionsStrategy = false
        state.error = action.error.message || 'Failed to fetch options strategy'
      })

    // Execute Options Strategy
    builder
      .addCase(executeOptionsStrategy.pending, (state) => {
        state.loading.executeOptions = true
        state.error = null
      })
      .addCase(executeOptionsStrategy.fulfilled, (state, action) => {
        state.loading.executeOptions = false
        // Add executed trades to recent trades
        if (action.payload.executed_legs) {
          action.payload.executed_legs.forEach((leg: any) => {
            state.recentTrades.unshift({
              id: leg.trade_id,
              timestamp: action.payload.timestamp,
              instrument: leg.instrument,
              side: leg.side as 'BUY' | 'SELL',
              quantity: leg.quantity,
              price: leg.price,
              pnl: 0, // Will be calculated later
              status: 'open'
            })
          })
          state.recentTrades = state.recentTrades.slice(0, 100)
        }
        state.lastUpdated = new Date().toISOString()
      })
      .addCase(executeOptionsStrategy.rejected, (state, action) => {
        state.loading.executeOptions = false
        state.error = action.error.message || 'Failed to execute options strategy'
      })

    // Fetch Options Strategy History
    builder
      .addCase(fetchOptionsStrategyHistory.fulfilled, (state, action) => {
        // This could be used to populate a history view, but for now we don't store it in state
        // The component can handle the response directly
      })
  },
})

export const { updateDecision, updatePortfolio, addTrade, clearError, addOrUpdateSignal, setSignals, updateAgentResponse, updateAgentStatus, updateOrchestratorDecision } = tradingSlice.actions
export default tradingSlice.reducer