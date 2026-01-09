import { createApi } from '@reduxjs/toolkit/query/react'
import { axiosBaseQuery } from './axiosBaseQuery'

const BASE = import.meta.env.VITE_DASHBOARD_API_URL ?? 'http://localhost:8888'

export const dashboardApi = createApi({
  reducerPath: 'dashboardApi',
  baseQuery: axiosBaseQuery({ baseUrl: BASE }),
  tagTypes: ['AgentStatus', 'Decision', 'MarketData', 'Portfolio'],
  endpoints: (builder) => ({
    getHealth: builder.query<{ status: string }, void>({
      query: () => ({ url: '/api/health' }),
    }),

    getSystemHealth: builder.query<any, void>({
      query: () => ({ url: '/api/system-health' }),
    }),

    getLatestSignal: builder.query<any, { symbol?: string } | void>({
      query: (arg) => ({ url: `/api/latest-signal${arg?.symbol ? `?symbol=${arg.symbol}` : ''}` }),
    }),

    getMarketData: builder.query<any, { symbol: string }>({
      query: ({ symbol }) => ({ url: `/api/market-data?symbol=${encodeURIComponent(symbol)}` }),
    }),

    getRecentTrades: builder.query<any[], { limit?: number } | void>({
      query: (arg) => ({ url: `/api/recent-trades${arg?.limit ? `?limit=${arg.limit}` : ''}` }),
    }),

    getAgentStatus: builder.query<any, void>({
      query: () => ({ url: '/api/agent-status' }),
      providesTags: ['AgentStatus'],
    }),

    getPortfolio: builder.query<any, void>({
      query: () => ({ url: '/api/portfolio' }),
    }),

    getTechnicalIndicators: builder.query<any, { symbol: string }>({
      query: ({ symbol }) => ({ url: `/api/technical-indicators?symbol=${encodeURIComponent(symbol)}` }),
    }),
  }),
})

export const {
  useGetHealthQuery,
  useGetSystemHealthQuery,
  useGetLatestSignalQuery,
  useGetMarketDataQuery,
  useGetRecentTradesQuery,
  useGetAgentStatusQuery,
  useGetPortfolioQuery,
  useGetTechnicalIndicatorsQuery,
} = dashboardApi
