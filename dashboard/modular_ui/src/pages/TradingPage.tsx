import React, { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Activity, AlertCircle, CheckCircle2 } from 'lucide-react'
import { RootState } from '../store'
import { fetchLatestDecision, fetchPortfolio, clearError } from '../store/slices/tradingSlice'
import { TradeExecutionWidget } from '../components/widgets/TradeExecutionWidget'
import { ActivePositionsWidget } from '../components/widgets/ActivePositionsWidget'
import { QuickActionsWidget } from '../components/widgets/QuickActionsWidget'
import { RiskManagementWidget } from '../components/widgets/RiskManagementWidget'
import { ActiveSignalsWidget } from '../components/widgets/ActiveSignalsWidget'

export const TradingPage: React.FC = () => {
  const dispatch = useDispatch()
  const { error, portfolio, latestDecision } = useSelector((state: RootState) => state.trading)

  useEffect(() => {
    // Initial data fetch
    dispatch(fetchLatestDecision() as any)
    dispatch(fetchPortfolio() as any)

    // Auto-refresh every 10 seconds
    const interval = setInterval(() => {
      dispatch(fetchLatestDecision() as any)
      dispatch(fetchPortfolio() as any)
    }, 10000)

    return () => clearInterval(interval)
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Trading
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Execute trades and manage positions
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Status Indicator */}
          <div className="flex items-center gap-2">
            {portfolio && portfolio.positions_count > 0 ? (
              <>
                <CheckCircle2 className="w-4 h-4 text-green-500" />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {portfolio.positions_count} Active {portfolio.positions_count === 1 ? 'Position' : 'Positions'}
                </span>
              </>
            ) : (
              <>
                <Activity className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-600 dark:text-gray-400">No Positions</span>
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

      {/* Trading Summary */}
      {portfolio && (
        <div className="bg-gradient-to-r from-primary-50 to-primary-100 dark:from-primary-900/20 dark:to-primary-800/20 rounded-lg p-4 border border-primary-200 dark:border-primary-800">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Portfolio Value</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                ₹{portfolio.total_value?.toLocaleString('en-IN', { minimumFractionDigits: 2 }) || '0.00'}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Cash Balance</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                ₹{portfolio.cash_balance?.toLocaleString('en-IN', { minimumFractionDigits: 2 }) || '0.00'}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Day P&L</p>
              <p className={`text-xl font-bold ${(portfolio.day_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {(portfolio.day_pnl || 0) >= 0 ? '+' : ''}₹{Math.abs(portfolio.day_pnl || 0).toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Total P&L</p>
              <p className={`text-xl font-bold ${(portfolio.total_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {(portfolio.total_pnl || 0) >= 0 ? '+' : ''}₹{Math.abs(portfolio.total_pnl || 0).toFixed(2)}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Main Widgets Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left Column - Main Trading Actions */}
        <div className="xl:col-span-2 space-y-6">
          <TradeExecutionWidget />
          <ActiveSignalsWidget />
          <ActivePositionsWidget />
        </div>

        {/* Right Column - Quick Actions and Risk Management */}
        <div className="space-y-6">
          <QuickActionsWidget />
          <RiskManagementWidget />
        </div>
      </div>
    </div>
  )
}