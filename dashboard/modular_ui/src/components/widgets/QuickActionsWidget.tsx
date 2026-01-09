import React, { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Zap, TrendingUp, TrendingDown, AlertCircle, RefreshCw } from 'lucide-react'
import { RootState } from '../../store'
import { fetchLatestDecision, executeTrade } from '../../store/slices/tradingSlice'
import { useGetAgentStatusQuery } from '../../api/dashboardApi'
import { dashboardApi } from '../../api/dashboardApi'
import axios from 'axios'

export const QuickActionsWidget: React.FC = () => {
  const dispatch = useDispatch()
  const { latestDecision, loading } = useSelector((state: RootState) => state.trading)
  const [executing, setExecuting] = useState(false)
  const { refetch: refetchAgentStatus } = useGetAgentStatusQuery()

  const handleQuickBuy = async () => {
    if (!confirm('Execute quick BUY order?')) return

    setExecuting(true)
    try {
      await dispatch(executeTrade({
        instrument: 'BANKNIFTY',
        side: 'BUY',
        quantity: 1,
        order_type: 'MARKET',
      }) as any)
    } catch (err) {
      console.error('Quick buy failed:', err)
    } finally {
      setExecuting(false)
    }
  }

  const handleQuickSell = async () => {
    if (!confirm('Execute quick SELL order?')) return

    setExecuting(true)
    try {
      await dispatch(executeTrade({
        instrument: 'BANKNIFTY',
        side: 'SELL',
        quantity: 1,
        order_type: 'MARKET',
      }) as any)
    } catch (err) {
      console.error('Quick sell failed:', err)
    } finally {
      setExecuting(false)
    }
  }

  const handleExecuteSignal = async (signalId: string) => {
    if (!confirm('Execute this signal?')) return

    setExecuting(true)
    try {
      await axios.post(`/api/trading/execute/${signalId}`)
      // Refresh decision
      dispatch(fetchLatestDecision() as any)
    } catch (err: any) {
      alert(`Failed to execute signal: ${err.response?.data?.error || err.message}`)
    } finally {
      setExecuting(false)
    }
  }

  const handleRunCycle = async () => {
    setExecuting(true)
    try {
      // Call Engine API via proxy - /api/engine is already configured in vite.config.js
      const response = await axios.post('/api/engine/analyze', {
        instrument: 'BANKNIFTY',
        context: {}
      }, {
        timeout: 30000  // 30 second timeout for analysis
      })
      
      // Wait for analysis to complete and MongoDB to save agent decisions
      await new Promise(resolve => setTimeout(resolve, 2000))
      
      // Refresh decision after cycle
      dispatch(fetchLatestDecision() as any)
      
      // Trigger agent status refresh (wait for MongoDB save)
      setTimeout(() => {
        // Dispatch custom event for AgentStatusWidget to listen
        window.dispatchEvent(new CustomEvent('refresh-agent-status'))
        // Also invalidate RTK Query cache
        dispatch(dashboardApi.util.invalidateTags(['AgentStatus']))
        refetchAgentStatus()
      }, 2500)
      
    } catch (err: any) {
      alert(`Failed to run trading cycle: ${err.response?.data?.error || err.message}`)
    } finally {
      setExecuting(false)
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
          <Zap className="w-5 h-5 mr-2 text-primary-500" />
          Quick Actions
        </h3>
      </div>

      <div className="space-y-3">
        {/* Quick Trade Buttons */}
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={handleQuickBuy}
            disabled={executing}
            className="py-3 px-4 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
          >
            <TrendingUp className="w-4 h-4" />
            Quick BUY
          </button>
          <button
            onClick={handleQuickSell}
            disabled={executing}
            className="py-3 px-4 bg-red-600 hover:bg-red-700 disabled:bg-red-400 text-white rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
          >
            <TrendingDown className="w-4 h-4" />
            Quick SELL
          </button>
        </div>

        {/* Trading Cycle */}
        <button
          onClick={handleRunCycle}
          disabled={executing}
          className="w-full py-2 px-4 bg-primary-600 hover:bg-primary-700 disabled:bg-primary-400 text-white rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
        >
          {executing ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              Running Cycle...
            </>
          ) : (
            <>
              <RefreshCw className="w-4 h-4" />
              Run Trading Cycle
            </>
          )}
        </button>

        {/* Latest Decision */}
        {latestDecision && (
          <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-gray-600 dark:text-gray-400">
                Latest Decision
              </span>
              <span className={`text-xs px-2 py-1 rounded font-semibold ${
                latestDecision.signal === 'BUY'
                  ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                  : latestDecision.signal === 'SELL'
                  ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                  : 'bg-gray-100 dark:bg-gray-600 text-gray-700 dark:text-gray-300'
              }`}>
                {latestDecision.signal}
              </span>
            </div>
            <p className="text-sm text-gray-900 dark:text-white mb-1">
              {latestDecision.instrument}
            </p>
            <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">
              Confidence: {(latestDecision.confidence * 100).toFixed(0)}%
            </p>
            {latestDecision.entry_price && (
              <div className="grid grid-cols-3 gap-2 text-xs mb-2">
                {latestDecision.entry_price && (
                  <div>
                    <span className="text-gray-600 dark:text-gray-400">Entry:</span>
                    <span className="ml-1 font-semibold">₹{latestDecision.entry_price.toFixed(2)}</span>
                  </div>
                )}
                {latestDecision.stop_loss && (
                  <div>
                    <span className="text-gray-600 dark:text-gray-400">SL:</span>
                    <span className="ml-1 font-semibold text-red-600">₹{latestDecision.stop_loss.toFixed(2)}</span>
                  </div>
                )}
                {latestDecision.take_profit && (
                  <div>
                    <span className="text-gray-600 dark:text-gray-400">TP:</span>
                    <span className="ml-1 font-semibold text-green-600">₹{latestDecision.take_profit.toFixed(2)}</span>
                  </div>
                )}
              </div>
            )}
            <button
              onClick={() => {
                // Execute based on decision signal
                if (latestDecision.signal === 'BUY' || latestDecision.signal === 'SELL') {
                  dispatch(executeTrade({
                    instrument: latestDecision.instrument,
                    side: latestDecision.signal,
                    quantity: 1,
                    order_type: 'MARKET',
                    entry_price: latestDecision.entry_price,
                    stop_loss: latestDecision.stop_loss,
                    take_profit: latestDecision.take_profit,
                  }) as any)
                }
              }}
              disabled={executing || latestDecision.signal === 'HOLD'}
              className="w-full py-1.5 px-3 text-xs bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400 text-white rounded font-semibold transition-colors"
            >
              Execute Signal
            </button>
          </div>
        )}

        {/* Info Message */}
        <div className="mt-4 p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-blue-800 dark:text-blue-300">
            Quick actions execute market orders for BANKNIFTY with default quantity. Use Trade Execution for custom orders.
          </p>
        </div>
      </div>
    </div>
  )
}
