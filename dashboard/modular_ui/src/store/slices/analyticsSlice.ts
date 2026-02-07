import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import axios from 'axios'

export interface PerformanceMetrics {
  total_pnl: number
  win_rate: number
  total_trades: number
  avg_win: number
  avg_loss: number
  largest_win: number
  largest_loss: number
  sharpe_ratio: number
  max_drawdown: number
  current_streak: number
  best_streak: number
  worst_streak: number
}

export interface RiskMetrics {
  sharpe_ratio: number
  max_drawdown: number
  var_95: number
  total_exposure: number
  portfolio_value: number
  daily_var: number
  stress_test_loss: number
  correlation_matrix: Record<string, Record<string, number>>
}

export interface LLMMetrics {
  providers: Record<string, {
    status: string
    requests_today: number
    requests_per_minute: number
    tokens_today: number
    last_error?: string
    last_error_time?: string
  }>
}

interface AnalyticsState {
  performance: PerformanceMetrics | null
  risk: RiskMetrics | null
  llm: LLMMetrics | null
  loading: {
    performance: boolean
    risk: boolean
    llm: boolean
  }
  error: string | null
  lastUpdated: string | null
}

const initialState: AnalyticsState = {
  performance: null,
  risk: null,
  llm: null,
  loading: {
    performance: false,
    risk: false,
    llm: false,
  },
  error: null,
  lastUpdated: null,
}

export const fetchPerformanceMetrics = createAsyncThunk(
  'analytics/fetchPerformanceMetrics',
  async (_, { rejectWithValue }) => {
    try {
      console.log('📊 Fetching performance metrics...')
      const response = await axios.get('/api/analytics/performance', { timeout: 10000 }) // 10 second timeout
      console.log('📊 Performance metrics received:', response.data)
      return response.data
    } catch (err: any) {
      console.error('❌ Performance metrics fetch failed:', err)
      // Return empty data if endpoint doesn't exist (404) or timeout
      if (err.response?.status === 404 || err.code === 'ECONNABORTED') {
        console.log('📊 Performance endpoint not available, returning fallback data')
        return {
          total_pnl: 0,
          win_rate: 0,
          total_trades: 0,
          avg_win: 0,
          avg_loss: 0,
          largest_win: 0,
          largest_loss: 0,
          sharpe_ratio: 0,
          max_drawdown: 0,
          current_streak: 0,
          best_streak: 0,
          worst_streak: 0
        }
      }
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to fetch performance metrics')
    }
  }
)

export const fetchRiskMetrics = createAsyncThunk(
  'analytics/fetchRiskMetrics',
  async (_, { rejectWithValue }) => {
    try {
      console.log('📊 Fetching risk metrics...')
      const response = await axios.get('/api/analytics/risk', { timeout: 10000 })
      console.log('📊 Risk metrics received:', response.data)
      return response.data
    } catch (err: any) {
      console.error('❌ Risk metrics fetch failed:', err)
      // Return fallback data if endpoint doesn't exist (404) or timeout
      if (err.response?.status === 404 || err.code === 'ECONNABORTED') {
        console.log('📊 Risk endpoint not available, returning fallback data')
        return {
          sharpe_ratio: 0,
          max_drawdown: 0,
          var_95: 0,
          total_exposure: 0,
          portfolio_value: 0,
          daily_var: 0,
          stress_test_loss: 0,
          correlation_matrix: {}
        }
      }
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to fetch risk metrics')
    }
  }
)

export const fetchLLMMetrics = createAsyncThunk(
  'analytics/fetchLLMMetrics',
  async (_, { rejectWithValue }) => {
    try {
      console.log('📊 Fetching LLM metrics...')
      const response = await axios.get('/api/analytics/llm', { timeout: 10000 })
      console.log('📊 LLM metrics received:', response.data)
      return response.data
    } catch (err: any) {
      console.error('❌ LLM metrics fetch failed:', err)
      // Return fallback data if endpoint doesn't exist (404) or timeout
      if (err.response?.status === 404 || err.code === 'ECONNABORTED') {
        console.log('📊 LLM endpoint not available, returning fallback data')
        return {
          providers: {
            groq: {
              status: 'unavailable',
              requests_today: 0,
              requests_per_minute: 0,
              tokens_today: 0
            },
            openai: {
              status: 'unavailable',
              requests_today: 0,
              requests_per_minute: 0,
              tokens_today: 0
            }
          }
        }
      }
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to fetch LLM metrics')
    }
  }
)

const analyticsSlice = createSlice({
  name: 'analytics',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchPerformanceMetrics.pending, (state) => {
        state.loading.performance = true
        state.error = null
      })
      .addCase(fetchPerformanceMetrics.fulfilled, (state, action) => {
        state.loading.performance = false
        state.performance = action.payload
        state.lastUpdated = new Date().toISOString()
      })
      .addCase(fetchPerformanceMetrics.rejected, (state, action) => {
        state.loading.performance = false
        state.error = action.error.message || 'Failed to fetch performance metrics'
      })
      .addCase(fetchRiskMetrics.pending, (state) => {
        state.loading.risk = true
      })
      .addCase(fetchRiskMetrics.fulfilled, (state, action) => {
        state.loading.risk = false
        state.risk = action.payload
      })
      .addCase(fetchRiskMetrics.rejected, (state, action) => {
        state.loading.risk = false
        state.error = action.error.message || 'Failed to fetch risk metrics'
      })
      .addCase(fetchLLMMetrics.pending, (state) => {
        state.loading.llm = true
      })
      .addCase(fetchLLMMetrics.fulfilled, (state, action) => {
        state.loading.llm = false
        state.llm = action.payload
      })
      .addCase(fetchLLMMetrics.rejected, (state, action) => {
        state.loading.llm = false
        state.error = action.error.message || 'Failed to fetch LLM metrics'
      })
  },
})

export const { clearError } = analyticsSlice.actions
export default analyticsSlice.reducer