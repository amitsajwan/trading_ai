import React, { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { RefreshCw, TrendingUp, TrendingDown, X, AlertCircle } from 'lucide-react'
import { RootState } from '../../store'
import { fetchPortfolio, clearError } from '../../store/slices/tradingSlice'
import axios from 'axios'

export const ActivePositionsWidget: React.FC = () => {
  const dispatch = useDispatch()
  const { portfolio, loading, error } = useSelector((state: RootState) => state.trading)
  const [positions, setPositions] = React.useState<any[]>([])

  useEffect(() => {
    // Fetch positions from trading API
    const fetchPositions = async () => {
      try {
        const response = await axios.get('/api/trading/positions')
        // User API returns a list directly, or wrapped in {positions: []} from dashboard proxy
        const positionsData = Array.isArray(response.data) 
          ? response.data 
          : (response.data?.positions || [])
        setPositions(positionsData)
      } catch (err) {
        console.error('Failed to fetch positions:', err)
      }
    }

    fetchPositions()
    dispatch(fetchPortfolio() as any)

    // Auto-refresh every 5 seconds
    const interval = setInterval(() => {
      fetchPositions()
      dispatch(fetchPortfolio() as any)
    }, 5000)

    return () => clearInterval(interval)
  }, [dispatch])

  const handleClosePosition = async (positionId: string, instrument: string) => {
    if (!confirm(`Close position in ${instrument}?`)) return

    try {
      await axios.post(`/api/trading/close/${positionId}`)
      // Refresh positions
      const response = await axios.get('/api/trading/positions')
      const positionsData = Array.isArray(response.data) 
        ? response.data 
        : (response.data?.positions || [])
      setPositions(positionsData)
    } catch (err: any) {
      alert(`Failed to close position: ${err.response?.data?.error || err.message}`)
    }
  }

  const handleRefresh = () => {
    axios.get('/api/trading/positions').then((response) => {
      const positionsData = Array.isArray(response.data) 
        ? response.data 
        : (response.data?.positions || [])
      setPositions(positionsData)
    })
    dispatch(fetchPortfolio() as any)
  }

  if (loading.portfolio && positions.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-4"></div>
          <div className="space-y-3">
            <div className="h-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
            <div className="h-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  const totalUnrealizedPnl = positions.reduce((sum, pos) => sum + (pos.unrealized_pnl || 0), 0)
  const totalRealizedPnl = positions.reduce((sum, pos) => sum + (pos.realized_pnl || 0), 0)

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
          <TrendingUp className="w-5 h-5 mr-2 text-primary-500" />
          Active Positions
        </h3>
        <button
          onClick={handleRefresh}
          disabled={loading.portfolio}
          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${loading.portfolio ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
          <span className="text-sm text-red-800 dark:text-red-300">{error}</span>
          <button onClick={() => dispatch(clearError())} className="ml-auto text-xs underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Summary */}
      {positions.length > 0 && (
        <div className="mb-4 grid grid-cols-2 gap-4">
          <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
            <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Total Unrealized P&L</p>
            <p className={`text-lg font-bold ${totalUnrealizedPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {totalUnrealizedPnl >= 0 ? '+' : ''}₹{totalUnrealizedPnl.toFixed(2)}
            </p>
          </div>
          <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
            <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Total Realized P&L</p>
            <p className={`text-lg font-bold ${totalRealizedPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {totalRealizedPnl >= 0 ? '+' : ''}₹{totalRealizedPnl.toFixed(2)}
            </p>
          </div>
        </div>
      )}

      {/* Positions List */}
      {positions.length === 0 ? (
        <div className="text-center text-gray-500 dark:text-gray-400 py-8">
          <TrendingDown className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No active positions</p>
        </div>
      ) : (
        <div className="space-y-3">
          {positions.map((position) => {
            const unrealizedPnl = position.unrealized_pnl || 0
            const pnlPercent = position.average_price > 0
              ? ((unrealizedPnl / (position.average_price * position.quantity)) * 100)
              : 0

            return (
              <div
                key={position.instrument || position.id}
                className="border border-gray-200 dark:border-gray-600 rounded-lg p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h4 className="font-semibold text-gray-900 dark:text-white">
                        {position.instrument}
                      </h4>
                      {position.instrument_type && (
                        <span className="text-xs px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded">
                          {position.instrument_type}
                        </span>
                      )}
                      {position.option_type && (
                        <span className="text-xs px-2 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded">
                          {position.option_type}
                        </span>
                      )}
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                      <div>
                        <p className="text-gray-600 dark:text-gray-400 text-xs">Quantity</p>
                        <p className="font-semibold text-gray-900 dark:text-white">
                          {position.quantity}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-600 dark:text-gray-400 text-xs">Avg Price</p>
                        <p className="font-semibold text-gray-900 dark:text-white">
                          ₹{position.average_price?.toFixed(2) || '0.00'}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-600 dark:text-gray-400 text-xs">Current Price</p>
                        <p className="font-semibold text-gray-900 dark:text-white">
                          ₹{position.current_price?.toFixed(2) || 'N/A'}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-600 dark:text-gray-400 text-xs">Market Value</p>
                        <p className="font-semibold text-gray-900 dark:text-white">
                          ₹{position.market_value?.toFixed(2) || '0.00'}
                        </p>
                      </div>
                    </div>

                    {position.strike_price && (
                      <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                        Strike: ₹{position.strike_price.toFixed(2)}
                        {position.expiry_date && ` | Expiry: ${new Date(position.expiry_date).toLocaleDateString()}`}
                      </div>
                    )}
                  </div>

                  <div className="ml-4 text-right">
                    <div className={`mb-2 ${unrealizedPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      <div className="flex items-center justify-end gap-1 mb-1">
                        {unrealizedPnl >= 0 ? (
                          <TrendingUp className="w-4 h-4" />
                        ) : (
                          <TrendingDown className="w-4 h-4" />
                        )}
                        <span className="text-lg font-bold">
                          {unrealizedPnl >= 0 ? '+' : ''}₹{Math.abs(unrealizedPnl).toFixed(2)}
                        </span>
                      </div>
                      <p className="text-xs">
                        {pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
                      </p>
                    </div>

                    <button
                      onClick={() => handleClosePosition(position.id || position.instrument, position.instrument)}
                      className="px-3 py-1 text-xs bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded hover:bg-red-200 dark:hover:bg-red-900/50 transition-colors flex items-center gap-1"
                      title="Close position"
                    >
                      <X className="w-3 h-3" />
                      Close
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {portfolio && (
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600 text-xs text-gray-500 dark:text-gray-400">
          Portfolio Value: ₹{portfolio.total_value?.toLocaleString('en-IN', { minimumFractionDigits: 2 }) || '0.00'} | 
          Cash: ₹{portfolio.cash_balance?.toLocaleString('en-IN', { minimumFractionDigits: 2 }) || '0.00'}
        </div>
      )}
    </div>
  )
}
