import React, { useState } from 'react'
import { Calculator, TrendingUp, TrendingDown, DollarSign, BarChart3, RefreshCw } from 'lucide-react'
import { useCalculateKellyMutation } from '../../api/dashboardApi'

interface KellySizingWidgetProps {
  accountBalance?: number
  maxLossPerUnit?: number
  strategyType?: string
}

export const KellySizingWidget: React.FC<KellySizingWidgetProps> = ({
  accountBalance = 100000,
  maxLossPerUnit,
  strategyType = 'momentum'
}) => {
  const [calculateKelly, { data: kellyData, isLoading, error }] = useCalculateKellyMutation()
  const [winProb, setWinProb] = useState<number>(0.55)
  const [riskReward, setRiskReward] = useState<number>(2.0)
  const [manualMode, setManualMode] = useState(false)

  const handleCalculate = async () => {
    if (manualMode) {
      // Use manual inputs
      await calculateKelly({
        account_balance: accountBalance,
        max_loss_per_unit: maxLossPerUnit || 100.0,
        win_probability: winProb,
        risk_reward_ratio: riskReward,
      })
    } else {
      // Use historical stats (would need trade history from API)
      await calculateKelly({
        account_balance: accountBalance,
        max_loss_per_unit: maxLossPerUnit || 100.0,
        trade_history: [], // TODO: Fetch from API
        strategy_type: strategyType
      })
    }
  }

  const kellyPercent = kellyData?.kelly_pct || 0
  const recommendedQuantity = kellyData?.quantity || 0
  const riskAmount = kellyData?.risk_amount || 0
  const isSafe = kellyPercent > 0 && kellyPercent <= 0.25 // 25% is reasonable

  return (
    <section 
      aria-labelledby="kelly-sizing-heading" 
      data-testid="widget-kelly-sizing"
      className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 id="kelly-sizing-heading" className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
          <Calculator className="w-5 h-5 mr-2 text-primary-500" />
          Kelly Position Sizing
        </h3>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={manualMode}
            onChange={(e) => setManualMode(e.target.checked)}
            className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
          />
          <span className="text-xs text-gray-600 dark:text-gray-400">Manual</span>
        </label>
      </div>

      {manualMode && (
        <div className="mb-4 space-y-3 bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Win Probability ({Math.round(winProb * 100)}%)
            </label>
            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.01"
              value={winProb}
              onChange={(e) => setWinProb(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Risk/Reward Ratio ({riskReward.toFixed(2)})
            </label>
            <input
              type="range"
              min="0.5"
              max="5.0"
              step="0.1"
              value={riskReward}
              onChange={(e) => setRiskReward(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
        </div>
      )}

      <div className="mb-4">
        <button
          onClick={handleCalculate}
          disabled={isLoading}
          className="w-full py-2 px-4 bg-primary-600 hover:bg-primary-700 disabled:bg-primary-400 text-white rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
        >
          {isLoading ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              Calculating...
            </>
          ) : (
            <>
              <Calculator className="w-4 h-4" />
              Calculate Kelly Size
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-sm text-red-800 dark:text-red-300">
            Error calculating Kelly size: {error?.toString() || 'Unknown error'}
          </p>
        </div>
      )}

      {kellyData && (
        <div className="space-y-4">
          {/* Kelly Percentage */}
          <div className={`p-4 rounded-lg border ${
            isSafe
              ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
              : kellyPercent > 0.5
              ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
              : 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
          }`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <BarChart3 className={`w-5 h-5 ${
                  isSafe ? 'text-green-600' : kellyPercent > 0.5 ? 'text-red-600' : 'text-yellow-600'
                }`} />
                <span className="text-sm font-semibold text-gray-900 dark:text-white">
                  Kelly Percentage
                </span>
              </div>
              <span className={`text-lg font-bold ${
                isSafe ? 'text-green-600' : kellyPercent > 0.5 ? 'text-red-600' : 'text-yellow-600'
              }`}>
                {(kellyPercent * 100).toFixed(2)}%
              </span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all ${
                  isSafe ? 'bg-green-500' : kellyPercent > 0.5 ? 'bg-red-500' : 'bg-yellow-500'
                }`}
                style={{ width: `${Math.min(kellyPercent * 100, 100)}%` }}
              />
            </div>
            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
              {isSafe ? 'Safe position size' : kellyPercent > 0.5 ? 'Too risky - reduce size' : 'Moderate risk - consider reducing'}
            </p>
          </div>

          {/* Recommended Quantity */}
          <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="w-5 h-5 text-primary-500" />
              <span className="text-sm font-semibold text-gray-900 dark:text-white">
                Recommended Position Size
              </span>
            </div>
            <div className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              {recommendedQuantity} units
            </div>
            <div className="text-xs text-gray-600 dark:text-gray-400">
              Based on {((kellyData.kelly_pct || 0) * 100).toFixed(2)}% of account balance
            </div>
          </div>

          {/* Risk Amount */}
          <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <DollarSign className="w-5 h-5 text-primary-500" />
              <span className="text-sm font-semibold text-gray-900 dark:text-white">
                Risk Amount
              </span>
            </div>
            <div className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
              ₹{riskAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-xs text-gray-600 dark:text-gray-400">
              {(riskAmount / accountBalance * 100).toFixed(2)}% of account balance
            </div>
          </div>

          {/* Historical Stats */}
          {kellyData.historical_stats && (
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <BarChart3 className="w-5 h-5 text-primary-500" />
                <span className="text-sm font-semibold text-gray-900 dark:text-white">
                  Historical Statistics
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-gray-600 dark:text-gray-400">Win Rate:</span>
                  <span className="ml-2 font-semibold text-gray-900 dark:text-white">
                    {(kellyData.historical_stats.win_rate * 100).toFixed(1)}%
                  </span>
                </div>
                <div>
                  <span className="text-gray-600 dark:text-gray-400">Avg Win:</span>
                  <span className="ml-2 font-semibold text-green-600">
                    ₹{kellyData.historical_stats.avg_win.toFixed(2)}
                  </span>
                </div>
                <div>
                  <span className="text-gray-600 dark:text-gray-400">Avg Loss:</span>
                  <span className="ml-2 font-semibold text-red-600">
                    ₹{kellyData.historical_stats.avg_loss.toFixed(2)}
                  </span>
                </div>
                <div>
                  <span className="text-gray-600 dark:text-gray-400">R:R Ratio:</span>
                  <span className="ml-2 font-semibold text-gray-900 dark:text-white">
                    {kellyData.historical_stats.risk_reward.toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Warning if Kelly too high */}
          {kellyPercent > 0.3 && (
            <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
              <div className="flex items-center gap-2">
                <TrendingDown className="w-4 h-4 text-yellow-600 dark:text-yellow-400" />
                <span className="text-sm font-semibold text-yellow-800 dark:text-yellow-300">
                  Warning: Kelly percentage is high ({(kellyPercent * 100).toFixed(2)}%)
                </span>
              </div>
              <p className="text-xs text-yellow-700 dark:text-yellow-400 mt-1">
                Consider using fractional Kelly (e.g., 1/4 Kelly) for safety
              </p>
            </div>
          )}
        </div>
      )}

      {!kellyData && !isLoading && (
        <div className="text-center py-8 text-sm text-gray-500 dark:text-gray-400">
          <Calculator className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>Click "Calculate Kelly Size" to get position sizing recommendations</p>
        </div>
      )}
    </section>
  )
}
