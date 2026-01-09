import React, { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { TrendingUp, TrendingDown, Activity, RefreshCw } from 'lucide-react'
import { RootState } from '../../store'
import { fetchCurrentTick, updateTick, TickData } from '../../store/slices/marketDataSlice'
import { useWebSocket } from '../../hooks/useWebSocket'

interface LiveTickDataWidgetProps {
  instrument?: string
  autoRefresh?: boolean
  refreshInterval?: number
}

export const LiveTickDataWidget: React.FC<LiveTickDataWidgetProps> = ({
  instrument = 'BANKNIFTY',
  autoRefresh = true,
  refreshInterval = 2000,
}) => {
  const dispatch = useDispatch()
  const { currentTick, loading, lastUpdated } = useSelector((state: RootState) => state.marketData)
  const { connected: wsConnected } = useWebSocket()
  const [previousPrice, setPreviousPrice] = useState<number | null>(null)

  useEffect(() => {
    // Initial fetch
    dispatch(fetchCurrentTick(instrument) as any)

    // Only poll if WebSocket is not connected or autoRefresh is explicitly enabled
    // When WebSocket is connected, ticks come in real-time, so polling is less critical
    if (autoRefresh && !wsConnected) {
      const interval = setInterval(() => {
        dispatch(fetchCurrentTick(instrument) as any)
      }, refreshInterval)

      return () => clearInterval(interval)
    } else if (autoRefresh && wsConnected) {
      // Still poll occasionally as a fallback, but less frequently
      const interval = setInterval(() => {
        dispatch(fetchCurrentTick(instrument) as any)
      }, refreshInterval * 5) // Poll 5x less frequently when WebSocket is connected

      return () => clearInterval(interval)
    }
  }, [dispatch, instrument, autoRefresh, refreshInterval, wsConnected])

  useEffect(() => {
    if (currentTick?.last_price) {
      setPreviousPrice(currentTick.last_price)
    }
  }, [currentTick?.last_price])

  const handleRefresh = () => {
    dispatch(fetchCurrentTick(instrument) as any)
  }

  const priceChange = currentTick && previousPrice 
    ? currentTick.last_price - previousPrice 
    : 0
  const isPositive = priceChange >= 0

  if (loading.tick && !currentTick) {
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

  if (!currentTick) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No tick data available</p>
          <button
            onClick={handleRefresh}
            className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
          <Activity className="w-5 h-5 mr-2 text-primary-500" />
          Live Tick Data
        </h3>
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
          <span className="text-xs text-gray-500 dark:text-gray-400">Live</span>
          <button
            onClick={handleRefresh}
            disabled={loading.tick}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading.tick ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="space-y-4">
        {/* Current Price */}
        <div className="bg-gradient-to-r from-primary-50 to-primary-100 dark:from-primary-900/20 dark:to-primary-800/20 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              {currentTick.instrument || instrument}
            </span>
            {priceChange !== 0 && (
              <div className={`flex items-center text-sm font-semibold ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
                {isPositive ? (
                  <TrendingUp className="w-4 h-4 mr-1" />
                ) : (
                  <TrendingDown className="w-4 h-4 mr-1" />
                )}
                {isPositive ? '+' : ''}₹{Math.abs(priceChange).toFixed(2)}
              </div>
            )}
          </div>
          <div className="text-3xl font-bold text-gray-900 dark:text-white">
            ₹{currentTick.last_price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>

        {/* Additional Metrics */}
        <div className="grid grid-cols-2 gap-4">
          {currentTick.volume !== undefined && (
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Volume</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {(currentTick.volume / 1000000).toFixed(2)}M
              </p>
            </div>
          )}
          {currentTick.oi !== undefined && (
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">OI</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {(currentTick.oi / 1000000).toFixed(2)}M
              </p>
            </div>
          )}
        </div>

        {/* Timestamp */}
        <div className="text-xs text-gray-500 dark:text-gray-400 text-right pt-2 border-t border-gray-200 dark:border-gray-600">
          Last updated: {currentTick.timestamp ? new Date(currentTick.timestamp).toLocaleTimeString() : 'N/A'}
        </div>
      </div>
    </div>
  )
}
