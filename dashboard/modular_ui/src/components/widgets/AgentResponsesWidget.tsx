import React from 'react'
import { useSelector } from 'react-redux'
import { AlertCircle, Brain, Minus, TrendingDown, TrendingUp } from 'lucide-react'
import { RootState } from '../../store'
import { getAgentCommentary } from '../../utils/agentNarrative'

interface AgentResponsesWidgetProps {
  currentRunOnly?: boolean
}

const formatTime = (ts?: string) => {
  if (!ts) return '-'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return '-'
  return d.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  })
}

const getDecisionIcon = (decision?: string) => {
  switch ((decision || '').toUpperCase()) {
    case 'BUY':
      return <TrendingUp className="w-4 h-4 text-green-500" />
    case 'SELL':
      return <TrendingDown className="w-4 h-4 text-red-500" />
    default:
      return <Minus className="w-4 h-4 text-gray-500" />
  }
}

const getDecisionColor = (decision?: string) => {
  switch ((decision || '').toUpperCase()) {
    case 'BUY':
      return 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
    case 'SELL':
      return 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
    case 'EXCLUDED':
      return 'bg-amber-50 border-amber-200 dark:bg-amber-900/20 dark:border-amber-800'
    default:
      return 'bg-gray-50 border-gray-200 dark:bg-gray-900/20 dark:border-gray-800'
  }
}

export const AgentResponsesWidget: React.FC<AgentResponsesWidgetProps> = ({ currentRunOnly = false }) => {
  const { agentResponses, loading } = useSelector((state: RootState) => state.trading)
  const currentRunId = useSelector((state: RootState) => state.ui.executionMode.runId)

  if (loading.agentResponses) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Agent Responses</h3>
        <div className="animate-pulse space-y-3">
          <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded" />
        </div>
      </div>
    )
  }

  const filtered = currentRunOnly && currentRunId
    ? agentResponses.filter((r: any) => String(r?.run_id || '').trim() === currentRunId)
    : agentResponses

  const recent = [...filtered]
    .sort((a, b) => new Date(b.timestamp || 0).getTime() - new Date(a.timestamp || 0).getTime())
    .slice(0, 12)

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Agent Responses</h3>
        <div className="flex items-center space-x-2 text-xs text-gray-500 dark:text-gray-400">
          <Brain className="w-4 h-4 text-blue-500" />
          <span>{filtered.length} responses{currentRunOnly && currentRunId ? ` in ${currentRunId}` : ''}</span>
        </div>
      </div>

      <div className="space-y-3 max-h-96 overflow-y-auto">
        {recent.length === 0 ? (
          <div className="text-center text-gray-500 dark:text-gray-400 py-8">
            <Brain className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No agent responses received yet</p>
            <p className="text-xs mt-1">Waiting for analysis cycle completion</p>
          </div>
        ) : (
          recent.map((response, index) => {
            const excluded = (response as any).excluded || response.decision?.toUpperCase() === 'EXCLUDED'
            return (
              <div
                key={`${response.agent || 'agent'}-${response.timestamp || 'ts'}-${index}`}
                className={`p-3 rounded-lg border ${getDecisionColor(response.decision)}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    {getDecisionIcon(response.decision)}
                    <span className="font-medium text-gray-900 dark:text-white">{response.agent || 'Unknown Agent'}</span>
                    {excluded && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">
                        <AlertCircle className="w-3 h-3 mr-1" />
                        Excluded
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{formatTime(response.timestamp)}</div>
                </div>

                <div className="flex items-center justify-between text-sm mb-2">
                  <div className="text-gray-700 dark:text-gray-300">
                    Decision: <span className="font-semibold">{response.decision || 'N/A'}</span>
                  </div>
                  <div className="text-gray-700 dark:text-gray-300">
                    Confidence: <span className="font-semibold">{((response.confidence || 0) * 100).toFixed(0)}%</span>
                  </div>
                </div>

                {((response as any).run_id || (response as any).cycle_id) && (
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                    Run: {(response as any).run_id || '-'} {(response as any).cycle_id ? `| Cycle: ${(response as any).cycle_id}` : ''}
                  </div>
                )}

                <div className="text-sm text-gray-600 dark:text-gray-400 line-clamp-3">
                  {getAgentCommentary(response) || 'Commentary not provided by agent.'}
                </div>
              </div>
            )
          })
        )}
      </div>

      {filtered.length > 12 && (
        <div className="mt-3 text-center text-xs text-gray-500 dark:text-gray-400">Showing latest 12 responses</div>
      )}
    </div>
  )
}
