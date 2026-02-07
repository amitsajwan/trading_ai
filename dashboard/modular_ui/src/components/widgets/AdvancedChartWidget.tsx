import React, { useMemo, useEffect } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { TrendingUp, TrendingDown, BarChart3 } from 'lucide-react'
import { RootState } from '../../store'
import { useWebSocket } from '../../hooks/useWebSocket'
import { formatTimestampForDisplay } from '../../utils/dateUtils'
import { fetchOHLCData } from '../../store/slices/marketDataSlice'

interface AdvancedChartWidgetProps {
  instrument?: string
  timeframe?: string
}

export const AdvancedChartWidget: React.FC<AdvancedChartWidgetProps> = ({
  instrument = 'BANKNIFTY',
  timeframe: initialTimeframe = '1min'
}) => {
  const dispatch = useDispatch()
  const [selectedTimeframe, setSelectedTimeframe] = React.useState(initialTimeframe)
  const { ohlcData, currentTick } = useSelector((state: RootState) => state.marketData)
  const { connected: wsConnected, subscribe } = useWebSocket()

  // Fetch OHLC data when component mounts or instrument/timeframe changes
  useEffect(() => {
    dispatch(fetchOHLCData({ instrument, timeframe: selectedTimeframe, limit: 200 }) as any)
  }, [dispatch, instrument, selectedTimeframe])

  // Subscribe to OHLC data for the selected timeframe
  useEffect(() => {
    if (wsConnected && subscribe) {
      subscribe([`market:ohlc:${instrument}:${selectedTimeframe}`, `market:ohlc:${instrument}`, `market:ohlc:*`])
    }
  }, [wsConnected, subscribe, instrument, selectedTimeframe])

  // Convert OHLC data to chart format using real multi-timeframe data
  const chartData = useMemo(() => {
    // Access multi-timeframe OHLC data from Redux
    const timeframeData = ohlcData?.[instrument]?.[selectedTimeframe] || []

    if (timeframeData.length > 0) {
      // Use real OHLC data for the selected timeframe
      return timeframeData.slice(-200).map(bar => ({
        timestamp: selectedTimeframe === 'daily'
          ? new Date(bar.timestamp || bar.start_at || '').toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' })
          : formatTimestampForDisplay(bar.timestamp || bar.start_at),
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        volume: bar.volume,
        price: bar.close
      }))
    }

    // Generate mock data if no real data available for this timeframe
    const mockData = []
    // Use a reasonable base price for the instrument, not currentTick (which might be for different instrument)
    const basePrice = instrument === 'BANKNIFTY' ? 59875 : instrument === 'BANKNIFTY26JANFUT' ? 59992 : 45000

    // Adjust time intervals based on selected timeframe
    let intervalMs = 60000 // 1 minute default
    switch (selectedTimeframe) {
      case '5min': intervalMs = 300000; break
      case '15min': intervalMs = 900000; break
      case '1h': intervalMs = 3600000; break
      case 'daily': intervalMs = 86400000; break
    }

    for (let i = 0; i < 50; i++) {
      const timestamp = new Date(Date.now() - (50 - i) * intervalMs)
      const open = basePrice + (Math.random() - 0.5) * 1000
      const close = open + (Math.random() - 0.5) * 500
      const high = Math.max(open, close) + Math.random() * 200
      const low = Math.min(open, close) - Math.random() * 200
      const volume = Math.floor(Math.random() * 10000) + 1000

      mockData.push({
        timestamp: selectedTimeframe === 'daily' ? timestamp.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' }) : formatTimestampForDisplay(timestamp.toISOString()),
        open: Math.round(open * 100) / 100,
        high: Math.round(high * 100) / 100,
        low: Math.round(low * 100) / 100,
        close: Math.round(close * 100) / 100,
        volume,
        price: Math.round(close * 100) / 100
      })
    }
    return mockData
  }, [ohlcData, instrument, selectedTimeframe, currentTick])

  // Calculate simple moving averages
  const dataWithMA = useMemo(() => {
    return chartData.map((item, index) => {
      const ma5 = index >= 4
        ? chartData.slice(index - 4, index + 1).reduce((sum, d) => sum + d.close, 0) / 5
        : null
      const ma10 = index >= 9
        ? chartData.slice(index - 9, index + 1).reduce((sum, d) => sum + d.close, 0) / 10
        : null

      return {
        ...item,
        ma5: ma5 ? Math.round(ma5 * 100) / 100 : null,
        ma10: ma10 ? Math.round(ma10 * 100) / 100 : null
      }
    })
  }, [chartData])

  const latestData = chartData[chartData.length - 1]
  const previousData = chartData[chartData.length - 2]

  // Calculate price change from chart data, or use current tick if no chart data
  const priceChange = latestData && previousData
    ? latestData.close - previousData.close
    : 0

  const priceChangePercent = previousData && previousData.close !== 0
    ? (priceChange / previousData.close) * 100
    : 0

  // Get current price for display (prefer chart data over tick data for consistency)
  const currentPrice = latestData?.close || currentTick?.last_price || 0

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Advanced Chart
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            {instrument} - {selectedTimeframe} timeframe
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <label htmlFor="chart-timeframe" className="text-sm text-gray-600 dark:text-gray-400">Timeframe:</label>
          <select
            id="chart-timeframe"
            value={selectedTimeframe}
            onChange={(e) => setSelectedTimeframe(e.target.value)}
            className="px-2 py-1 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded text-sm"
          >
            <option value="1min">1min</option>
            <option value="5min">5min</option>
            <option value="15min">15min</option>
            <option value="1h">1h</option>
            <option value="daily">Daily</option>
          </select>
        </div>
        <div className="flex items-center space-x-4">
          {currentPrice > 0 && (
            <div className="text-right">
              <div className="text-lg font-bold text-gray-900 dark:text-white">
                ₹{currentPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <div className={`text-sm flex items-center ${priceChange >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {priceChange >= 0 ? <TrendingUp className="w-4 h-4 mr-1" /> : <TrendingDown className="w-4 h-4 mr-1" />}
                {priceChange >= 0 ? '+' : ''}₹{Math.abs(priceChange).toFixed(2)}
                ({priceChangePercent >= 0 ? '+' : ''}{priceChangePercent.toFixed(2)}%)
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Price Chart */}
      <div className="mb-6">
        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Price Chart</h4>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={dataWithMA}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
            <XAxis
              dataKey="timestamp"
              className="text-gray-600 dark:text-gray-400"
              tick={{ fontSize: 10 }}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={['dataMin - 100', 'dataMax + 100']}
              className="text-gray-600 dark:text-gray-400"
              tick={{ fontSize: 10 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgb(31 41 55)',
                border: 'none',
                borderRadius: '8px',
                color: 'white',
                fontSize: '12px'
              }}
              formatter={(value: any, name: string) => [
                `₹${Number(value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
                name === 'price' ? 'Close' : name === 'ma5' ? 'MA5' : name === 'ma10' ? 'MA10' : name
              ]}
            />
            <Line
              type="monotone"
              dataKey="price"
              stroke="#10B981"
              strokeWidth={2}
              dot={false}
              name="Close"
            />
            <Line
              type="monotone"
              dataKey="ma5"
              stroke="#3B82F6"
              strokeWidth={1}
              strokeDasharray="5 5"
              dot={false}
              name="MA5"
            />
            <Line
              type="monotone"
              dataKey="ma10"
              stroke="#F59E0B"
              strokeWidth={1}
              strokeDasharray="5 5"
              dot={false}
              name="MA10"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Volume Chart */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Volume</h4>
        <ResponsiveContainer width="100%" height={100}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
            <XAxis
              dataKey="timestamp"
              className="text-gray-600 dark:text-gray-400"
              tick={{ fontSize: 10 }}
              interval="preserveStartEnd"
            />
            <YAxis
              className="text-gray-600 dark:text-gray-400"
              tick={{ fontSize: 10 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgb(31 41 55)',
                border: 'none',
                borderRadius: '8px',
                color: 'white',
                fontSize: '12px'
              }}
              formatter={(value: any) => [`${Number(value).toLocaleString('en-IN')}`, 'Volume']}
            />
            <Bar dataKey="volume" fill="#6366F1" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Chart Info */}
      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
        <div className="grid grid-cols-3 gap-4 text-xs text-gray-600 dark:text-gray-400">
          <div>
            <span className="font-medium">Data Points:</span> {chartData.length}
          </div>
          <div>
            <span className="font-medium">Timeframe:</span> {selectedTimeframe}
          </div>
          <div>
            <span className="font-medium">Indicators:</span> MA5, MA10
          </div>
        </div>
        <div className="mt-2 text-xs">
          {ohlcData?.[instrument]?.[selectedTimeframe]?.length > 0 ? (
            <span className="text-green-600 dark:text-green-400">
              <span className="font-medium">Status:</span> Live multi-timeframe data
            </span>
          ) : (
            <span className="text-amber-600 dark:text-amber-400">
              <span className="font-medium">Note:</span> Showing mock data - waiting for {selectedTimeframe} OHLC data
            </span>
          )}
        </div>
      </div>
    </div>
  )
}