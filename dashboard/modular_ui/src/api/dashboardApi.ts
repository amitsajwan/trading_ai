import { createApi } from '@reduxjs/toolkit/query/react'
import { axiosBaseQuery } from './axiosBaseQuery'
import type {
  SystemHealth,
  TradingSignal,
  MarketData,
  AgentStatusResponse,
  Position,
  RecentTradesResponse,
  PortfolioHeatSummary,
  HeatUtilization,
  KellyCalculation,
  ApprovalResult,
  ApprovalHistory,
  ApprovalStats
} from './types'

const BASE = import.meta.env.VITE_DASHBOARD_API_URL ?? ''

export const dashboardApi = createApi({
  reducerPath: 'dashboardApi',
  baseQuery: axiosBaseQuery({ baseUrl: BASE }),
  tagTypes: ['AgentStatus', 'Decision', 'MarketData', 'Portfolio', 'Risk', 'Approval'],
  endpoints: (builder) => ({
    getHealth: builder.query<{ status: string }, void>({
      query: () => ({ url: '/api/health' }),
    }),

    getConfig: builder.query<{ instrument: string; env: string }, void>({
      query: () => ({ url: '/api/config' }),
    }),

    getSystemHealth: builder.query<SystemHealth, void>({
      query: () => ({ url: '/api/system-health' }),
    }),

    getLatestSignal: builder.query<{ signal: TradingSignal }, { symbol?: string } | void>({
      query: (arg) => ({ url: `/api/latest-signal${arg?.symbol ? `?symbol=${arg.symbol}` : ''}` }),
    }),

    getMarketData: builder.query<MarketData, { symbol: string }>({
      query: ({ symbol }) => ({ url: `/api/market-data?symbol=${encodeURIComponent(symbol)}` }),
    }),

    getRecentTrades: builder.query<RecentTradesResponse['trades'], { limit?: number } | void>({
      query: (arg) => ({ url: `/api/recent-trades${arg?.limit ? `?limit=${arg.limit}` : ''}` }),
      transformResponse: (response: RecentTradesResponse) => response.trades
    }),

    getAgentStatus: builder.query<AgentStatusResponse, void>({
      query: () => ({ url: '/api/agent-status' }),
      providesTags: ['AgentStatus'],
    }),

    getPortfolio: builder.query<{ positions: Position[] }, void>({
      query: () => ({ url: '/api/portfolio' }),
    }),

    getTechnicalIndicators: builder.query<any, { symbol: string }>({
      query: ({ symbol }) => ({ url: `http://localhost:8004/api/v1/technical/indicators/${encodeURIComponent(symbol)}` }),
    }),

    // Risk Management API (Layer 8)
    getPortfolioHeatSummary: builder.query<PortfolioHeatSummary, void>({
      query: () => ({ url: '/api/risk/portfolio/summary' }),
      providesTags: ['Risk'],
    }),

    getHeatUtilization: builder.query<HeatUtilization, void>({
      query: () => ({ url: '/api/risk/portfolio/heat-utilization' }),
      providesTags: ['Risk'],
    }),

    calculateKelly: builder.mutation<KellyCalculation, {
      account_balance: number
      max_loss_per_unit: number
      win_probability?: number
      risk_reward_ratio?: number
      trade_history?: Array<Record<string, any>>
      strategy_type?: string
    }>({
      query: (body) => ({
        url: '/api/risk/kelly/calculate',
        method: 'POST',
        data: body,
      }),
    }),

    getApprovalHistory: builder.query<ApprovalHistory, { limit?: number } | void>({
      query: (arg) => ({
        url: `/api/risk/approval/history${arg?.limit ? `?limit=${arg.limit}` : ''}`,
      }),
      providesTags: ['Approval'],
    }),

    getApprovalStats: builder.query<ApprovalStats, void>({
      query: () => ({ url: '/api/risk/approval/stats' }),
      providesTags: ['Approval'],
    }),

    reviewAndApprove: builder.mutation<ApprovalResult, {
      trading_decision: Record<string, any>
      current_positions: Array<Record<string, any>>
      proposed_quantity?: number
      max_loss_per_unit?: number
      trade_history?: Array<Record<string, any>>
    }>({
      query: (body) => ({
        url: '/api/risk/approval/review',
        method: 'POST',
        data: body,
      }),
      invalidatesTags: ['Approval', 'Risk'],
    }),
  }),
})

export const {
  useGetHealthQuery,
  useGetConfigQuery,
  useGetSystemHealthQuery,
  useGetLatestSignalQuery,
  useGetMarketDataQuery,
  useGetRecentTradesQuery,
  useGetAgentStatusQuery,
  useGetPortfolioQuery,
  useGetTechnicalIndicatorsQuery,
  // Risk Management hooks (Layer 8)
  useGetPortfolioHeatSummaryQuery,
  useGetHeatUtilizationQuery,
  useCalculateKellyMutation,
  useGetApprovalHistoryQuery,
  useGetApprovalStatsQuery,
  useReviewAndApproveMutation,
} = dashboardApi
