import React from 'react'
import { useSelector } from 'react-redux'
import { TrendingUp, TrendingDown, Activity, DollarSign, BarChart3 } from 'lucide-react'
import { RootState } from '../../store'

export const MarketOverviewWidget: React.FC = () => {
  // Use real-time data from Redux (populated by WebSocket)
  const currentTick = useSelector((state: RootState) => state.marketData.currentTick)
  const technicalIndicators = useSelector((state: RootState) => state.marketData.technicalIndicators)

  // Get the latest timeframe data for BANKNIFTY (usually '1min')
  const bankniftyData = technicalIndicators?.BANKNIFTY
  const latestTimeframe = bankniftyData ? Object.keys(bankniftyData)[0] : null
  const bankniftyIndicators = latestTimeframe ? bankniftyData[latestTimeframe] : {}


  return (
    <div className="space-y-6">
      {/* Market Status */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Market Overview</h3>
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
          <span className="text-sm text-green-600 dark:text-green-400">Live</span>
        </div>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">BANKNIFTY</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {currentTick?.last_price?.toLocaleString('en-IN') || '—'}
              </p>
            </div>
            <Activity className="w-8 h-8 text-blue-500" />
          </div>
          <div className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Live Price
          </div>
        </div>

        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">RSI (14)</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {bankniftyIndicators.rsi_14?.toFixed(1) || '—'}
              </p>
            </div>
            <BarChart3 className="w-8 h-8 text-purple-500" />
          </div>
          <div className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Momentum
          </div>
        </div>

        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Volume</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {(currentTick?.volume || bankniftyIndicators.volume_sma_20 || 0).toLocaleString('en-IN')}
              </p>
            </div>
            <TrendingUp className="w-8 h-8 text-green-500" />
          </div>
          <div className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            {currentTick?.volume ? 'Current Volume' : 'Avg Volume (20)'}
          </div>
        </div>
      </div>

      {/* Market Indicators */}
      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Technical Signals</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="text-center">
            <div className={`text-lg font-bold ${
              (bankniftyIndicators.rsi_14 || 0) > 70 ? 'text-red-600' :
              (bankniftyIndicators.rsi_14 || 0) < 30 ? 'text-green-600' :
              'text-gray-900 dark:text-white'
            }`}>
              {bankniftyIndicators.rsi_14?.toFixed(1) || '—'}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">RSI</div>
          </div>

          <div className="text-center">
            <div className="text-lg font-bold text-gray-900 dark:text-white">
              {bankniftyIndicators.macd_value?.toFixed(2) || '—'}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">MACD</div>
          </div>

          <div className="text-center">
            <div className={`text-lg font-bold ${
              (bankniftyIndicators.adx_14 || 0) > 25 ? 'text-green-600' : 'text-gray-900 dark:text-white'
            }`}>
              {bankniftyIndicators.adx_14?.toFixed(1) || '—'}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">ADX</div>
          </div>

          <div className="text-center">
            <div className="text-lg font-bold text-gray-900 dark:text-white">
              {bankniftyIndicators.atr_14?.toFixed(2) || '—'}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">ATR</div>
          </div>
        </div>
      </div>

      {/* Market Status Summary */}
      <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-100">Market Status</h4>
            <p className="text-xs text-blue-700 dark:text-blue-300 mt-1">
              Real-time data streaming active
            </p>
          </div>
          <div className="text-right">
            <div className="text-lg font-bold text-blue-900 dark:text-blue-100">
              {currentTick ? 'Connected' : 'Waiting'}
            </div>
            <div className="text-xs text-blue-600 dark:text-blue-400">
              WebSocket Live
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

