import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import axios from 'axios'

export interface TickData {
  instrument: string
  last_price: number
  timestamp: string
  volume?: number
  oi?: number
}

export interface OHLCData {
  timestamp?: string
  start_at?: string  // Alternative field name from API
  open: number
  high: number
  low: number
  close: number
  volume: number
  instrument?: string
  timeframe?: string
}

export interface OptionStrike {
  strike: number
  ce_ltp?: number
  ce_oi?: number
  ce_iv?: number
  pe_ltp?: number
  pe_oi?: number
  pe_iv?: number
}

export interface OptionsChain {
  available?: boolean
  futures_price?: number
  expiry: string
  chain?: OptionStrike[]
  strikes?: OptionStrike[]  // Alternative field name from API
  instrument?: string
  pcr?: number
  max_pain?: number
  timestamp?: string
}

export interface MarketOverview {
  instrument: string
  current_price: number
  change_24h: number
  change_percent_24h: number
  volume_24h: number
  high_24h: number
  low_24h: number
  vwap: number
  timestamp: string
  status: string
}

export interface TechnicalIndicators {
  [key: string]: any
  timestamp?: string
  instrument?: string
}

interface MarketDataState {
  currentTick: TickData | null
  ohlcData: OHLCData[]
  optionsChain: OptionsChain | null
  overview: MarketOverview | null
  orderFlow: any | null
  technicalIndicators: TechnicalIndicators | null
  loading: {
    tick: boolean
    ohlc: boolean
    options: boolean
    overview: boolean
    orderFlow: boolean
  }
  error: string | null
  lastUpdated: string | null
}

const initialState: MarketDataState = {
  currentTick: null,
  ohlcData: [],
  optionsChain: null,
  overview: null,
  orderFlow: null,
  technicalIndicators: null,
  loading: {
    tick: false,
    ohlc: false,
    options: false,
    overview: false,
    orderFlow: false,
  },
  error: null,
  lastUpdated: null,
}

// Async thunks for API calls
export const fetchCurrentTick = createAsyncThunk(
  'marketData/fetchCurrentTick',
  async (instrument: string = 'BANKNIFTY') => {
    const response = await axios.get(`/api/market-data/tick/${instrument}`)
    return response.data
  }
)

export const fetchOHLCData = createAsyncThunk(
  'marketData/fetchOHLCData',
  async ({ instrument, timeframe, limit }: { instrument: string; timeframe: string; limit: number }) => {
    const response = await axios.get(`/api/market-data/ohlc/${instrument}`, {
      params: { timeframe, limit }
    })
    return response.data
  }
)

export const fetchOptionsChain = createAsyncThunk(
  'marketData/fetchOptionsChain',
  async (instrument: string = 'BANKNIFTY') => {
    const response = await axios.get(`/api/market-data/options/chain/${instrument}`)
    const data = response.data
    
    // Normalize response: API returns {strikes, expiry, instrument}, Redux expects {chain, available}
    if (data.strikes && !data.chain) {
      return {
        ...data,
        chain: data.strikes,
        available: true,
      }
    }
    
    return {
      ...data,
      available: data.available !== false, // Default to true if not specified
    }
  }
)

export const fetchMarketOverview = createAsyncThunk(
  'marketData/fetchMarketOverview',
  async () => {
    const response = await axios.get('/api/market-data')
    return response.data
  }
)

export const fetchOrderFlow = createAsyncThunk(
  'marketData/fetchOrderFlow',
  async (_, { rejectWithValue }) => {
    try {
      const response = await axios.get('/api/order-flow')
      return response.data
    } catch (err: any) {
      // Return empty data if endpoint doesn't exist (404)
      if (err.response?.status === 404) {
        return { data: [], flow: {} }
      }
      return rejectWithValue(err.response?.data?.error || err.message || 'Failed to fetch order flow')
    }
  }
)

const marketDataSlice = createSlice({
  name: 'marketData',
  initialState,
  reducers: {
    updateTick: (state, action: PayloadAction<TickData>) => {
      const newTick = action.payload
      const oldTick = state.currentTick
      
      // Only update if price actually changed (prevent unnecessary re-renders from duplicate ticks)
      if (oldTick && 
          oldTick.last_price === newTick.last_price &&
          oldTick.instrument === newTick.instrument &&
          oldTick.volume === newTick.volume &&
          oldTick.oi === newTick.oi) {
        // Tick data hasn't changed, skip update
        return
      }
      
      state.currentTick = newTick
      state.lastUpdated = new Date().toISOString()
      
      // Also update overview if it exists - update current_price and timestamp
      if (state.overview) {
        const instrument = newTick.instrument || 'BANKNIFTY'
        // Update if instrument matches or if overview doesn't have instrument set
        if (instrument === state.overview.instrument || !state.overview.instrument) {
          const newPrice = newTick.last_price
          const currentPrice = state.overview.current_price
          
          // Only update if price changed (prevent flickering from rapid updates)
          if (Math.abs(newPrice - currentPrice) > 0.01) {
            // Calculate price change from the original overview price (not from last tick)
            // This maintains the 24h change calculation
            const basePrice = state.overview.current_price
            const priceChange = newPrice - basePrice
            const priceChangePercent = basePrice > 0 ? (priceChange / basePrice) * 100 : 0
            
            // Update overview with new tick data
            state.overview.current_price = newPrice
            state.overview.change_24h = priceChange
            state.overview.change_percent_24h = priceChangePercent
            state.overview.timestamp = newTick.timestamp || new Date().toISOString()
            
            // Update high/low if needed (tracking intraday high/low)
            if (newPrice > state.overview.high_24h) {
              state.overview.high_24h = newPrice
            }
            if (newPrice < state.overview.low_24h) {
              state.overview.low_24h = newPrice
            }
          } else {
            // Price hasn't changed significantly, just update timestamp
            state.overview.timestamp = newTick.timestamp || new Date().toISOString()
          }
          
          // Update instrument if not set
          if (!state.overview.instrument) {
            state.overview.instrument = instrument
          }
        }
      }
    },
    clearError: (state) => {
      state.error = null
    },
    updateIndicators: (state, action: PayloadAction<TechnicalIndicators>) => {
      state.technicalIndicators = {
        ...state.technicalIndicators,
        ...action.payload,
        timestamp: action.payload.timestamp || new Date().toISOString(),
      }
      state.lastUpdated = new Date().toISOString()
    },
    updateOHLC: (state, action: PayloadAction<OHLCData>) => {
      // Add or update OHLC candle data
      const newCandle = action.payload
      const existingIndex = state.ohlcData.findIndex(
        (candle) => 
          candle.timestamp === newCandle.timestamp || 
          candle.start_at === newCandle.start_at ||
          (candle.instrument === newCandle.instrument && 
           candle.timeframe === newCandle.timeframe &&
           Math.abs(new Date(candle.timestamp || candle.start_at || '').getTime() - 
                   new Date(newCandle.timestamp || newCandle.start_at || '').getTime()) < 60000) // Within 1 minute
      )
      
      if (existingIndex >= 0) {
        // Update existing candle
        state.ohlcData[existingIndex] = newCandle
      } else {
        // Add new candle and sort by timestamp
        state.ohlcData.push(newCandle)
        state.ohlcData.sort((a, b) => {
          const timeA = new Date(a.timestamp || a.start_at || '').getTime()
          const timeB = new Date(b.timestamp || b.start_at || '').getTime()
          return timeA - timeB
        })
        // Keep only last 500 candles to prevent memory issues
        if (state.ohlcData.length > 500) {
          state.ohlcData = state.ohlcData.slice(-500)
        }
      }
      state.lastUpdated = new Date().toISOString()
    },
    updateOptionsChain: (state, action: PayloadAction<Partial<OptionsChain>>) => {
      if (state.optionsChain) {
        // Merge updates into existing options chain
        state.optionsChain = {
          ...state.optionsChain,
          ...action.payload,
          timestamp: action.payload.timestamp || state.optionsChain.timestamp || new Date().toISOString(),
        }
      } else {
        // Create new options chain if it doesn't exist
        state.optionsChain = {
          ...action.payload,
          timestamp: action.payload.timestamp || new Date().toISOString(),
        } as OptionsChain
      }
      state.lastUpdated = new Date().toISOString()
    },
  },
  extraReducers: (builder) => {
    // Current Tick
    builder
      .addCase(fetchCurrentTick.pending, (state) => {
        state.loading.tick = true
        state.error = null
      })
      .addCase(fetchCurrentTick.fulfilled, (state, action) => {
        state.loading.tick = false
        state.currentTick = action.payload
        state.lastUpdated = new Date().toISOString()
      })
      .addCase(fetchCurrentTick.rejected, (state, action) => {
        state.loading.tick = false
        state.error = action.error.message || 'Failed to fetch tick data'
      })

    // OHLC Data
    builder
      .addCase(fetchOHLCData.pending, (state) => {
        state.loading.ohlc = true
      })
      .addCase(fetchOHLCData.fulfilled, (state, action) => {
        state.loading.ohlc = false
        state.ohlcData = action.payload
      })
      .addCase(fetchOHLCData.rejected, (state, action) => {
        state.loading.ohlc = false
        state.error = action.error.message || 'Failed to fetch OHLC data'
      })

    // Options Chain
    builder
      .addCase(fetchOptionsChain.pending, (state) => {
        state.loading.options = true
      })
      .addCase(fetchOptionsChain.fulfilled, (state, action) => {
        state.loading.options = false
        state.optionsChain = action.payload
      })
      .addCase(fetchOptionsChain.rejected, (state, action) => {
        state.loading.options = false
        state.error = action.error.message || 'Failed to fetch options chain'
      })

    // Market Overview
    builder
      .addCase(fetchMarketOverview.pending, (state) => {
        state.loading.overview = true
      })
      .addCase(fetchMarketOverview.fulfilled, (state, action) => {
        state.loading.overview = false
        state.overview = action.payload
      })
      .addCase(fetchMarketOverview.rejected, (state, action) => {
        state.loading.overview = false
        state.error = action.error.message || 'Failed to fetch market overview'
      })

    // Order Flow
    builder
      .addCase(fetchOrderFlow.pending, (state) => {
        state.loading.orderFlow = true
      })
      .addCase(fetchOrderFlow.fulfilled, (state, action) => {
        state.loading.orderFlow = false
        state.orderFlow = action.payload
      })
      .addCase(fetchOrderFlow.rejected, (state, action) => {
        state.loading.orderFlow = false
        state.error = action.error.message || 'Failed to fetch order flow'
      })
  },
})

export const { updateTick, clearError, updateIndicators, updateOHLC, updateOptionsChain } = marketDataSlice.actions
export default marketDataSlice.reducer