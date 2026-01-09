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
      const response = await axios.get('/api/analytics/performance')
      return response.data
    } catch (err: any) {
      // Return empty data if endpoint doesn't exist (404)
      if (err.response?.status === 404) {
        return { data: [], metrics: {} }
      }
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to fetch performance metrics')
    }
  }
)

export const fetchRiskMetrics = createAsyncThunk(
  'analytics/fetchRiskMetrics',
  async (_, { rejectWithValue }) => {
    try {
      const response = await axios.get('/api/analytics/risk')
      return response.data
    } catch (err: any) {
      // Return empty data if endpoint doesn't exist (404)
      if (err.response?.status === 404) {
        return { data: [], metrics: {} }
      }
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to fetch risk metrics')
    }
  }
)

export const fetchLLMMetrics = createAsyncThunk(
  'analytics/fetchLLMMetrics',
  async (_, { rejectWithValue }) => {
    try {
      const response = await axios.get('/api/analytics/llm')
      return response.data
    } catch (err: any) {
      // Return empty data if endpoint doesn't exist (404)
      if (err.response?.status === 404) {
        return { data: [], metrics: {} }
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