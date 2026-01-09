import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import axios from 'axios'

export interface NewsArticle {
  id: string
  title: string
  content: string
  source: string
  url: string
  published_at: string
  sentiment: 'positive' | 'negative' | 'neutral'
  sentiment_score: number
  instruments: string[]
  relevance_score: number
}

interface NewsState {
  articles: NewsArticle[]
  loading: boolean
  error: string | null
  lastUpdated: string | null
  filters: {
    instrument: string | null
    sentiment: string | null
    source: string | null
  }
}

const initialState: NewsState = {
  articles: [],
  loading: false,
  error: null,
  lastUpdated: null,
  filters: {
    instrument: null,
    sentiment: null,
    source: null,
  },
}

export const fetchNewsArticles = createAsyncThunk(
  'news/fetchNewsArticles',
  async ({ instrument, limit }: { instrument?: string; limit?: number } = {}) => {
    const params = new URLSearchParams()
    if (instrument) params.append('instrument', instrument)
    if (limit) params.append('limit', limit.toString())

    const response = await axios.get(`/api/news/articles?${params}`)
    return response.data
  }
)

export const fetchNewsSentiment = createAsyncThunk(
  'news/fetchNewsSentiment',
  async (instrument: string) => {
    const response = await axios.get(`/api/news/sentiment/${instrument}`)
    return response.data
  }
)

const newsSlice = createSlice({
  name: 'news',
  initialState,
  reducers: {
    setFilters: (state, action) => {
      state.filters = { ...state.filters, ...action.payload }
    },
    clearFilters: (state) => {
      state.filters = { instrument: null, sentiment: null, source: null }
    },
    clearError: (state) => {
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchNewsArticles.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchNewsArticles.fulfilled, (state, action) => {
        state.loading = false
        state.articles = action.payload.articles || []
        state.lastUpdated = new Date().toISOString()
      })
      .addCase(fetchNewsArticles.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Failed to fetch news articles'
      })
  },
})

export const { setFilters, clearFilters, clearError } = newsSlice.actions
export default newsSlice.reducer