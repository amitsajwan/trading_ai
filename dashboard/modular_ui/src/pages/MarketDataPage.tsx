import React, { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Activity, AlertCircle, CheckCircle2 } from 'lucide-react'
import { RootState } from '../store'
import { fetchMarketOverview, clearError } from '../store/slices/marketDataSlice'
import { LiveTickDataWidget } from '../components/widgets/LiveTickDataWidget'
import { OptionsChainWidget } from '../components/widgets/OptionsChainWidget'
import { OrderFlowWidget } from '../components/widgets/OrderFlowWidget'
import { HistoricalDataWidget } from '../components/widgets/HistoricalDataWidget'

const INSTRUMENTS = ['BANKNIFTY', 'NIFTY', 'SENSEX', 'FINNIFTY']

export const MarketDataPage: React.FC = () => {
  const dispatch = useDispatch()
  const { overview, error, lastUpdated } = useSelector((state: RootState) => state.marketData)
  const [selectedInstrument, setSelectedInstrument] = useState<string>('BANKNIFTY')

  useEffect(() => {
    // Fetch market overview on mount
    dispatch(fetchMarketOverview() as any)
  }, [dispatch])

  useEffect(() => {
    // Clear errors after 5 seconds
    if (error) {
      const timer = setTimeout(() => {
        dispatch(clearError())
      }, 5000)
      return () => clearTimeout(timer)
    }
  }, [error, dispatch])

  const handleInstrumentChange = (instrument: string) => {
    setSelectedInstrument(instrument)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Market Data
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Real-time market data and analytics
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Instrument Selector */}
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Instrument:
            </label>
            <select
              value={selectedInstrument}
              onChange={(e) => handleInstrumentChange(e.target.value)}
              className="px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {INSTRUMENTS.map((inst) => (
                <option key={inst} value={inst}>
                  {inst}
                </option>
              ))}
            </select>
          </div>

          {/* Status Indicator */}
          <div className="flex items-center gap-2">
            {overview?.status === 'active' ? (
              <>
                <CheckCircle2 className="w-4 h-4 text-green-500" />
                <span className="text-sm text-gray-600 dark:text-gray-400">Market Open</span>
              </>
            ) : (
              <>
                <Activity className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-600 dark:text-gray-400">Market Closed</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-red-800 dark:text-red-300">Error</p>
            <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
          </div>
          <button
            onClick={() => dispatch(clearError())}
            className="text-sm text-red-700 dark:text-red-400 hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Market Overview Summary */}
      {overview && (
        <div className="bg-gradient-to-r from-primary-50 to-primary-100 dark:from-primary-900/20 dark:to-primary-800/20 rounded-lg p-4 border border-primary-200 dark:border-primary-800">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Current Price</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                ₹{overview.current_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">24h Change</p>
              <p className={`text-xl font-bold ${overview.change_24h >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {overview.change_24h >= 0 ? '+' : ''}₹{overview.change_24h.toFixed(2)} ({overview.change_percent_24h.toFixed(2)}%)
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">24h Volume</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                {(overview.volume_24h / 10000000).toFixed(1)}Cr
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">VWAP</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                ₹{overview.vwap.toFixed(2)}
              </p>
            </div>
          </div>
          {lastUpdated && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-3 text-right">
              Last updated: {new Date(lastUpdated).toLocaleTimeString()}
            </p>
          )}
        </div>
      )}

      {/* Main Widgets Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Live Tick Data */}
        <LiveTickDataWidget 
          instrument={selectedInstrument}
          autoRefresh={true}
          refreshInterval={2000}
        />

        {/* Options Chain */}
        <OptionsChainWidget 
          instrument={selectedInstrument}
          autoRefresh={true}
          refreshInterval={5000}
          maxVisibleStrikes={10}
        />

        {/* Order Flow */}
        <OrderFlowWidget 
          autoRefresh={true}
          refreshInterval={3000}
        />

        {/* Historical Data */}
        <HistoricalDataWidget 
          instrument={selectedInstrument}
          defaultTimeframe="15minute"
          defaultLimit={20}
          autoRefresh={true}
          refreshInterval={60000}
        />
      </div>
    </div>
  )
}