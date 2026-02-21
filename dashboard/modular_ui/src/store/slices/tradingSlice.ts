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
  status: 'active' | 'inactive' | 'error' | 'excluded' | 'stale' | 'idle'
  last_update: string
  signal?: string
  confidence?: number
  summary?: any
  technical_indicators?: any
  reasoning?: string
  cycle_info?: any
  run_id?: string
  cycle_id?: string
  ran_in_current_run?: boolean
}

export interface AgentResponse {
  agent: string
  decision: string
  confidence?: number
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
  run_id?: string
  cycle_id?: string
  response_id?: string
}

export interface OrchestratorDecision {
  decision_id: string
  timestamp: string
  instrument: string
  final_decision: string
  confidence: number
  agent_responses: AgentResponse[]
  reasoning: string
  signal_created?: boolean
  signal_id?: string
  run_id?: string
  cycle_id?: string
  research_thesis?: {
    agent?: string
    decision?: string
    confidence?: number
    reasoning?: string
  } | null
  execution_verdict?: {
    decision?: string
    confidence?: number
    judge?: string
    can_trade?: boolean
    gate_reason?: string
    status?: string
    signal_created?: boolean
  } | null
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
  action: string
  signal?: string
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
  reason_hash?: string
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
    const response = await axios.get('/api/latest-signal')
    const payload = response.data?.signal || response.data || {}
    return {
      instrument: payload.instrument || 'BANKNIFTY-I',
      signal: payload.action || payload.signal || 'HOLD',
      confidence: Number(payload.confidence || 0),
      reasoning: payload.reasoning || '',
      timestamp: payload.timestamp || new Date().toISOString(),
      entry_price: payload.entry_price,
      stop_loss: payload.stop_loss,
      take_profit: payload.take_profit,
    }
  }
)

export const fetchPortfolio = createAsyncThunk(
  'trading/fetchPortfolio',
  async () => {
    const response = await axios.get('/api/portfolio')
    const payload = response.data || {}
    const summary = payload.summary || {}
    return {
      total_value: Number(summary.total_value || 0),
      cash_balance: Number(summary.cash_balance || 0),
      positions: payload.positions || [],
      day_pnl: Number(summary.day_pnl || 0),
      total_pnl: Number(summary.total_pnl || 0),
      margin_used: Number(summary.margin_used || 0),
      margin_available: Number(summary.margin_available || 0),
      positions_count: Number(summary.positions_count || (payload.positions || []).length || 0),
      timestamp: payload.timestamp || new Date().toISOString(),
    }
  }
)

export const fetchRecentTrades = createAsyncThunk(
  'trading/fetchRecentTrades',
  async (limit: number = 20) => {
    const response = await axios.get('/api/recent-trades', { params: { limit } })
    return Array.isArray(response.data) ? response.data : []
  }
)

export const fetchAgentStatuses = createAsyncThunk(
  'trading/fetchAgentStatuses',
  async (_, { rejectWithValue }) => {
    const toOptionalConfidence = (value: any): number | undefined => {
      if (value === null || value === undefined || value === '') return undefined
      const n = Number(value)
      if (!Number.isFinite(n) || n < 0) return undefined
      if (n <= 1) return n
      if (n <= 100) return n / 100
      return undefined
    }

    const normalizeDashboardPayload = (data: any): AgentStatus[] | null => {
      if (!(data?.agents && typeof data.agents === 'object')) return null
      return Object.values(data.agents).map((agent: any) => ({
        name: agent.name,
        status: (agent.status || 'idle') as AgentStatus['status'],
        last_update: agent.last_update,
        signal: agent.signal,
        confidence: toOptionalConfidence(agent.confidence),
        summary: agent.summary,
        reasoning: agent.reasoning,
        // Preserve true provenance; do not stamp current run on legacy/stale records.
        run_id: agent.run_id || '',
        cycle_id: agent.cycle_id || '',
        ran_in_current_run:
          typeof agent.ran_in_current_run === 'boolean'
            ? agent.ran_in_current_run
            : undefined
      }))
    }

    const normalizeEnginePayload = (data: any): AgentStatus[] | null => {
      if (!Array.isArray(data)) return null
      return data.map((agent: any) => {
        const rawLastDecision = agent.last_decision
        const isDecisionObject = rawLastDecision && typeof rawLastDecision === 'object' && !Array.isArray(rawLastDecision)
        const signal = isDecisionObject
          ? (rawLastDecision.decision || rawLastDecision.signal || '')
          : (rawLastDecision || '')
        const reasoning = isDecisionObject
          ? (rawLastDecision.reasoning || agent.reasoning)
          : agent.reasoning
        const confidence = toOptionalConfidence(
          isDecisionObject ? rawLastDecision.confidence ?? agent.confidence : agent.confidence
        )

        return {
          name: agent.name,
          status: (agent.status || agent.state || 'idle') as AgentStatus['status'],
          last_update: agent.updated_at || agent.last_update || '',
          signal,
          confidence,
          summary: agent,
          reasoning,
          run_id: agent.run_id || '',
          cycle_id: agent.cycle_id || '',
          ran_in_current_run:
            typeof agent.ran_in_current_run === 'boolean'
              ? agent.ran_in_current_run
              : undefined
        }
      })
    }

    const endpoints = [
      // Prefer engine endpoint first: faster path and richer run metadata.
      '/api/engine/agents/status',
      '/api/agent-status',
    ]

    let lastError = 'Failed to fetch agent statuses'
    try {
      for (const endpoint of endpoints) {
        try {
          const response = await axios.get(endpoint, { timeout: 20000 })
          const data = response.data

          const dashboardNormalized = normalizeDashboardPayload(data)
          if (dashboardNormalized) return dashboardNormalized

          const engineNormalized = normalizeEnginePayload(data)
          if (engineNormalized) return engineNormalized

          lastError = `Agent status payload malformed from ${endpoint}`
        } catch (err: any) {
          lastError = err?.response?.data?.error || err?.message || `Failed endpoint ${endpoint}`
        }
      }

      return rejectWithValue(lastError)
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to fetch agent statuses')
    }
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

const ENGINE_BASE = ''

function extractSignalsFromPayload(payload: any): any[] {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.signals)) return payload.signals
  if (Array.isArray(payload?.data)) return payload.data
  if (Array.isArray(payload?.items)) return payload.items
  return []
}

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
  async (instrument: string | undefined, { rejectWithValue }) => {
    try {
      const requestedInstrument = (instrument || '').trim().toUpperCase()
      let runtimeInstrument = requestedInstrument
      if (!runtimeInstrument) {
        try {
          const modeResp = await axios.get('/api/control/mode/info')
          runtimeInstrument = String(modeResp?.data?.instrument || '').trim().toUpperCase()
        } catch {
          // Best-effort only; fallback below.
        }
      }
      const targetInstrument =
        runtimeInstrument ||
        ((import.meta.env.VITE_INSTRUMENT_SYMBOL as string) || 'BANKNIFTY-I').toUpperCase()

      const response = await axios.get(`/api/v1/signals/${encodeURIComponent(targetInstrument)}`, {
        params: { limit: 200 }
      })
      let signals = extractSignalsFromPayload(response.data)

      // Recover from stale UI instrument by retrying with backend active instrument.
      if (requestedInstrument && signals.length === 0) {
        const fallbackModeResp = await axios.get('/api/control/mode/info')
        const fallbackInstrument = String(fallbackModeResp?.data?.instrument || '').trim().toUpperCase()
        const fallbackResponse = fallbackInstrument
          ? await axios.get(`/api/v1/signals/${encodeURIComponent(fallbackInstrument)}`, { params: { limit: 200 } })
          : await axios.get(`/api/v1/signals/${encodeURIComponent('BANKNIFTY-I')}`, { params: { limit: 200 } })
        signals = extractSignalsFromPayload(fallbackResponse.data)
      }

      return signals.map((signal: any) => ({
        id: signal._id || signal.signal_id,
        signal_id: signal.signal_id || signal.id || signal.condition_id,
        condition_id: signal.condition_id,
        strategy: signal.action || signal.signal || signal.strategy || 'unknown',
        signal: signal.signal || signal.action || signal.strategy || 'HOLD',
        action: signal.action || signal.signal || signal.strategy || 'HOLD',
        instrument: signal.instrument || targetInstrument || 'BANKNIFTY-I',
        entry_price: signal.entry_price,
        stop_loss: signal.stop_loss,
        take_profit: signal.take_profit,
        confidence: Number(signal.confidence || 0),
        status: signal.status || 'pending',
        timestamp: signal.timestamp || signal.created_at || new Date().toISOString(),
        indicator: signal.indicator,
        operator: signal.operator,
        threshold: signal.threshold,
        current_value: signal.current_value,
        reason_hash: signal.reason_hash,
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
  async (strategyData: any, { rejectWithValue }) => {
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
      const response = await axios.post('/api/trading/cycle', {
        instrument,
        context: context || {},
      })
      return response.data
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to run orchestrator analysis')
    }
  }
)

export const fetchOrchestratorDecisions = createAsyncThunk(
  'trading/fetchOrchestratorDecisions',
  async (
    arg: number | { limit?: number; instrument?: string } = 20,
    { rejectWithValue, getState }
  ) => {
    try {
      const requestedLimit = typeof arg === 'number' ? arg : (arg?.limit ?? 20)
      const requestedInstrument = typeof arg === 'number' ? '' : (arg?.instrument || '')

      const state = getState() as any
      const stateInstrument =
        state?.ui?.executionMode?.instrument ||
        state?.trading?.latestDecision?.instrument ||
        ''

      let runtimeInstrument = (requestedInstrument || stateInstrument || '').toUpperCase()
      if (!runtimeInstrument) {
        try {
          const modeInfo = await axios.get('/api/control/mode/info')
          runtimeInstrument = String(modeInfo?.data?.instrument || '').toUpperCase()
        } catch {
          // Best effort only; final fallback below.
        }
      }
      const instrument =
        runtimeInstrument ||
        ((import.meta.env.VITE_INSTRUMENT_SYMBOL as string) || 'BANKNIFTY-I').toUpperCase()

      const response = await axios.get('/api/orchestrator-decisions', {
        params: { limit: requestedLimit, instrument, include_history: false }
      })
      const rows = response.data.decisions || []
      return rows.map((d: any) => {
        const ts = d.timestamp || d.created_at || new Date().toISOString()
        const runId = d.run_id || d.details?.run_id || d.orchestrator_run_id
        const cycleId = d.cycle_id || d.details?.cycle_id || d.invocation_id
        const agentResponses = (d.agent_responses || [])
          .filter((r: any) => !!(r && r.agent))
          .map((r: any) => ({ ...r, agent: String(r.agent) }))
        return {
          ...d,
          timestamp: ts,
          run_id: runId,
          cycle_id: cycleId,
          agent_responses: agentResponses,
          research_thesis: d.research_thesis || d.details?.research_thesis || null,
          execution_verdict: d.execution_verdict || d.details?.execution_verdict || null,
          decision_id:
            d.decision_id ||
            d._id ||
            d.signal_id ||
            `${d.instrument || instrument}:${runId || ''}:${cycleId || ''}:${d.final_decision || d.decision || 'HOLD'}:${ts}`,
        }
      })
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
      const key =
        response.response_id ||
        `${response.agent || 'UNKNOWN'}:${response.run_id || ''}:${response.cycle_id || ''}:${response.timestamp || ''}`
      const existingIndex = state.agentResponses.findIndex(r =>
        (r.response_id && response.response_id && r.response_id === response.response_id) ||
        `${r.agent || 'UNKNOWN'}:${r.run_id || ''}:${r.cycle_id || ''}:${r.timestamp || ''}` === key
      )
      if (existingIndex >= 0) {
        state.agentResponses[existingIndex] = { ...state.agentResponses[existingIndex], ...response }
      } else {
        state.agentResponses.unshift(response)
        // Keep only last 200 responses across runs
        state.agentResponses = state.agentResponses.slice(0, 200)
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
      const compositeKey = `${decision.instrument || ''}:${decision.run_id || ''}:${decision.cycle_id || ''}:${decision.final_decision || ''}:${decision.timestamp || ''}`
      const existingIndex = state.orchestratorDecisions.findIndex(d =>
        (d.decision_id && decision.decision_id && d.decision_id === decision.decision_id) ||
        `${d.instrument || ''}:${d.run_id || ''}:${d.cycle_id || ''}:${d.final_decision || ''}:${d.timestamp || ''}` === compositeKey
      )
      if (existingIndex >= 0) {
        state.orchestratorDecisions[existingIndex] = {
          ...state.orchestratorDecisions[existingIndex],
          ...decision,
          // Prefer richer agent breakdown when subsequent update arrives.
          agent_responses:
            (decision.agent_responses && decision.agent_responses.length > 0)
              ? decision.agent_responses
              : state.orchestratorDecisions[existingIndex].agent_responses
        }
      } else {
        state.orchestratorDecisions.unshift(decision)
      }
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
        const rawAgentResponses =
          payload.agent_responses ||
          payload.details?.agent_responses ||
          payload.details?.agent_results ||
          []
        const normalizedAgentResponses = (rawAgentResponses || [])
          .filter((r: any) => !!(r && r.agent))
          .map((r: any) => ({
            ...r,
            agent: String(r.agent),
          }))
        const newDecision: OrchestratorDecision = {
          decision_id:
            payload.decision_id ||
            payload._id ||
            `${instrument}:${payload.run_id || ''}:${payload.cycle_id || ''}:${Date.now()}`,
          timestamp: payload.timestamp || new Date().toISOString(),
          instrument,
          final_decision: (payload.final_decision || payload.decision || 'HOLD') as any,
          confidence: payload.confidence || 0,
          agent_responses: normalizedAgentResponses,
          reasoning: payload.reasoning || payload.message || '',
          research_thesis: payload.research_thesis || payload.details?.research_thesis || null,
          execution_verdict: payload.execution_verdict || payload.details?.execution_verdict || null,
          run_id: payload.run_id || payload.details?.run_id,
          cycle_id: payload.cycle_id || payload.details?.cycle_id,
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
        // Preserve existing cards during refresh to avoid UI blink.
        state.loading.orchestrator = state.orchestratorDecisions.length === 0
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

