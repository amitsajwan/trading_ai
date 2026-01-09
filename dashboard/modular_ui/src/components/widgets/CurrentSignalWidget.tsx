import React, { useMemo } from 'react'
import { useSelector, shallowEqual } from 'react-redux'
import { TrendingUp, TrendingDown, Minus, Target, AlertTriangle, BarChart3 } from 'lucide-react'
import { RootState } from '../../store'

export const CurrentSignalWidget: React.FC = React.memo(() => {
  // Use selective selectors to prevent unnecessary re-renders
  const latestDecision = useSelector((state: RootState) => state.trading.latestDecision, shallowEqual)
  const optionsStrategy = useSelector((state: RootState) => state.trading.optionsStrategy, shallowEqual)
  const loading = useSelector((state: RootState) => state.trading.loading.decision)
  const signals = useSelector((state: RootState) => state.trading.signals, shallowEqual)

  // Find a relevant active signal for the instrument (prefer pending)
  // Memoize to prevent recalculation on every render
  const activeSignal = useMemo(() => {
    if (!signals || !latestDecision) return null
    return signals.find(s => s.instrument === latestDecision.instrument && (s.status === 'pending' || s.status === 'triggered')) 
        || signals.find(s => s.instrument === latestDecision.instrument)
  }, [signals, latestDecision?.instrument])

  // If we have an options strategy, show a summary of it (or fallback to active signal metadata)
  const strategySummary = optionsStrategy?.available ? optionsStrategy : activeSignal?.metadata?.options_strategy_summary

  if (strategySummary?.available || strategySummary) {
    const summary = strategySummary?.available ? optionsStrategy : strategySummary
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Current Strategy
          </h3>
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Live
            </span>
          </div>
        </div>

        {/* Options Strategy Summary */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center space-x-2 px-4 py-2 rounded-lg bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-200 mb-3">
            <BarChart3 className="w-6 h-6" />
            <span className="text-xl font-bold uppercase">
              {optionsStrategy.strategy_type.replace(/_/g, ' ')}
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            {optionsStrategy.confidence.toFixed(1)}%
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400 max-w-xs mx-auto">
            Multi-leg options strategy with {optionsStrategy.legs.length} legs
          </p>
        </div>

        {/* Quick Risk Summary */}
        <div className="space-y-3">
          <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-gray-600">
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Max Profit
            </span>
            <span className="text-sm font-semibold text-green-600 dark:text-green-400">
              ₹{optionsStrategy.risk_analysis.max_profit.toLocaleString('en-IN')}
            </span>
          </div>

          <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-gray-600">
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Max Loss
            </span>
            <span className="text-sm font-semibold text-red-600 dark:text-red-400">
              ₹{optionsStrategy.risk_analysis.max_loss.toLocaleString('en-IN')}
            </span>
          </div>

          <div className="flex justify-between items-center py-2">
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Risk/Reward
            </span>
            <span className="text-sm font-semibold text-gray-900 dark:text-white">
              1:{optionsStrategy.risk_analysis.risk_reward_ratio.toFixed(1)}
            </span>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600 dark:text-gray-400">
              {optionsStrategy.underlying}
            </span>
            <span className="text-gray-500 dark:text-gray-400">
              {new Date(optionsStrategy.timestamp).toLocaleTimeString()}
            </span>
          </div>
        </div>
      </div>
    )
  }

  // Original signal display logic
  if (loading.decision) {
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

  if (!latestDecision) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <Target className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No trading signals available</p>
          <p className="text-sm mt-1">AI agents are analyzing market conditions</p>
        </div>
      </div>
    )
  }

  const getSignalColor = (signal: string) => {
    switch (signal.toUpperCase()) {
      case 'BUY': return 'text-green-600 bg-green-100 dark:bg-green-900 dark:text-green-200'
      case 'SELL': return 'text-red-600 bg-red-100 dark:bg-red-900 dark:text-red-200'
      case 'HOLD': return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900 dark:text-yellow-200'
      default: return 'text-gray-600 bg-gray-100 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  const getSignalIcon = (signal: string) => {
    switch (signal.toUpperCase()) {
      case 'BUY': return <TrendingUp className="w-6 h-6" />
      case 'SELL': return <TrendingDown className="w-6 h-6" />
      case 'HOLD': return <Minus className="w-6 h-6" />
      default: return <AlertTriangle className="w-6 h-6" />
    }
  }

  const formatPrice = (price: number | undefined) => {
    return price ? `₹${price.toLocaleString('en-IN')}` : '--'
  }

  const getStatusBadge = (status?: string) => {
    switch ((status || '').toLowerCase()) {
      case 'pending': return <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-indigo-100 text-indigo-700">PENDING</span>
      case 'triggered': return <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-yellow-100 text-yellow-800">TRIGGERED</span>
      case 'executed': return <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-green-100 text-green-700">EXECUTED</span>
      case 'expired': return <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-gray-100 text-gray-700">EXPIRED</span>
      case 'cancelled': return <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-red-100 text-red-700">CANCELLED</span>
      default: return null
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Current Signal
        </h3>
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <span className="text-sm text-gray-500 dark:text-gray-400">
            Live
          </span>
        </div>
      </div>

      {/* Signal Display */}
      <div className="text-center mb-6">
        <div className="flex items-center justify-center mb-3 space-x-3">
          <div className={`inline-flex items-center space-x-2 px-4 py-2 rounded-lg ${getSignalColor(latestDecision.signal)}`}>
            {getSignalIcon(latestDecision.signal)}
            <span className="text-xl font-bold uppercase">
              {latestDecision.signal}
            </span>
          </div>
          {/* Status badge from active signal */}
          <div>
            {getStatusBadge(activeSignal?.status)}
          </div>
        </div>

        <div className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          {latestDecision.confidence.toFixed(1)}%
        </div>
        <p className="text-sm text-gray-600 dark:text-gray-400 max-w-xs mx-auto">
          {latestDecision.reasoning}
        </p>

        {/* If active signal includes options strategy summary, show a compact summary */}
        {activeSignal?.metadata?.options_strategy_summary && (
          <div className="mt-4 bg-gray-50 dark:bg-gray-900 p-3 rounded">
            <div className="text-xs text-gray-500">Options Strategy</div>
            <div className="mt-1 text-sm">
              <strong>{activeSignal.metadata.options_strategy_summary.strategy_type}</strong> • {activeSignal.metadata.options_strategy_summary.legs_count} legs • Max loss: ₹{Number(activeSignal.metadata.options_strategy_summary.max_loss || 0).toLocaleString('en-IN')} • Expiry: {activeSignal.metadata.options_strategy_summary.expiry}
            </div>
          </div>
        )}
      </div>

      {/* Trading Parameters */}
      <div className="space-y-3">
        <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-gray-600">
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
            Entry Price
          </span>
          <span className="text-sm font-semibold text-gray-900 dark:text-white">
            {formatPrice(latestDecision.entry_price)}
          </span>
        </div>

        <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-gray-600">
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
            Stop Loss
          </span>
          <span className="text-sm font-semibold text-red-600 dark:text-red-400">
            {formatPrice(latestDecision.stop_loss)}
          </span>
        </div>

        <div className="flex justify-between items-center py-2">
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
            Take Profit
          </span>
          <span className="text-sm font-semibold text-green-600 dark:text-green-400">
            {formatPrice(latestDecision.take_profit)}
          </span>
        </div>
      </div>

      {/* Instrument & Timestamp */}
      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
        <div className="flex justify-between text-sm">
          <span className="text-gray-600 dark:text-gray-400">
            {latestDecision.instrument}
          </span>
          <span className="text-gray-500 dark:text-gray-400">
            {new Date(latestDecision.timestamp).toLocaleTimeString()}
          </span>
        </div>
      </div>
    </div>
  )
}, (prevProps, nextProps) => {
  // Custom comparison function - component never receives props, so always return true
  return true
})