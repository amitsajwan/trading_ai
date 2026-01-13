import React from 'react'
import { Thermometer, AlertTriangle, CheckCircle, TrendingUp, TrendingDown } from 'lucide-react'
import { useGetPortfolioHeatSummaryQuery, useGetHeatUtilizationQuery } from '../../api/dashboardApi'

export const PortfolioHeatWidget: React.FC = () => {
  const { data: heatSummary, isLoading, error } = useGetPortfolioHeatSummaryQuery()
  const { data: heatUtilization, isLoading: utilLoading } = useGetHeatUtilizationQuery()

  if (isLoading || utilLoading) {
    return (
      <section aria-labelledby="portfolio-heat-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 id="portfolio-heat-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Portfolio Heat</h3>
        <div className="mt-4 animate-pulse">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-3"></div>
          <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </section>
    )
  }

  if (error || !heatSummary) {
    return (
      <section aria-labelledby="portfolio-heat-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 id="portfolio-heat-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Portfolio Heat</h3>
        <div className="mt-4 text-sm text-gray-500 dark:text-gray-400">
          <AlertTriangle className="w-6 h-6 inline-block mr-2 opacity-50" />
          Unable to load portfolio heat data
        </div>
      </section>
    )
  }

  const heatPercent = (heatSummary.total_portfolio_heat / heatSummary.max_portfolio_heat) * 100
  const availablePercent = (heatSummary.available_heat / heatSummary.max_portfolio_heat) * 100
  const isHigh = heatPercent > 80
  const isMedium = heatPercent > 50 && heatPercent <= 80

  return (
      <section 
      aria-labelledby="portfolio-heat-heading" 
      data-testid="widget-portfolio-heat"
      className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 id="portfolio-heat-heading" className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
          <Thermometer className="w-5 h-5 mr-2 text-primary-500" />
          Portfolio Heat
        </h3>
        {heatSummary.can_trade ? (
          <CheckCircle className="w-5 h-5 text-green-500" />
        ) : (
          <AlertTriangle className="w-5 h-5 text-red-500" />
        )}
      </div>

      {/* Heat Utilization Bar */}
      <div className="mb-6">
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Heat Utilization
          </span>
          <span className={`text-sm font-semibold ${
            isHigh ? 'text-red-600' : isMedium ? 'text-yellow-600' : 'text-green-600'
          }`}>
            {heatPercent.toFixed(1)}%
          </span>
        </div>
        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-4 relative">
          <div
            className={`h-4 rounded-full transition-all ${
              isHigh ? 'bg-red-500' : isMedium ? 'bg-yellow-500' : 'bg-green-500'
            }`}
            style={{ width: `${Math.min(heatPercent, 100)}%` }}
          />
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs font-semibold text-gray-900 dark:text-white">
              {heatSummary.total_portfolio_heat.toFixed(3)} / {heatSummary.max_portfolio_heat.toFixed(3)}
            </span>
          </div>
        </div>
        <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Available: {(heatSummary.available_heat * 100).toFixed(2)}%
        </div>
      </div>

      {/* Heat Breakdown */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className={`w-4 h-4 ${heatSummary.total_current_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`} />
            <span className="text-xs text-gray-600 dark:text-gray-400">Current P&L</span>
          </div>
          <p className={`text-lg font-semibold ${heatSummary.total_current_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {heatSummary.total_current_pnl >= 0 ? '+' : ''}₹{heatSummary.total_current_pnl.toFixed(2)}
          </p>
        </div>

        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <TrendingDown className="w-4 h-4 text-red-500" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Max Loss</span>
          </div>
          <p className="text-lg font-semibold text-gray-900 dark:text-white">
            ₹{heatSummary.total_max_loss.toFixed(2)}
          </p>
        </div>

        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
          <span className="text-xs text-gray-600 dark:text-gray-400">Daily P&L</span>
          <p className={`text-lg font-semibold ${heatSummary.daily_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {heatSummary.daily_pnl >= 0 ? '+' : ''}₹{heatSummary.daily_pnl.toFixed(2)}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            ({(heatSummary.daily_loss_pct * 100).toFixed(2)}% of account)
          </p>
        </div>

        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
          <span className="text-xs text-gray-600 dark:text-gray-400">Active Positions</span>
          <p className="text-lg font-semibold text-gray-900 dark:text-white">
            {heatSummary.active_positions}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Account: ₹{heatSummary.account_balance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </p>
        </div>
      </div>

      {/* Status Indicator */}
      <div className={`p-3 rounded-lg border ${
        !heatSummary.can_trade
          ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
          : isHigh
          ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
          : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
      }`}>
        <div className="flex items-center gap-2">
          {!heatSummary.can_trade ? (
            <>
              <AlertTriangle className="w-4 h-4 text-red-600 dark:text-red-400" />
              <span className="text-sm font-semibold text-red-800 dark:text-red-300">
                Trading Restricted - Risk Limits Exceeded
              </span>
            </>
          ) : isHigh ? (
            <>
              <AlertTriangle className="w-4 h-4 text-yellow-600 dark:text-yellow-400" />
              <span className="text-sm font-semibold text-yellow-800 dark:text-yellow-300">
                High Heat - Consider Reducing Positions
              </span>
            </>
          ) : (
            <>
              <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400" />
              <span className="text-sm font-semibold text-green-800 dark:text-green-300">
                Risk Limits Within Bounds
              </span>
            </>
          )}
        </div>
      </div>
    </section>
  )
}
