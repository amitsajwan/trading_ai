import React from 'react'
import { useSelector } from 'react-redux'
import { History, TrendingUp, TrendingDown, DollarSign, Target, AlertTriangle } from 'lucide-react'
import { RootState } from '../../store'
import { formatTimestampForDisplay } from '../../utils/dateUtils'

export const TradeHistoryWidget: React.FC = () => {
  const { recentTrades, signals, loading } = useSelector((state: RootState) => state.trading)

  // Link trades to signals
  const tradesWithSignals = React.useMemo(() => {
    return recentTrades.map(trade => {
      const relatedSignal = signals.find(signal => signal.signal_id === trade.signal_id)
      return {
        ...trade,
        signal: relatedSignal
      }
    }).slice(0, 20) // Show last 20 trades
  }, [recentTrades, signals])

  const getTradeIcon = (side: string) => {
    return side === 'BUY'
      ? <TrendingUp className="w-4 h-4 text-green-500" />
      : <TrendingDown className="w-4 h-4 text-red-500" />
  }

  const getTradeColor = (side: string, pnl?: number) => {
    if (pnl !== undefined && pnl !== 0) {
      return pnl > 0
        ? 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
        : 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
    }
    return side === 'BUY'
      ? 'bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800'
      : 'bg-orange-50 border-orange-200 dark:bg-orange-900/20 dark:border-orange-800'
  }

  if (loading.trades) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Trade History</h3>
        <div className="animate-pulse">
          <div className="h-16 bg-gray-200 dark:bg-gray-700 rounded mb-3"></div>
          <div className="h-16 bg-gray-200 dark:bg-gray-700 rounded mb-3"></div>
          <div className="h-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Trade History</h3>
        <div className="flex items-center space-x-2">
          <History className="w-4 h-4 text-gray-500" />
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {tradesWithSignals.length} trades
          </span>
        </div>
      </div>

      <div className="space-y-3 max-h-96 overflow-y-auto">
        {tradesWithSignals.length === 0 ? (
          <div className="text-center text-gray-500 dark:text-gray-400 py-8">
            <History className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No trades executed yet</p>
            <p className="text-xs mt-1">Trades will appear here when signals are executed</p>
          </div>
        ) : (
          tradesWithSignals.map((trade, index) => (
            <div
              key={`${trade.id}-${index}`}
              className={`p-3 rounded-lg border ${getTradeColor(trade.side, trade.pnl)}`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  {getTradeIcon(trade.side)}
                  <div>
                    <div className="font-medium text-gray-900 dark:text-white">
                      {trade.side} {trade.instrument}
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      {trade.quantity} shares @ ₹{trade.price.toFixed(2)}
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  {trade.pnl !== undefined && (
                    <div className={`text-sm font-medium ${
                      trade.pnl > 0 ? 'text-green-600' : trade.pnl < 0 ? 'text-red-600' : 'text-gray-600'
                    }`}>
                      {trade.pnl > 0 ? '+' : ''}₹{trade.pnl.toFixed(2)}
                    </div>
                  )}
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {formatTimestampForDisplay(trade.timestamp)}
                  </div>
                </div>
              </div>

              {trade.signal && (
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                  <div className="flex items-center space-x-2">
                    <Target className="w-3 h-3 text-blue-500" />
                    <span className="text-xs text-gray-600 dark:text-gray-400">
                      Signal: {trade.signal.action} ({(trade.signal.confidence * 100).toFixed(0)}%)
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    ID: {trade.signal_id}
                  </div>
                </div>
              )}

              {trade.exit_price && (
                <div className="mt-2 text-xs text-gray-600 dark:text-gray-400">
                  Exit: ₹{trade.exit_price} on {trade.exit_timestamp ? new Date(trade.exit_timestamp).toLocaleDateString() : '—'}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {tradesWithSignals.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
          <div className="grid grid-cols-3 gap-4 text-xs text-gray-600 dark:text-gray-400">
            <div className="text-center">
              <div className="font-medium text-gray-900 dark:text-white">
                {tradesWithSignals.filter(t => t.pnl && t.pnl > 0).length}
              </div>
              <div>Winning Trades</div>
            </div>
            <div className="text-center">
              <div className="font-medium text-gray-900 dark:text-white">
                ₹{tradesWithSignals.reduce((sum, t) => sum + (t.pnl || 0), 0).toFixed(2)}
              </div>
              <div>Total P&L</div>
            </div>
            <div className="text-center">
              <div className="font-medium text-gray-900 dark:text-white">
                {((tradesWithSignals.filter(t => t.pnl && t.pnl > 0).length / Math.max(tradesWithSignals.length, 1)) * 100).toFixed(0)}%
              </div>
              <div>Win Rate</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}