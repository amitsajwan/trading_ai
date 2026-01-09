import React, { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { RefreshCw, Calendar, BarChart3, AlertCircle, TrendingUp, TrendingDown } from 'lucide-react'
import { RootState } from '../../store'
import { fetchOHLCData, OHLCData } from '../../store/slices/marketDataSlice'

interface HistoricalDataWidgetProps {
  instrument?: string
  defaultTimeframe?: string
  defaultLimit?: number
  autoRefresh?: boolean
  refreshInterval?: number
}

const TIMEFRAMES = [
  { value: 'minute', label: '1 Min' },
  { value: '3minute', label: '3 Min' },
  { value: '5minute', label: '5 Min' },
  { value: '15minute', label: '15 Min' },
  { value: '30minute', label: '30 Min' },
  { value: 'hour', label: '1 Hour' },
  { value: 'day', label: '1 Day' },
]

export const HistoricalDataWidget: React.FC<HistoricalDataWidgetProps> = ({
  instrument = 'BANKNIFTY',
  defaultTimeframe = '15minute',
  defaultLimit = 20,
  autoRefresh = true,
  refreshInterval = 60000, // 1 minute for historical data
}) => {
  const dispatch = useDispatch()
  const { ohlcData, loading } = useSelector((state: RootState) => state.marketData)
  const [timeframe, setTimeframe] = useState(defaultTimeframe)
  const [limit, setLimit] = useState(defaultLimit)

  useEffect(() => {
    dispatch(fetchOHLCData({ instrument, timeframe, limit }) as any)

    if (autoRefresh) {
      const interval = setInterval(() => {
        dispatch(fetchOHLCData({ instrument, timeframe, limit }) as any)
      }, refreshInterval)

      return () => clearInterval(interval)
    }
  }, [dispatch, instrument, timeframe, limit, autoRefresh, refreshInterval])

  const handleRefresh = () => {
    dispatch(fetchOHLCData({ instrument, timeframe, limit }) as any)
  }

  const handleTimeframeChange = (newTimeframe: string) => {
    setTimeframe(newTimeframe)
  }

  const formatTimestamp = (timestamp: string | undefined) => {
    if (!timestamp) return 'N/A'
    try {
      const date = new Date(timestamp)
      if (timeframe === 'day') {
        return date.toLocaleDateString()
      }
      return date.toLocaleString('en-IN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return timestamp
    }
  }

  // Get timestamp from either timestamp or start_at field
  const getTimestamp = (bar: OHLCData & { start_at?: string }) => {
    return bar.timestamp || bar.start_at || ''
  }

  const calculateChange = (data: OHLCData[]) => {
    if (data.length < 2) return { value: 0, percent: 0, isPositive: true }
    const first = data[data.length - 1]
    const last = data[0]
    if (!first || !last || !first.open || !last.close) {
      return { value: 0, percent: 0, isPositive: true }
    }
    const change = last.close - first.open
    const percent = first.open > 0 ? (change / first.open) * 100 : 0
    return {
      value: change,
      percent,
      isPositive: change >= 0,
    }
  }

  if (loading.ohlc && (!ohlcData || ohlcData.length === 0)) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-4"></div>
          <div className="space-y-3">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  if (!ohlcData || ohlcData.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <BarChart3 className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No historical data available</p>
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

  // Ensure data is sorted by timestamp (newest first)
  // Handle both timestamp and start_at fields
  const sortedData = [...ohlcData].sort((a, b) => {
    const aTime = getTimestamp(a as any)
    const bTime = getTimestamp(b as any)
    return new Date(bTime).getTime() - new Date(aTime).getTime()
  })

  const change = calculateChange(sortedData)
  const latest = sortedData[0]

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
            <BarChart3 className="w-5 h-5 mr-2 text-primary-500" />
            Historical Data
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            OHLC data and technical indicators
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={loading.ohlc}
          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${loading.ohlc ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Timeframe Selector */}
      <div className="mb-4">
        <div className="flex items-center space-x-2 mb-2">
          <Calendar className="w-4 h-4 text-gray-500" />
          <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Timeframe:</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf.value}
              onClick={() => handleTimeframeChange(tf.value)}
              className={`px-3 py-1 text-xs rounded-lg transition-colors ${
                timeframe === tf.value
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {tf.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Stats */}
      {latest && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
            <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Open</p>
            <p className="text-sm font-semibold text-gray-900 dark:text-white">
              ₹{latest.open.toFixed(2)}
            </p>
          </div>
          <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
            <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">High</p>
            <p className="text-sm font-semibold text-green-600 dark:text-green-400">
              ₹{latest.high.toFixed(2)}
            </p>
          </div>
          <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
            <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Low</p>
            <p className="text-sm font-semibold text-red-600 dark:text-red-400">
              ₹{latest.low.toFixed(2)}
            </p>
          </div>
          <div className="bg-primary-50 dark:bg-primary-900/20 rounded-lg p-3">
            <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Close</p>
            <p className="text-sm font-semibold text-primary-600 dark:text-primary-400">
              ₹{latest.close.toFixed(2)}
            </p>
          </div>
        </div>
      )}

      {/* Period Change */}
      {sortedData.length >= 2 && (
        <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-600 dark:text-gray-400">
              Period Change ({sortedData.length} bars)
            </span>
            <div className={`flex items-center ${change.isPositive ? 'text-green-600' : 'text-red-600'}`}>
              {change.isPositive ? (
                <TrendingUp className="w-4 h-4 mr-1" />
              ) : (
                <TrendingDown className="w-4 h-4 mr-1" />
              )}
              <span className="text-sm font-semibold">
                {change.isPositive ? '+' : ''}₹{change.value.toFixed(2)} ({change.percent.toFixed(2)}%)
              </span>
            </div>
          </div>
        </div>
      )}

      {/* OHLC Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-600">
              <th className="text-left py-2 px-2 font-semibold text-gray-700 dark:text-gray-300">Time</th>
              <th className="text-right py-2 px-2 font-semibold text-gray-700 dark:text-gray-300">Open</th>
              <th className="text-right py-2 px-2 font-semibold text-gray-700 dark:text-gray-300">High</th>
              <th className="text-right py-2 px-2 font-semibold text-gray-700 dark:text-gray-300">Low</th>
              <th className="text-right py-2 px-2 font-semibold text-gray-700 dark:text-gray-300">Close</th>
              <th className="text-right py-2 px-2 font-semibold text-gray-700 dark:text-gray-300">Volume</th>
            </tr>
          </thead>
          <tbody>
            {sortedData.slice(0, limit).map((bar, index) => {
              const isPositive = bar.close >= bar.open
              const timestamp = getTimestamp(bar as any)
              return (
                <tr
                  key={`${timestamp}-${index}`}
                  className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                >
                  <td className="py-2 px-2 text-gray-600 dark:text-gray-400 text-xs">
                    {formatTimestamp(timestamp)}
                  </td>
                  <td className="py-2 px-2 text-right text-gray-900 dark:text-white">
                    {bar.open.toFixed(2)}
                  </td>
                  <td className="py-2 px-2 text-right text-green-600 dark:text-green-400">
                    {bar.high.toFixed(2)}
                  </td>
                  <td className="py-2 px-2 text-right text-red-600 dark:text-red-400">
                    {bar.low.toFixed(2)}
                  </td>
                  <td className={`py-2 px-2 text-right font-semibold ${
                    isPositive ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                  }`}>
                    {bar.close.toFixed(2)}
                  </td>
                  <td className="py-2 px-2 text-right text-gray-600 dark:text-gray-400 text-xs">
                    {(bar.volume / 1000000).toFixed(2)}M
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {sortedData.length > limit && (
        <div className="mt-3 text-center">
          <button
            onClick={() => setLimit(limit + 10)}
            className="text-xs text-primary-600 dark:text-primary-400 hover:underline"
          >
            Show more ({sortedData.length - limit} more bars)
          </button>
        </div>
      )}
    </div>
  )
}
