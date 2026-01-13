import React from 'react'
import { useSelector } from 'react-redux'
import { TrendingUp, TrendingDown, Minus, Brain, AlertCircle } from 'lucide-react'
import { RootState } from '../../store'

export const AgentResponsesWidget: React.FC = () => {
  const { agentResponses, loading } = useSelector((state: RootState) => state.trading)

  const getDecisionIcon = (decision: string) => {
    switch (decision.toUpperCase()) {
      case 'BUY':
        return <TrendingUp className="w-4 h-4 text-green-500" />
      case 'SELL':
        return <TrendingDown className="w-4 h-4 text-red-500" />
      default:
        return <Minus className="w-4 h-4 text-gray-500" />
    }
  }

  const getDecisionColor = (decision: string) => {
    switch (decision.toUpperCase()) {
      case 'BUY':
        return 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
      case 'SELL':
        return 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
      default:
        return 'bg-gray-50 border-gray-200 dark:bg-gray-900/20 dark:border-gray-800'
    }
  }

  if (loading.agentResponses) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Agent Responses</h3>
        <div className="animate-pulse">
          <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded mb-3"></div>
          <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded mb-3"></div>
          <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Agent Responses</h3>
        <div className="flex items-center space-x-2">
          <Brain className="w-4 h-4 text-blue-500" />
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {agentResponses.length} responses
          </span>
        </div>
      </div>

      <div className="space-y-3 max-h-96 overflow-y-auto">
        {agentResponses.length === 0 ? (
          <div className="text-center text-gray-500 dark:text-gray-400 py-8">
            <Brain className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No agent responses received yet</p>
            <p className="text-xs mt-1">Waiting for agents to analyze market conditions</p>
          </div>
        ) : (
          agentResponses.slice(0, 10).map((response, index) => (
            <div
              key={`${response.agent}-${response.timestamp}-${index}`}
              className={`p-3 rounded-lg border ${getDecisionColor(response.decision)}`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  {getDecisionIcon(response.decision)}
                  <span className="font-medium text-gray-900 dark:text-white">
                    {response.agent}
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    response.confidence > 0.7
                      ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                      : response.confidence > 0.5
                      ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                      : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                  }`}>
                    {(response.confidence * 100).toFixed(0)}%
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {new Date(response.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              </div>

              {response.details?.reasoning && (
                <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                  {response.details.reasoning}
                </div>
              )}

              <div className="flex flex-wrap gap-2 text-xs">
                {response.details?.entry_price && (
                  <span className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 px-2 py-1 rounded">
                    Entry: ₹{response.details.entry_price}
                  </span>
                )}
                {response.details?.stop_loss && (
                  <span className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200 px-2 py-1 rounded">
                    Stop: ₹{response.details.stop_loss}
                  </span>
                )}
                {response.details?.take_profit && (
                  <span className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 px-2 py-1 rounded">
                    Target: ₹{response.details.take_profit}
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {agentResponses.length > 10 && (
        <div className="mt-4 text-center">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            Showing latest 10 responses ({agentResponses.length - 10} more available)
          </span>
        </div>
      )}
    </div>
  )
}