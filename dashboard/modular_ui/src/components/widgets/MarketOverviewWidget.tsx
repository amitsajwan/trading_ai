import React, { useMemo } from 'react'
import { useSelector, shallowEqual } from 'react-redux'
import { TrendingUp, TrendingDown, Activity, DollarSign } from 'lucide-react'
import { RootState } from '../../store'
import { useGetMarketDataQuery } from '../../api/dashboardApi'

export const MarketOverviewWidget: React.FC = React.memo(() => {
  // Use selective selectors with shallowEqual to prevent unnecessary re-renders
  const overview = useSelector((state: RootState) => state.marketData.overview, shallowEqual)
  const loading = useSelector((state: RootState) => state.marketData.loading.overview)
  // Fetch market data to determine staleness for badges
  const marketDataQuery = useGetMarketDataQuery({ symbol: overview?.instrument ?? 'BANKNIFTY' })
  const marketData = marketDataQuery.data

  if (loading.overview) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-4"></div>
          <div className="space-y-3">
            <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
          </div>
        </div>
      </div>
    )
  }

  if (!overview) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No market data available</p>
        </div>
      </div>
    )
  }

  const priceChange = overview.change_24h
  const isPositive = priceChange >= 0

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Market Overview
        </h3>
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${overview.status === 'active' ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <span className="text-sm text-gray-500 dark:text-gray-400 capitalize">
            {overview.status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Current Price */}
        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                {overview.instrument}
              </p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                ₹{overview.current_price.toLocaleString('en-IN')}
              </p>
            </div>
            <DollarSign className="w-8 h-8 text-primary-500" />
          </div>
          <div className={`flex items-center mt-2 ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
            {isPositive ? (
              <TrendingUp className="w-4 h-4 mr-1" />
            ) : (
              <TrendingDown className="w-4 h-4 mr-1" />
            )}
            <span className="text-sm font-medium">
              {isPositive ? '+' : ''}₹{Math.abs(priceChange).toFixed(2)} ({overview.change_percent_24h.toFixed(2)}%)
            </span>
          </div>
        </div>

        {/* 24h High */}
        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                24h High
              </p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                ₹{overview.high_24h.toLocaleString('en-IN')}
              </p>
            </div>
            <TrendingUp className="w-6 h-6 text-green-500" />
          </div>
        </div>

        {/* 24h Low */}
        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                24h Low
              </p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                ₹{overview.low_24h.toLocaleString('en-IN')}
              </p>
            </div>
            <TrendingDown className="w-6 h-6 text-red-500" />
          </div>
        </div>

        {/* VWAP */}
        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                <span>VWAP</span>
                <span title="Volume-weighted average price over the past 24 hours (calculated from 1-min OHLC bars)" className="ml-2 text-xs text-gray-400">ℹ️</span>
              </p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                ₹{overview.vwap.toFixed(2)}
              </p>
            </div>
            <div className="flex items-center">
              <Activity className="w-6 h-6 text-blue-500 mr-2" />
              {marketData?.is_stale ? (
                <span className="text-xs text-yellow-600 font-semibold">Stale</span>
              ) : (
                <span className="text-xs text-green-600">Live</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Volume */}
      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
            24h Volume
          </span>
          <span className="text-lg font-semibold text-gray-900 dark:text-white">
            {(overview.volume_24h / 10000000).toFixed(1)}Cr
          </span>
        </div>
      </div>

      {/* Last Updated */}
      <div className="mt-2 text-xs text-gray-500 dark:text-gray-400 text-right">
        Updated: {new Date(overview.timestamp).toLocaleTimeString()}
      </div>
    </div>
  )
})