import React, { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Activity, AlertCircle, CheckCircle2, Clock, Play, X } from 'lucide-react'
import { RootState } from '../../store'
import { 
  fetchSignals, 
  checkSignalConditions, 
  executeSignalWhenReady,
  TradingSignal 
} from '../../store/slices/tradingSlice'

export const ActiveSignalsWidget: React.FC = () => {
  const dispatch = useDispatch()
  const { signals, loading, error } = useSelector((state: RootState) => state.trading)
  const [selectedSignal, setSelectedSignal] = useState<string | null>(null)

  useEffect(() => {
    // Initial fetch
    dispatch(fetchSignals('BANKNIFTY') as any)

    // Auto-refresh every 10 seconds
    const interval = setInterval(() => {
      dispatch(fetchSignals('BANKNIFTY') as any)
    }, 10000)

    return () => clearInterval(interval)
  }, [dispatch])

  // Check conditions for all signals periodically
  useEffect(() => {
    const checkInterval = setInterval(() => {
      signals.forEach(signal => {
        if (signal.status === 'pending' && signal.signal_id) {
          dispatch(checkSignalConditions(signal.signal_id) as any)
        }
      })
    }, 5000) // Check every 5 seconds

    return () => clearInterval(checkInterval)
  }, [signals, dispatch])

  const handleExecuteWhenReady = async (signal: TradingSignal) => {
    if (signal.signal_id || signal.condition_id) {
      await dispatch(executeSignalWhenReady(signal.signal_id || signal.condition_id || '') as any)
      // Refresh signals after execution
      setTimeout(() => {
        dispatch(fetchSignals('BANKNIFTY') as any)
      }, 1000)
    }
  }

  const getStatusIcon = (status?: string, conditionsMet?: boolean) => {
    if (status === 'executed') {
      return <CheckCircle2 className="w-4 h-4 text-green-500" />
    }
    if (status === 'triggered' || conditionsMet) {
      return <Play className="w-4 h-4 text-blue-500" />
    }
    if (status === 'expired' || status === 'cancelled') {
      return <X className="w-4 h-4 text-gray-400" />
    }
    return <Clock className="w-4 h-4 text-yellow-500" />
  }

  const getStatusColor = (status?: string, conditionsMet?: boolean) => {
    if (status === 'executed') return 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
    if (status === 'triggered' || conditionsMet) return 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
    if (status === 'expired' || status === 'cancelled') return 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700'
    return 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
  }

  const activeSignals = signals.filter(s => 
    s.status === 'pending' || s.status === 'triggered' || !s.status
  )

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-primary-600 dark:text-primary-400" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Active Trading Signals
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600 dark:text-gray-400">
            {activeSignals.length} Active
          </span>
        </div>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400" />
          <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
        </div>
      )}

      {loading.signals ? (
        <div className="text-center py-8">
          <Activity className="w-8 h-8 text-gray-400 animate-spin mx-auto mb-2" />
          <p className="text-sm text-gray-600 dark:text-gray-400">Loading signals...</p>
        </div>
      ) : activeSignals.length === 0 ? (
        <div className="text-center py-8">
          <Clock className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <p className="text-sm text-gray-600 dark:text-gray-400">No active signals</p>
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
            Signals will appear here after orchestrator analysis cycles
          </p>
        </div>
      ) : (
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {activeSignals.map((signal) => (
            <div
              key={signal.signal_id || signal.condition_id || Math.random()}
              className={`border rounded-lg p-4 transition-all ${
                getStatusColor(signal.status, signal.conditions_met)
              } ${selectedSignal === signal.signal_id ? 'ring-2 ring-primary-500' : ''}`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    {getStatusIcon(signal.status, signal.conditions_met)}
                    <span
                      className={`text-sm font-semibold ${
                        signal.action === 'BUY'
                          ? 'text-green-600 dark:text-green-400'
                          : signal.action === 'SELL'
                          ? 'text-red-600 dark:text-red-400'
                          : 'text-gray-600 dark:text-gray-400'
                      }`}
                    >
                      {signal.action}
                    </span>
                    <span className="text-sm text-gray-600 dark:text-gray-400">
                      {signal.instrument}
                    </span>
                    {signal.confidence && (
                      <span className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">
                        {(signal.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>

                  {signal.indicator && signal.threshold && (
                    <div className="text-xs text-gray-600 dark:text-gray-400 mb-1">
                      <span className="font-medium">Condition:</span> {signal.indicator}{' '}
                      {signal.operator || '>'} {signal.threshold}
                      {signal.current_value !== undefined && (
                        <span className="ml-2">
                          (Current: {signal.current_value.toFixed(2)})
                        </span>
                      )}
                    </div>
                  )}

                  {signal.reasoning && (
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-2 line-clamp-2">
                      {signal.reasoning}
                    </p>
                  )}

                  <div className="flex items-center gap-4 mt-2 text-xs text-gray-500 dark:text-gray-500">
                    {signal.stop_loss && (
                      <span>SL: ₹{signal.stop_loss.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    )}
                    {signal.take_profit && (
                      <span>TP: ₹{signal.take_profit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    )}
                    {signal.timestamp && (
                      <span>
                        {new Date(signal.timestamp).toLocaleTimeString()}
                      </span>
                    )}

                    {/* Show signal id and allow quick copy */}
                    {signal.signal_id && (
                      <div className="text-xs text-gray-400 dark:text-gray-500 mt-1 flex items-center gap-2">
                        <span className="font-mono">ID: {String(signal.signal_id).slice(0,8)}</span>
                        <button
                          onClick={() => navigator.clipboard?.writeText(String(signal.signal_id))}
                          className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded"
                          title="Copy signal id"
                        >Copy</button>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex flex-col gap-2 items-end">
                  {signal.conditions_met ? (
                    <button
                      onClick={() => handleExecuteWhenReady(signal)}
                      className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-xs font-medium rounded transition-colors"
                    >
                      Execute
                    </button>
                  ) : signal.status === 'pending' || !signal.status ? (
                    <button
                      onClick={() => handleExecuteWhenReady(signal)}
                      className="px-3 py-1.5 bg-primary-600 hover:bg-primary-700 text-white text-xs font-medium rounded transition-colors"
                      title="Enable automatic execution when conditions are met"
                    >
                      Monitor
                    </button>
                  ) : null}
                  
                  {signal.status && (
                    <span className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded capitalize">
                      {signal.status}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {activeSignals.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <p className="text-xs text-gray-500 dark:text-gray-500 text-center">
            Signals are monitored in real-time. Conditions checked every 5 seconds.
          </p>
        </div>
      )}
    </div>
  )
}
