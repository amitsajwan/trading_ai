import React, { useState } from 'react'
import { useGetPortfolioQuery, useCalculateKellyMutation } from '../../api/dashboardApi'
import { Activity, Calculator, TrendingUp } from 'lucide-react'

export const PortfolioWidget: React.FC = () => {
  const { data, error, isLoading, isFetching } = useGetPortfolioQuery()
  const [calculateKelly, { data: kellyData, isLoading: kellyLoading }] = useCalculateKellyMutation()
  const [showKelly, setShowKelly] = useState(false)

  if (isLoading) {
    return (
      <section aria-labelledby="portfolio-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 id="portfolio-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Portfolio</h3>
        <div className="mt-4 animate-pulse">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-3"></div>
          <div className="h-40 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </section>
    )
  }

  if (error || !data) {
    return (
      <section aria-labelledby="portfolio-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 id="portfolio-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Portfolio</h3>
        <div className="mt-4 text-sm text-gray-500 dark:text-gray-400">
          <Activity className="w-6 h-6 inline-block mr-2 opacity-50" />
          Unable to load portfolio
        </div>
      </section>
    )
  }

  const positions = data.positions ?? []

  return (
    <section aria-labelledby="portfolio-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between">
        <h3 id="portfolio-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Portfolio</h3>
        {isFetching && <span className="text-xs text-gray-500">Refreshing…</span>}
      </div>

      {positions.length === 0 ? (
        <div className="mt-4 text-sm text-gray-500 dark:text-gray-400">No positions</div>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm" role="table" aria-label="portfolio table">
            <thead>
              <tr>
                <th className="font-medium text-gray-600 dark:text-gray-300">Instrument</th>
                <th className="font-medium text-gray-600 dark:text-gray-300">Qty</th>
                <th className="font-medium text-gray-600 dark:text-gray-300">Avg Price</th>
                <th className="font-medium text-gray-600 dark:text-gray-300">P&L</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p: any) => (
                <tr key={p.id} className="border-t border-gray-100 dark:border-gray-700">
                  <td className="py-2">{p.instrument}</td>
                  <td className="py-2">{p.quantity}</td>
                  <td className="py-2">₹{Number(p.avg_price).toFixed(2)}</td>
                  <td className={`py-2 ${p.unrealized_pl >= 0 ? 'text-green-600' : 'text-red-600'}`}>₹{Number(p.unrealized_pl).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Layer 8: Kelly Position Sizing */}
      {positions.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center">
              <Calculator className="w-4 h-4 mr-2 text-primary-500" />
              Kelly Position Sizing
            </h4>
            <button
              onClick={() => {
                setShowKelly(!showKelly)
                if (!showKelly && !kellyData) {
                  // Calculate Kelly for first position
                  const firstPos = positions[0]
                  calculateKelly({
                    account_balance: data.summary?.total_value || 100000,
                    max_loss_per_unit: Math.abs((firstPos.entry_price || 0) - (firstPos.stop_loss || firstPos.entry_price || 0)) * (firstPos.quantity || 0),
                    trade_history: [], // Could fetch from API
                    strategy_type: 'momentum'
                  })
                }
              }}
              className="text-xs text-primary-600 dark:text-primary-400 hover:underline"
            >
              {showKelly ? 'Hide' : 'Calculate'}
            </button>
          </div>
          
          {showKelly && (
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
              {kellyLoading ? (
                <div className="text-xs text-gray-500 dark:text-gray-400">Calculating...</div>
              ) : kellyData ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="w-4 h-4 text-green-500" />
                    <span className="text-sm font-semibold text-gray-900 dark:text-white">
                      Recommended Position Size: {kellyData.quantity} units
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-gray-600 dark:text-gray-400">Kelly %:</span>
                      <span className="ml-1 font-semibold">{(kellyData.kelly_pct * 100).toFixed(2)}%</span>
                    </div>
                    <div>
                      <span className="text-gray-600 dark:text-gray-400">Risk Amount:</span>
                      <span className="ml-1 font-semibold">₹{kellyData.risk_amount.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-gray-600 dark:text-gray-400">Win Rate:</span>
                      <span className="ml-1 font-semibold">
                        {(kellyData.historical_stats.win_rate * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600 dark:text-gray-400">R:R Ratio:</span>
                      <span className="ml-1 font-semibold">{kellyData.risk_reward_ratio.toFixed(2)}</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  Click "Calculate" to see Kelly position sizing recommendations
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="mt-3 text-xs text-gray-500">Updated: {new Date(data.updated_at ?? Date.now()).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })}</div>
    </section>
  )
}
