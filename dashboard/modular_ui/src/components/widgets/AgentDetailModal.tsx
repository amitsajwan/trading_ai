import React from 'react'
import { X, TrendingUp, TrendingDown, Minus, BarChart3, Target, AlertTriangle } from 'lucide-react'
import { AgentStatus } from '../../store/slices/tradingSlice'

interface AgentDetailModalProps {
  agent: AgentStatus | null
  isOpen: boolean
  onClose: () => void
}

export const AgentDetailModal: React.FC<AgentDetailModalProps> = ({ agent, isOpen, onClose }) => {
  if (!isOpen || !agent) return null

  const getDecisionIcon = (decision?: string) => {
    switch (decision?.toUpperCase()) {
      case 'BUY':
        return <TrendingUp className="w-6 h-6 text-green-500" />
      case 'SELL':
        return <TrendingDown className="w-6 h-6 text-red-500" />
      default:
        return <Minus className="w-6 h-6 text-gray-500" />
    }
  }

  const getDecisionColor = (decision?: string) => {
    switch (decision?.toUpperCase()) {
      case 'BUY':
        return 'text-green-600 bg-green-50 dark:bg-green-900/20'
      case 'SELL':
        return 'text-red-600 bg-red-50 dark:bg-red-900/20'
      default:
        return 'text-gray-600 bg-gray-50 dark:bg-gray-900/20'
    }
  }

  const formatIndicatorValue = (key: string, value: any): string => {
    if (value === null || value === undefined) return 'N/A'

    // Format based on indicator type
    if (key.includes('price') || key.includes('value')) {
      return typeof value === 'number' ? value.toFixed(2) : String(value)
    }
    if (key.includes('ratio') || key.includes('percentage')) {
      return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : String(value)
    }
    if (key.includes('rsi') || key.includes('adx') || key.includes('atr')) {
      return typeof value === 'number' ? value.toFixed(2) : String(value)
    }

    return String(value)
  }

  const getIndicatorDescription = (key: string): string => {
    const descriptions: Record<string, string> = {
      'rsi_14': 'Relative Strength Index (14-period)',
      'macd_value': 'MACD line value',
      'macd_signal': 'MACD signal line',
      'macd_histogram': 'MACD histogram',
      'bollinger_upper': 'Bollinger Band upper limit',
      'bollinger_middle': 'Bollinger Band middle (SMA)',
      'bollinger_lower': 'Bollinger Band lower limit',
      'atr_14': 'Average True Range (14-period)',
      'adx_14': 'Average Directional Index (14-period)',
      'sma_20': 'Simple Moving Average (20-period)',
      'ema_20': 'Exponential Moving Average (20-period)',
      'support_level': 'Calculated support level',
      'resistance_level': 'Calculated resistance level',
      'trend_direction': 'Current trend direction',
      'trend_strength': 'Trend strength percentage'
    }

    return descriptions[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-lg ${getDecisionColor(agent.signal)}`}>
              {getDecisionIcon(agent.signal)}
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">{agent.name}</h2>
              <p className="text-sm text-gray-600 dark:text-gray-400">Detailed Analysis</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Current Decision */}
          <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-3">Current Decision</h3>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                {getDecisionIcon(agent.signal)}
                <span className="text-xl font-bold text-gray-900 dark:text-white">{agent.signal || 'HOLD'}</span>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-gray-900 dark:text-white">
                  {agent.confidence ? (agent.confidence * 100).toFixed(1) : '0.0'}%
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Confidence</div>
              </div>
            </div>
          </div>

          {/* Technical Indicators */}
          {agent.technical_indicators && Object.keys(agent.technical_indicators).length > 0 && (
            <div>
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-3 flex items-center">
                <BarChart3 className="w-5 h-5 mr-2" />
                Technical Indicators
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {Object.entries(agent.technical_indicators).map(([key, value]) => (
                  <div key={key} className="bg-gray-50 dark:bg-gray-700 p-3 rounded">
                    <div className="text-sm font-medium text-gray-900 dark:text-white">
                      {getIndicatorDescription(key)}
                    </div>
                    <div className="text-lg font-bold text-blue-600 dark:text-blue-400 mt-1">
                      {formatIndicatorValue(key, value)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Reasoning */}
          {agent.reasoning && (
            <div>
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-3 flex items-center">
                <Target className="w-5 h-5 mr-2" />
                Analysis Reasoning
              </h3>
              <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                  {agent.reasoning}
                </p>
              </div>
            </div>
          )}

          {/* Additional Details */}
          {agent.summary && typeof agent.summary === 'object' && (
            <div>
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-3">Additional Details</h3>
              <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                <pre className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                  {JSON.stringify(agent.summary, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {/* Cycle Information */}
          {agent.cycle_info && (
            <div>
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-3">Analysis Cycle</h3>
              <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium text-gray-600 dark:text-gray-400">Cycle:</span>
                    <span className="ml-2 text-gray-900 dark:text-white">#{agent.cycle_info.cycle_number || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="font-medium text-gray-600 dark:text-gray-400">Duration:</span>
                    <span className="ml-2 text-gray-900 dark:text-white">
                      {agent.cycle_info.duration_seconds ? `${agent.cycle_info.duration_seconds.toFixed(1)}s` : 'N/A'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center p-6 border-t border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Last updated: {agent.last_update ? new Date(agent.last_update).toLocaleString() : 'Never'}
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}