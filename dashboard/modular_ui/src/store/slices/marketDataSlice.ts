import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import axios from 'axios'

export interface TickData {
  instrument: string
  last_price: number
  timestamp: string
  volume?: number
  volume_source?: 'direct' | 'core' | 'synthetic'  // Source of volume data
  core_instrument?: string  // Underlying instrument providing volume data
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
  ohlcData: Record<string, Record<string, OHLCData[]>>
  optionsChain: OptionsChain | null
  overview: MarketOverview | null
  orderFlow: any | null
  technicalIndicators: Record<string, Record<string, TechnicalIndicators>> | null
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
  ohlcData: {},
  optionsChain: null,
  overview: null,
  orderFlow: null,
  technicalIndicators: {},
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
    // Call market data API directly to bypass proxy issues
    const response = await axios.get(`http://localhost:8004/api/v1/options/chain/${instrument}`)
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
  async (symbol?: string) => {
    const url = symbol ? `/api/market-data?symbol=${encodeURIComponent(symbol)}` : '/api/market-data'
    const response = await axios.get(url)
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

export const fetchTechnicalIndicators = createAsyncThunk(
  'marketData/fetchTechnicalIndicators',
  async (instrument: string = 'BANKNIFTY') => {
    const response = await axios.get(`http://localhost:8004/api/v1/technical/indicators/${instrument}`)
    return {
      instrument: instrument.toUpperCase(),
      indicators: response.data.indicators,
      timestamp: response.data.timestamp
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
      const { instrument, timeframe = '1min', ...indicators } = action.payload
      console.log('🔄 Redux updateIndicators called:', {
        instrument,
        timeframe,
        atr_14: indicators.atr_14,
        rsi_14: indicators.rsi_14,
        macd_value: indicators.macd_value,
        allKeys: Object.keys(indicators),
        stateBefore: state.technicalIndicators?.[instrument]?.[timeframe]
      })

      if (instrument) {
        if (!state.technicalIndicators) {
          state.technicalIndicators = {}
        }
        if (!state.technicalIndicators[instrument]) {
          state.technicalIndicators[instrument] = {}
        }
        state.technicalIndicators[instrument][timeframe] = {
          ...indicators,
          timestamp: action.payload.timestamp || new Date().toISOString(),
        }
        console.log('✅ Redux state updated for', instrument, timeframe, '- ATR_14 now in state:', state.technicalIndicators?.[instrument]?.[timeframe]?.atr_14)
      }
      state.lastUpdated = new Date().toISOString()
    },
    updateOHLC: (state, action: PayloadAction<OHLCData>) => {
      // Add or update OHLC candle data organized by instrument and timeframe
      const newCandle = action.payload
      const instrument = newCandle.instrument || 'BANKNIFTY'
      const timeframe = newCandle.timeframe || '1min'

      // Initialize structure if needed
      if (!state.ohlcData[instrument]) {
        state.ohlcData[instrument] = {}
      }
      if (!state.ohlcData[instrument][timeframe]) {
        state.ohlcData[instrument][timeframe] = []
      }

      // Work with a copy of the current candles array to avoid Immer issues
      const currentCandles = [...state.ohlcData[instrument][timeframe]]

      // For OHLC data, check for exact duplicates (same timestamp AND same OHLC values)
      // This prevents overwriting candles with different data that happen to have the same timestamp
      const existingIndex = currentCandles.findIndex(
        (candle) =>
          candle.start_at === newCandle.start_at &&
          candle.open === newCandle.open &&
          candle.high === newCandle.high &&
          candle.low === newCandle.low &&
          candle.close === newCandle.close
      )

      let updatedCandles: OHLCData[]
      if (existingIndex >= 0) {
        // Update existing candle with identical data - create new array with updated item
        updatedCandles = currentCandles.map((candle, index) =>
          index === existingIndex ? newCandle : candle
        )
      } else {
        // Add new candle and sort by timestamp (Immer-compatible)
        const newCandles = [...currentCandles, newCandle]
        updatedCandles = newCandles.sort((a, b) => {
          const timeA = new Date(a.timestamp || a.start_at || '').getTime()
          const timeB = new Date(b.timestamp || b.start_at || '').getTime()
          return timeA - timeB
        })

        // Keep only last 500 candles per timeframe to prevent memory issues
        if (updatedCandles.length > 500) {
          updatedCandles = updatedCandles.slice(-500)
        }
      }

      // Assign the new array to state
      state.ohlcData[instrument][timeframe] = updatedCandles
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

        // action.payload is likely an array of OHLC data or a single object
        // We need to structure it properly for the state
        const data = action.payload

        // If it's an array of candles, we need to group them by instrument and timeframe
        if (Array.isArray(data)) {
          data.forEach((candle: OHLCData) => {
            const instrument = candle.instrument || 'BANKNIFTY26JANFUT'
            const timeframe = candle.timeframe || '1min'

            if (!state.ohlcData[instrument]) {
              state.ohlcData[instrument] = {}
            }
            if (!state.ohlcData[instrument][timeframe]) {
              state.ohlcData[instrument][timeframe] = []
            }

            // Check for duplicates and add/update
            const existingIndex = state.ohlcData[instrument][timeframe].findIndex(
              (existing) => existing.start_at === candle.start_at
            )

            if (existingIndex >= 0) {
              state.ohlcData[instrument][timeframe][existingIndex] = candle
            } else {
              state.ohlcData[instrument][timeframe].push(candle)
            }

            // Keep only last 500 candles
            if (state.ohlcData[instrument][timeframe].length > 500) {
              state.ohlcData[instrument][timeframe] = state.ohlcData[instrument][timeframe].slice(-500)
            }
          })
        } else if (data && typeof data === 'object') {
          // Single candle object - this shouldn't normally happen for fetchOHLCData
          const instrument = data.instrument || 'BANKNIFTY26JANFUT'
          const timeframe = data.timeframe || '1min'

          if (!state.ohlcData[instrument]) {
            state.ohlcData[instrument] = {}
          }
          if (!state.ohlcData[instrument][timeframe]) {
            state.ohlcData[instrument][timeframe] = []
          }

          state.ohlcData[instrument][timeframe].push(data)

          // Keep only last 500 candles
          if (state.ohlcData[instrument][timeframe].length > 500) {
            state.ohlcData[instrument][timeframe] = state.ohlcData[instrument][timeframe].slice(-500)
          }
        }

        state.lastUpdated = new Date().toISOString()
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

    // Technical Indicators
    builder
      .addCase(fetchTechnicalIndicators.pending, (state) => {
        state.loading.overview = true
        console.log('📊 Fetching technical indicators...')
      })
      .addCase(fetchTechnicalIndicators.fulfilled, (state, action) => {
        state.loading.overview = false
        // Update the technical indicators in Redux state
        const { instrument, indicators, timestamp } = action.payload

        console.log('📊 Technical indicators received:', {
          instrument,
          timestamp,
          atr_14: indicators?.atr_14,
          atr_20: indicators?.atr_20,
          rsi_14: indicators?.rsi_14,
          macd_value: indicators?.macd_value,
          adx_14: indicators?.adx_14,
          total_indicators: Object.keys(indicators || {}).length,
          raw_indicators_sample: Object.keys(indicators || {}).slice(0, 10)
        })

        // Extra debug for ATR specifically
        console.log('🔍 ATR Debug:', {
          atr_14_exists: 'atr_14' in (indicators || {}),
          atr_14_value: indicators?.atr_14,
          atr_14_type: typeof indicators?.atr_14,
          indicators_has_atr: indicators && 'atr_14' in indicators
        })

        if (!state.technicalIndicators) {
          state.technicalIndicators = {}
        }
        if (!state.technicalIndicators[instrument]) {
          state.technicalIndicators[instrument] = {}
        }
        state.technicalIndicators[instrument]['1min'] = {
          ...indicators,
          timestamp,
          instrument
        }

        console.log('📊 Updated Redux state with indicators for', instrument)
      })
      .addCase(fetchTechnicalIndicators.rejected, (state, action) => {
        state.loading.overview = false
        state.error = action.error.message || 'Failed to fetch technical indicators'
        console.error('❌ Failed to fetch technical indicators:', action.error)
      })
  },
})

export const { updateTick, clearError, updateIndicators, updateOHLC, updateOptionsChain } = marketDataSlice.actions
export default marketDataSlice.reducer