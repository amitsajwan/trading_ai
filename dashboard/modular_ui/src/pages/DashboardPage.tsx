import React, { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { RootState } from '../store'
import {
  fetchCurrentTick,
  fetchMarketOverview,
  fetchOptionsChain
} from '../store/slices/marketDataSlice'
import {
  fetchLatestDecision,
  fetchPortfolio,
  fetchAgentStatuses,
  fetchOptionsStrategy
} from '../store/slices/tradingSlice'
import { MarketOverviewWidget } from '../components/widgets/MarketOverviewWidget'
import { CurrentSignalWidget } from '../components/widgets/CurrentSignalWidget'
import { OptionsStrategyWidget } from '../components/widgets/OptionsStrategyWidget'
import { PortfolioWidget } from '../components/widgets/PortfolioWidget'
import { RecentTradesWidget } from '../components/widgets/RecentTradesWidget'
import { TechnicalIndicatorsWidget } from '../components/widgets/TechnicalIndicatorsWidget'
import { AgentStatusWidget } from '../components/widgets/AgentStatusWidget'
import { WidgetShell } from '../components/widgets/WidgetShell'

export const DashboardPage: React.FC = () => {
  const dispatch = useDispatch()
  const { dashboardLayout } = useSelector((state: RootState) => state.ui)

  // Initial data loading
  useEffect(() => {
    // Market data
    dispatch(fetchCurrentTick())
    dispatch(fetchMarketOverview())
    dispatch(fetchOptionsChain())

    // Trading data
    dispatch(fetchLatestDecision())
    dispatch(fetchPortfolio())
    dispatch(fetchAgentStatuses())
    dispatch(fetchOptionsStrategy())
  }, [dispatch])

  // Auto-refresh
  useEffect(() => {
    if (!dashboardLayout.autoRefresh) return

    const interval = setInterval(() => {
      dispatch(fetchCurrentTick())
      dispatch(fetchMarketOverview()) // Refresh overview periodically to get fresh VWAP, volume, etc.
      dispatch(fetchLatestDecision())
      dispatch(fetchPortfolio())
      dispatch(fetchOptionsStrategy())
    }, dashboardLayout.refreshInterval * 1000)

    return () => clearInterval(interval)
  }, [dispatch, dashboardLayout.autoRefresh, dashboardLayout.refreshInterval])

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Trading Dashboard
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Real-time monitoring of your AI trading system
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="px-3 py-1 bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 rounded-full text-sm font-medium">
            Live Data Active
          </div>
        </div>
      </div>

      {/* Dashboard Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {/* Market Overview */}
        <div className="xl:col-span-2">
          <WidgetShell id="market-overview" title="Market Overview">
            <MarketOverviewWidget />
          </WidgetShell>
        </div>

        {/* Current Signal */}
        <div className="xl:col-span-1">
          <WidgetShell id="current-signal" title="Current Signal">
            <CurrentSignalWidget />
          </WidgetShell>
        </div>

        {/* Options Strategy */}
        <div className="xl:col-span-2">
          <WidgetShell id="options-strategy" title="Options Strategy">
            <OptionsStrategyWidget />
          </WidgetShell>
        </div>

        {/* Portfolio */}
        <div className="xl:col-span-1">
          <WidgetShell id="portfolio" title="Portfolio">
            <PortfolioWidget />
          </WidgetShell>
        </div>

        {/* Recent Trades */}
        <div className="xl:col-span-2">
          <WidgetShell id="recent-trades" title="Recent Trades">
            <RecentTradesWidget />
          </WidgetShell>
        </div>

        {/* Technical Indicators */}
        <div className="xl:col-span-3">
          <WidgetShell id="technical-indicators" title="Technical Indicators">
            <TechnicalIndicatorsWidget />
          </WidgetShell>
        </div>

        {/* Agent Status */}
        <div className="xl:col-span-3">
          <WidgetShell id="agent-status" title="Agent Status">
            <AgentStatusWidget />
          </WidgetShell>
        </div>
      </div>
    </div>
  )
}