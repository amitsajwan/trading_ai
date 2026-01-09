import React, { useEffect, useState } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { TrendingUp, TrendingDown, Target, AlertTriangle, DollarSign, BarChart3, Play, History } from 'lucide-react'
import { RootState } from '../../store'
import { fetchOptionsStrategy, executeOptionsStrategy, fetchOptionsStrategyHistory, OptionsStrategy as OptionsStrategyType, OptionsStrategyHistory } from '../../store/slices/tradingSlice'

export const OptionsStrategyWidget: React.FC = () => {
  const dispatch = useDispatch()
  const { optionsStrategy, loading } = useSelector((state: RootState) => state.trading)
  const [showHistory, setShowHistory] = useState(false)
  const [strategyHistory, setStrategyHistory] = useState<OptionsStrategyHistory | null>(null)

  useEffect(() => {
    dispatch(fetchOptionsStrategy() as any)
  }, [dispatch])

  const handleExecuteStrategy = async () => {
    if (!optionsStrategy?.available) return

    try {
      await dispatch(executeOptionsStrategy() as any)
      // Refresh the strategy after execution
      dispatch(fetchOptionsStrategy() as any)
    } catch (error) {
      console.error('Failed to execute strategy:', error)
    }
  }

  const handleShowHistory = async () => {
    try {
      const result = await dispatch(fetchOptionsStrategyHistory(5) as any)
      setStrategyHistory(result.payload)
      setShowHistory(true)
    } catch (error) {
      console.error('Failed to fetch history:', error)
    }
  }

  const getStrategyColor = (strategyType: string) => {
    switch (strategyType.toLowerCase()) {
      case 'bull_call_spread':
      case 'bull_put_spread':
        return 'text-green-600 bg-green-100 dark:bg-green-900 dark:text-green-200'
      case 'bear_put_spread':
      case 'bear_call_spread':
        return 'text-red-600 bg-red-100 dark:bg-red-900 dark:text-red-200'
      case 'iron_condor':
        return 'text-blue-600 bg-blue-100 dark:bg-blue-900 dark:text-blue-200'
      default:
        return 'text-gray-600 bg-gray-100 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  const getStrategyIcon = (strategyType: string) => {
    switch (strategyType.toLowerCase()) {
      case 'bull_call_spread':
      case 'bull_put_spread':
        return <TrendingUp className="w-5 h-5" />
      case 'bear_put_spread':
      case 'bear_call_spread':
        return <TrendingDown className="w-5 h-5" />
      case 'iron_condor':
        return <BarChart3 className="w-5 h-5" />
      default:
        return <Target className="w-5 h-5" />
    }
  }

  const formatCurrency = (amount: number) => {
    return `₹${amount.toLocaleString('en-IN')}`
  }

  const formatStrategyName = (strategyType: string) => {
    return strategyType.replace(/_/g, ' ').toUpperCase()
  }

  if (loading.optionsStrategy) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-4"></div>
          <div className="space-y-3">
            <div className="h-12 bg-gray-200 dark:bg-gray-700 rounded"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
          </div>
        </div>
      </div>
    )
  }

  if (showHistory && strategyHistory) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Strategy History
          </h3>
          <button
            onClick={() => setShowHistory(false)}
            className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
          >
            Back to Current
          </button>
        </div>

        <div className="space-y-4">
          {strategyHistory.strategies.map((strategy) => (
            <div key={strategy.strategy_id} className="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  {getStrategyIcon(strategy.strategy_type)}
                  <span className="font-medium text-gray-900 dark:text-white">
                    {formatStrategyName(strategy.strategy_type)}
                  </span>
                </div>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {new Date(strategy.timestamp).toLocaleString()}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-600 dark:text-gray-400">Net Premium:</span>
                  <span className={`ml-2 font-medium ${strategy.net_premium >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {formatCurrency(strategy.net_premium)}
                  </span>
                </div>
                <div>
                  <span className="text-gray-600 dark:text-gray-400">Margin:</span>
                  <span className="ml-2 font-medium text-gray-900 dark:text-white">
                    {formatCurrency(strategy.total_margin)}
                  </span>
                </div>
              </div>

              <div className="mt-2">
                <span className="text-sm text-gray-600 dark:text-gray-400">Legs:</span>
                <div className="mt-1 space-y-1">
                  {strategy.legs.map((leg, index) => (
                    <div key={index} className="text-xs text-gray-500 dark:text-gray-400 flex justify-between">
                      <span>{leg.instrument}</span>
                      <span>{leg.side} {leg.quantity} @ {formatCurrency(leg.price)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!optionsStrategy || !optionsStrategy.available) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <Target className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No options strategy available</p>
          <p className="text-sm mt-1">AI agents are analyzing market conditions</p>
          <button
            onClick={handleShowHistory}
            className="mt-4 text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
          >
            View Strategy History
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Options Strategy
        </h3>
        <div className="flex items-center space-x-2">
          <button
            onClick={handleShowHistory}
            className="text-sm text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-300"
          >
            <History className="w-4 h-4 inline mr-1" />
            History
          </button>
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <span className="text-sm text-gray-500 dark:text-gray-400">
            Live
          </span>
        </div>
      </div>

      {/* Strategy Header */}
      <div className="text-center mb-6">
        <div className={`inline-flex items-center space-x-2 px-4 py-2 rounded-lg mb-3 ${getStrategyColor(optionsStrategy.strategy_type)}`}>
          {getStrategyIcon(optionsStrategy.strategy_type)}
          <span className="text-lg font-bold uppercase">
            {formatStrategyName(optionsStrategy.strategy_type)}
          </span>
        </div>
        <div className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          {optionsStrategy.confidence.toFixed(1)}% Confidence
        </div>
        <p className="text-sm text-gray-600 dark:text-gray-400 max-w-xs mx-auto">
          {optionsStrategy.reasoning}
        </p>
      </div>

      {/* Strategy Legs */}
      <div className="mb-6">
        <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Strategy Legs</h4>
        <div className="space-y-2">
          {optionsStrategy.legs.map((leg, index) => (
            <div key={index} className="flex items-center justify-between py-2 px-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="flex items-center space-x-3">
                <span className={`text-sm font-medium ${leg.position === 'BUY' ? 'text-green-600' : 'text-red-600'}`}>
                  {leg.position}
                </span>
                <span className="text-sm text-gray-900 dark:text-white">
                  {leg.option_type} {leg.strike_price}
                </span>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  ×{leg.quantity}
                </span>
              </div>
              {leg.premium && (
                <span className="text-sm font-medium text-gray-900 dark:text-white">
                  {formatCurrency(leg.premium)}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Risk Analysis */}
      <div className="mb-6">
        <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Risk Analysis</h4>
        <div className="grid grid-cols-2 gap-4">
          <div className="text-center p-3 bg-green-50 dark:bg-green-900 rounded-lg">
            <div className="text-lg font-bold text-green-600 dark:text-green-200">
              {formatCurrency(optionsStrategy.risk_analysis.max_profit)}
            </div>
            <div className="text-sm text-green-600 dark:text-green-400">Max Profit</div>
          </div>
          <div className="text-center p-3 bg-red-50 dark:bg-red-900 rounded-lg">
            <div className="text-lg font-bold text-red-600 dark:text-red-200">
              {formatCurrency(optionsStrategy.risk_analysis.max_loss)}
            </div>
            <div className="text-sm text-red-600 dark:text-red-400">Max Loss</div>
          </div>
        </div>

        <div className="mt-3 space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600 dark:text-gray-400">Risk/Reward Ratio:</span>
            <span className="font-medium text-gray-900 dark:text-white">
              1:{optionsStrategy.risk_analysis.risk_reward_ratio.toFixed(1)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600 dark:text-gray-400">Margin Required:</span>
            <span className="font-medium text-gray-900 dark:text-white">
              {formatCurrency(optionsStrategy.risk_analysis.margin_required)}
            </span>
          </div>
          {optionsStrategy.risk_analysis.breakeven_points.length > 0 && (
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Breakeven:</span>
              <span className="font-medium text-gray-900 dark:text-white">
                {optionsStrategy.risk_analysis.breakeven_points.map(p => formatCurrency(p)).join(', ')}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Execute Button */}
      <div className="flex justify-center">
        <button
          onClick={handleExecuteStrategy}
          disabled={loading.executeOptions}
          className="inline-flex items-center space-x-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg font-medium transition-colors"
        >
          <Play className="w-4 h-4" />
          <span>{loading.executeOptions ? 'Executing...' : 'Execute Strategy'}</span>
        </button>
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
        <div className="flex justify-between text-sm">
          <span className="text-gray-600 dark:text-gray-400">
            {optionsStrategy.underlying}
          </span>
          <span className="text-gray-500 dark:text-gray-400">
            Expires {optionsStrategy.expiry}
          </span>
        </div>
      </div>
    </div>
  )
}