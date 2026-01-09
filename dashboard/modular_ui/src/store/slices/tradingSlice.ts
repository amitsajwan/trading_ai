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
  status?: 'pending' | 'triggered' | 'executed' | 'expired' | 'cancelled'
  indicator?: string
  operator?: string
  threshold?: number
  current_value?: number
  conditions_met?: boolean
  stop_loss?: number
  take_profit?: number
  strategy_type?: string
  expires_at?: string
}

interface TradingState {
  latestDecision: Decision | null
  portfolio: PortfolioSummary | null
  recentTrades: Trade[]
  agentStatuses: AgentStatus[]
  strategyRecommendation: StrategyRecommendation | null
  optionsStrategy: OptionsStrategy | null
  optionsAlgoActive: boolean
  signals: TradingSignal[]
  loading: {
    decision: boolean
    portfolio: boolean
    trades: boolean
    agents: boolean
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
  strategyRecommendation: null,
  optionsStrategy: null,
  optionsAlgoActive: false,
  signals: [],
  loading: {
    decision: false,
    portfolio: false,
    trades: false,
    agents: false,
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
    const response = await axios.get('/api/engine/trades', { params: { limit } })
    return response.data
  }
)

export const fetchAgentStatuses = createAsyncThunk(
  'trading/fetchAgentStatuses',
  async () => {
    const response = await axios.get('/api/engine/agents/status')
    return response.data
  }
)

export const fetchStrategyRecommendation = createAsyncThunk(
  'trading/fetchStrategyRecommendation',
  async () => {
    const response = await axios.get('/api/engine/strategy/recommendation')
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
  async (instrument: string = 'BANKNIFTY', { rejectWithValue }) => {
    try {
      const response = await axios.get(`/api/trading/signals?instrument=${instrument}`)
      return response.data.signals || []
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to fetch signals')
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
      const response = await axios.get('/api/options-strategy-agent')
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
      const response = await axios.post('/api/options-strategy-execute', strategyData || {})
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
        state.agentStatuses = action.payload.agents || []
      })
      .addCase(fetchAgentStatuses.rejected, (state, action) => {
        state.loading.agents = false
        state.error = action.error.message || 'Failed to fetch agent statuses'
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

export const { updateDecision, updatePortfolio, addTrade, clearError, addOrUpdateSignal, setSignals } = tradingSlice.actions
export default tradingSlice.reducer