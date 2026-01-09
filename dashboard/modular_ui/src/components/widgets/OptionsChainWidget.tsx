import React, { useEffect, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { RefreshCw, TrendingUp, TrendingDown, AlertCircle } from 'lucide-react'
import { RootState } from '../../store'
import { fetchOptionsChain, OptionsChain } from '../../store/slices/marketDataSlice'

interface OptionsChainWidgetProps {
  instrument?: string
  autoRefresh?: boolean
  refreshInterval?: number
  maxVisibleStrikes?: number
}

export const OptionsChainWidget: React.FC<OptionsChainWidgetProps> = ({
  instrument = 'BANKNIFTY',
  autoRefresh = true,
  refreshInterval = 5000,
  maxVisibleStrikes = 10,
}) => {
  const dispatch = useDispatch()
  const { optionsChain, loading } = useSelector((state: RootState) => state.marketData)

  useEffect(() => {
    dispatch(fetchOptionsChain(instrument) as any)

    if (autoRefresh) {
      const interval = setInterval(() => {
        dispatch(fetchOptionsChain(instrument) as any)
      }, refreshInterval)

      return () => clearInterval(interval)
    }
  }, [dispatch, instrument, autoRefresh, refreshInterval])

  const handleRefresh = () => {
    dispatch(fetchOptionsChain(instrument) as any)
  }

  // Calculate ATM strikes (closest to futures price)
  const { atmIndex, visibleStrikes } = useMemo(() => {
    if (!optionsChain) {
      return { atmIndex: -1, visibleStrikes: [] }
    }
    
    // Handle both chain and strikes fields
    const chainData = optionsChain.chain || optionsChain.strikes || []
    if (!chainData || chainData.length === 0) {
      return { atmIndex: -1, visibleStrikes: [] }
    }

    // Get futures price - try to find from first strike if not available, or use a reasonable default
    const futuresPrice = optionsChain?.futures_price || (chainData.length > 0 
      ? chainData[Math.floor(chainData.length / 2)].strike 
      : 45000)
    const chain = [...chainData].sort((a, b) => a.strike - b.strike)
    
    // Find ATM strike
    let atmIndex = 0
    let minDiff = Math.abs(chain[0].strike - futuresPrice)
    for (let i = 1; i < chain.length; i++) {
      const diff = Math.abs(chain[i].strike - futuresPrice)
      if (diff < minDiff) {
        minDiff = diff
        atmIndex = i
      }
    }

    // Get strikes around ATM
    const start = Math.max(0, atmIndex - Math.floor(maxVisibleStrikes / 2))
    const end = Math.min(chain.length, start + maxVisibleStrikes)
    const visible = chain.slice(start, end)

    return { atmIndex: atmIndex - start, visibleStrikes: visible }
  }, [optionsChain, maxVisibleStrikes])

  if (loading.options && !optionsChain) {
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

  const chainData = optionsChain?.chain || optionsChain?.strikes || []
  if (!optionsChain || (optionsChain.available === false) || chainData.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Options chain data not available</p>
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
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Options Chain
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            {optionsChain.expiry ? `Expiry: ${new Date(optionsChain.expiry).toLocaleDateString()}` : ''}
            {optionsChain.futures_price != null && (
              <span className="ml-2">Futures: ₹{optionsChain.futures_price.toFixed(2)}</span>
            )}
            {optionsChain.instrument && (
              <span className="ml-2">({optionsChain.instrument})</span>
            )}
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={loading.options}
          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${loading.options ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* PCR and Max Pain */}
      {(optionsChain.pcr != null || optionsChain.max_pain != null) && (
        <div className="grid grid-cols-2 gap-4 mb-4">
          {optionsChain.pcr != null && (
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Put/Call Ratio</p>
              <p className="text-lg font-semibold text-blue-600 dark:text-blue-400">
                {optionsChain.pcr.toFixed(2)}
              </p>
            </div>
          )}
          {optionsChain.max_pain != null && (
            <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3">
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Max Pain</p>
              <p className="text-lg font-semibold text-purple-600 dark:text-purple-400">
                ₹{optionsChain.max_pain.toLocaleString('en-IN')}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Options Chain Table */}
      {visibleStrikes.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-600">
                <th className="text-left py-2 px-2 font-semibold text-gray-700 dark:text-gray-300">CE</th>
                <th className="text-left py-2 px-2 font-semibold text-gray-700 dark:text-gray-300">Strike</th>
                <th className="text-left py-2 px-2 font-semibold text-gray-700 dark:text-gray-300">PE</th>
              </tr>
            </thead>
            <tbody>
              {visibleStrikes.map((strike, index) => {
                const isATM = index === atmIndex
                const futuresPrice = optionsChain?.futures_price
                const ceITM = strike.ce_ltp && futuresPrice && futuresPrice > strike.strike
                const peITM = strike.pe_ltp && futuresPrice && futuresPrice < strike.strike

                return (
                  <tr
                    key={strike.strike}
                    className={`border-b border-gray-100 dark:border-gray-700 ${
                      isATM ? 'bg-primary-50 dark:bg-primary-900/20' : ''
                    }`}
                  >
                    {/* Call Option */}
                    <td className="py-2 px-2">
                      {strike.ce_ltp != null ? (
                        <div>
                          <div className="font-semibold text-gray-900 dark:text-white">
                            {strike.ce_ltp.toFixed(2)}
                          </div>
                          {strike.ce_oi != null && (
                            <div className="text-xs text-gray-500 dark:text-gray-400">
                              OI: {(strike.ce_oi / 1000).toFixed(0)}K
                            </div>
                          )}
                          {strike.ce_iv != null && (
                            <div className="text-xs text-gray-500 dark:text-gray-400">
                              IV: {strike.ce_iv.toFixed(2)}%
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>

                    {/* Strike Price */}
                    <td className="py-2 px-2 text-center">
                      <div className={`font-bold ${isATM ? 'text-primary-600 dark:text-primary-400' : 'text-gray-900 dark:text-white'}`}>
                        {strike.strike}
                        {isATM && <span className="ml-1 text-xs">(ATM)</span>}
                      </div>
                    </td>

                    {/* Put Option */}
                    <td className="py-2 px-2">
                      {strike.pe_ltp != null ? (
                        <div>
                          <div className="font-semibold text-gray-900 dark:text-white">
                            {strike.pe_ltp.toFixed(2)}
                          </div>
                          {strike.pe_oi != null && (
                            <div className="text-xs text-gray-500 dark:text-gray-400">
                              OI: {(strike.pe_oi / 1000).toFixed(0)}K
                            </div>
                          )}
                          {strike.pe_iv != null && (
                            <div className="text-xs text-gray-500 dark:text-gray-400">
                              IV: {strike.pe_iv.toFixed(2)}%
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center text-gray-500 dark:text-gray-400 py-8">
          No strike data available
        </div>
      )}
    </div>
  )
}
