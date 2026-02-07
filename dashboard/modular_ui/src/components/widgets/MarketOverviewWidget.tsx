import React, { useEffect, useState } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { TrendingUp, TrendingDown, Activity, DollarSign, BarChart3 } from 'lucide-react'
import { RootState } from '../../store'
import { useGetConfigQuery } from '../../api/dashboardApi'

export const MarketOverviewWidget: React.FC = () => {
  const dispatch = useDispatch()

  // Fetch config from API with error handling
  const { data: config, error: configError, isLoading: configLoading } = useGetConfigQuery()

  // Use fallback config if API fails
  const effectiveConfig = config || {
    instrument: import.meta.env.VITE_INSTRUMENT_SYMBOL || 'BANKNIFTY26JANFUT',
    env: 'DEMO'
  }

  // Use real-time data from Redux (populated by WebSocket)
  const currentTick = useSelector((state: RootState) => state.marketData.currentTick)
  const technicalIndicators = useSelector((state: RootState) => state.marketData.technicalIndicators)
  const lastUpdated = useSelector((state: RootState) => state.marketData.lastUpdated)

  // Fallback: fetch indicators directly from API if WebSocket not working
  const [apiIndicators, setApiIndicators] = useState<any>(null)
  const [apiLoading, setApiLoading] = useState(false)

  // Fetch indicators from API as fallback
  const fetchIndicatorsFromAPI = async () => {
    if (apiLoading) return
    setApiLoading(true)
    try {
      const instrumentSymbol = effectiveConfig.instrument
      console.log('🎯 Using instrument symbol:', instrumentSymbol, 'config:', config)
      const response = await fetch(`${import.meta.env.VITE_MARKET_API_URL}/api/v1/technical/indicators/${instrumentSymbol}?timeframe=1min`)
      if (response.ok) {
        const data = await response.json()
        setApiIndicators(data.indicators || {})
        console.log('🔄 Fetched indicators from API:', data.indicators)
      }
    } catch (error) {
      console.error('Failed to fetch indicators from API:', error)
    } finally {
      setApiLoading(false)
    }
  }

  // Immediate render logging
  const currentInstrument = effectiveConfig.instrument
  console.log('🎨 MarketOverviewWidget RENDERING:', {
    renderTime: new Date().toISOString(),
    hasTechnicalIndicators: !!technicalIndicators,
    instrumentSymbol: currentInstrument,
    hasBankniftyData: !!technicalIndicators?.[currentInstrument],
    technicalIndicatorsKeys: technicalIndicators ? Object.keys(technicalIndicators) : [],
    bankniftyKeys: technicalIndicators?.[currentInstrument] ? Object.keys(technicalIndicators[currentInstrument]) : [],
    reduxAtr: technicalIndicators?.[currentInstrument]?.['1min']?.atr_14,
    apiAtr: apiIndicators?.atr_14,
    usingRedux: !!(technicalIndicators?.[currentInstrument]?.['1min']),
    usingApi: !!apiIndicators,
    lastUpdated
  })

  // Prefer Redux/WebSocket indicators, fall back to API polling data
  const instrumentSymbol = currentInstrument
  const reduxData = technicalIndicators?.[instrumentSymbol]?.['1min']
  const bankniftyIndicators = reduxData || apiIndicators || {}

  // Alternative direct access for debugging (from Redux)
  const directAtr = reduxData?.atr_14

  // Debug logging - runs on every render
  console.log('🔄 MarketOverviewWidget Render:', {
    lastUpdated,
    currentTickPrice: currentTick?.last_price,
    hasApiIndicators: !!apiIndicators,
    hasReduxIndicators: !!technicalIndicators,
    reduxData: reduxData,
    apiIndicatorsKeys: apiIndicators ? Object.keys(apiIndicators) : [],
    usingRedux: !!reduxData,
    usingApi: !reduxData && !!apiIndicators,
    atr_14: bankniftyIndicators?.atr_14,
    rsi_14: bankniftyIndicators?.rsi_14,
    macd_value: bankniftyIndicators?.macd_value,
    finalSource: reduxData ? 'REDUX' : 'API'
  })

  // Fetch indicators on mount and periodically
  useEffect(() => {
    console.log('🚀 MarketOverviewWidget: Component mounted')

    // Fetch immediately
    fetchIndicatorsFromAPI()

    // Set up interval to fetch every 10 seconds
    const interval = setInterval(() => {
      fetchIndicatorsFromAPI()
    }, 10000)

    return () => clearInterval(interval)
  }, [])


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
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">{effectiveConfig.instrument}</p>
              <p className="text-xs text-gray-500">Env: {effectiveConfig.env}</p>
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
              {currentTick?.volume_source && (
                <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                  {currentTick.volume_source === 'core'
                    ? `from ${currentTick.core_instrument || 'underlying'}`
                    : currentTick.volume_source === 'synthetic'
                    ? '(estimated)'
                    : '(direct)'}
                </p>
              )}
            </div>
            <TrendingUp className="w-8 h-8 text-green-500" />
          </div>
          <div className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            {currentTick?.volume ? (
              <>
                Current Volume
                {currentTick.volume_source === 'core' && (
                  <span className="text-blue-600 dark:text-blue-400"> • Core Data</span>
                )}
              </>
            ) : (
              'Avg Volume (20)'
            )}
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
              {(() => {
                // Try multiple ways to access ATR
                const atrValue = bankniftyIndicators?.atr_14 || directAtr;
                const displayValue = atrValue ? Number(atrValue).toFixed(2) : '—';
                console.log('🎯 ATR Display:', {
                  atrValue,
                  displayValue,
                  willShow: displayValue !== '—' ? displayValue : 'DASH'
                });
                return displayValue;
              })()}
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

