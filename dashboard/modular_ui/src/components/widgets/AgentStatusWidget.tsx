import React from 'react'
import { useSelector } from 'react-redux'
import { RootState } from '../../store'

interface AgentStatusWidgetProps {
  onAgentClick?: (agent: any) => void
}

export const AgentStatusWidget: React.FC<AgentStatusWidgetProps> = ({ onAgentClick }) => {
  const { agentStatuses, agentResponses, loading } = useSelector((state: RootState) => state.trading)

  // Combine agent statuses with latest responses
  const enrichedAgentStatuses = React.useMemo(() => {
    const statusMap = new Map(agentStatuses.map(status => [status.name, status]))

    // Add any agents from responses that aren't in statuses
    agentResponses.forEach(response => {
      if (!statusMap.has(response.agent)) {
        statusMap.set(response.agent, {
          name: response.agent,
          status: 'active' as const,
          last_update: response.timestamp,
          signal: response.decision,
          confidence: response.confidence,
          summary: response.details
        })
      } else {
        // Update existing status with latest response data
        const existing = statusMap.get(response.agent)!
        existing.last_update = response.timestamp
        existing.signal = response.decision
        existing.confidence = response.confidence
        existing.summary = response.details
      }
    })

    return Array.from(statusMap.values())
  }, [agentStatuses, agentResponses])

  if (loading.agents || loading.agentResponses) {
    return (
      <section aria-labelledby="agent-status-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 id="agent-status-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Agent Status</h3>
        <div className="mt-4 animate-pulse">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-2"></div>
          <div className="h-24 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </section>
    )
  }

  return (
    <section aria-labelledby="agent-status-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between">
        <h3 id="agent-status-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Agent Status</h3>
        <div className="text-xs text-green-600 dark:text-green-400">
          {enrichedAgentStatuses.length} agents active
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {enrichedAgentStatuses.map((agent) => (
          <div
            key={agent.name}
            className="p-3 bg-gray-50 dark:bg-gray-700 rounded cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
            onClick={() => onAgentClick?.(agent)}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-medium text-gray-900 dark:text-white">{agent.name}</div>
              <div className={`px-2 py-1 rounded-full text-xs font-medium ${
                agent.status === 'active'
                  ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                  : agent.status === 'error'
                  ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                  : 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
              }`}>
                {agent.status}
              </div>
            </div>
            <div className="space-y-1 text-xs text-gray-600 dark:text-gray-400">
              {agent.signal && (
                <div>Decision: <span className="font-medium">{agent.signal}</span></div>
              )}
              {agent.confidence !== undefined && (
                <div>Confidence: <span className="font-medium">{(agent.confidence * 100).toFixed(0)}%</span></div>
              )}

              {/* Show key technical indicators */}
              {agent.technical_indicators && (
                <div className="mt-1 pt-1 border-t border-gray-200 dark:border-gray-600">
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Key Indicators:</div>
                  {agent.technical_indicators.rsi_14 !== undefined && (
                    <div>RSI(14): {(agent.technical_indicators.rsi_14).toFixed(1)}</div>
                  )}
                  {agent.technical_indicators.macd_value !== undefined && (
                    <div>MACD: {agent.technical_indicators.macd_value.toFixed(3)}</div>
                  )}
                  {agent.technical_indicators.atr_14 !== undefined && (
                    <div>ATR(14): {agent.technical_indicators.atr_14.toFixed(2)}</div>
                  )}
                </div>
              )}

              {/* Show reasoning if available */}
              {agent.reasoning && agent.reasoning.length > 0 && (
                <div className="mt-1 pt-1 border-t border-gray-200 dark:border-gray-600">
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Analysis:</div>
                  <div className="text-xs italic truncate max-w-32" title={agent.reasoning}>
                    {agent.reasoning.length > 25 ? `${agent.reasoning.substring(0, 25)}...` : agent.reasoning}
                  </div>
                </div>
              )}

              <div>Last update: {agent.last_update ? new Date(agent.last_update).toLocaleTimeString() : '—'}</div>
            </div>
          </div>
        ))}
      </div>

      {enrichedAgentStatuses.length === 0 && (
        <div className="mt-4 text-center text-gray-500 dark:text-gray-400 py-8">
          <div className="text-4xl mb-2">🤖</div>
          <p>No agent data received yet</p>
          <p className="text-xs mt-1">Waiting for orchestrator to send agent updates</p>
        </div>
      )}
    </section>
  )
}
