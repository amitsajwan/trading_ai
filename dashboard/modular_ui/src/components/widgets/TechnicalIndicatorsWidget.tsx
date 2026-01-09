import React, { useState } from 'react'
import { useGetTechnicalIndicatorsQuery, useGetMarketDataQuery } from '../../api/dashboardApi'

export const TechnicalIndicatorsWidget: React.FC = () => {
  const [symbol, setSymbol] = useState('BANKNIFTY')
  const { data, isLoading, isError, isFetching } = useGetTechnicalIndicatorsQuery({ symbol })
  // Fetch market data to detect staleness (used for badge)
  const { data: marketData } = useGetMarketDataQuery({ symbol })

  const formatValue = (v: any) => {
    if (v === null || v === undefined) return '—'
    if (typeof v === 'number') {
      // Show integers without decimals, otherwise two decimals
      return Math.abs(v) >= 1000 ? v.toLocaleString('en-IN') : v.toFixed(2)
    }
    if (typeof v === 'object') return JSON.stringify(v)
    return String(v)
  }

  return (
    <section aria-labelledby="technical-indicators-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between">
        <h3 id="technical-indicators-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Technical Indicators <span title="Calculated from recent 1-minute OHLC bars (needs sufficient data)" className="ml-2 text-xs text-gray-400">ℹ️</span></h3>
        <div className="flex items-center space-x-2">
          <label htmlFor="ti-symbol" className="sr-only">Symbol</label>
          <input id="ti-symbol" aria-label="symbol" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} className="border rounded p-1 text-sm w-32" />
          {isFetching && <span className="text-xs text-gray-500">Refreshing…</span>}
        </div>
      </div>

      <div className="mt-4">
        {isLoading ? (
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2"></div>
            <div className="h-24 bg-gray-200 dark:bg-gray-700 rounded"></div>
          </div>
        ) : isError || !data ? (
          <div className="text-sm text-gray-500">Unable to load indicators for {symbol}</div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs text-gray-500">Last updated: {new Date(data.timestamp).toLocaleTimeString()}</div>
              {marketData?.is_stale ? (
                <div className="text-xs text-yellow-600 font-semibold">Stale data</div>
              ) : null}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {data.indicators && typeof data.indicators === 'object' ? (
                Object.entries(data.indicators).map(([k, v]) => (
                  <div key={k} className="bg-gray-50 dark:bg-gray-700 p-3 rounded">
                    <div className="text-xs text-gray-600 dark:text-gray-300">{k}</div>
                    <div className="text-lg font-medium text-gray-900 dark:text-white">{formatValue(v)}</div>
                  </div>
                ))
              ) : (
                // Fallback to show object keys
                Object.entries(data).map(([k, v]) => (
                  <div key={k} className="bg-gray-50 dark:bg-gray-700 p-3 rounded">
                    <div className="text-xs text-gray-600 dark:text-gray-300">{k}</div>
                    <div className="text-lg font-medium text-gray-900 dark:text-white">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</div>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>

      <div className="mt-3 text-xs text-gray-500">Symbol: {symbol}</div>
    </section>
  )
}
