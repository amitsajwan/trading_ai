import React from 'react'
import { useSelector } from 'react-redux'
import { TrendingUp, TrendingDown, Minus, Brain, AlertCircle } from 'lucide-react'
import { RootState } from '../../store'

export const AgentResponsesWidget: React.FC = () => {
  const { agentResponses, loading } = useSelector((state: RootState) => state.trading)

  // Debug logging
  React.useEffect(() => {
    if (agentResponses.length > 0) {
      console.log('AgentResponsesWidget: Received', agentResponses.length, 'agent responses')
      console.log('AgentResponsesWidget: First agent sample:', agentResponses[0])

      // Check what reasoning data looks like
      agentResponses.slice(0, 5).forEach((response, i) => {
        console.log(`Agent ${i+1} (${response.agent}):`, {
          decision: response.decision,
          confidence: response.confidence,
          detailsKeys: Object.keys(response.details || {}),
          reasoning: response.details?.reasoning,
          reasoningType: typeof response.details?.reasoning,
          research_plan: response.details?.research_plan,
          debate_summary: response.details?.debate_summary
        })
      })
    }
  }, [agentResponses])

  const getDecisionIcon = (decision: string | undefined) => {
    if (!decision) return <Minus className="w-4 h-4 text-gray-500" />
    switch (decision.toUpperCase()) {
      case 'BUY':
        return <TrendingUp className="w-4 h-4 text-green-500" />
      case 'SELL':
        return <TrendingDown className="w-4 h-4 text-red-500" />
      default:
        return <Minus className="w-4 h-4 text-gray-500" />
    }
  }

  const getDecisionColor = (decision: string | undefined) => {
    if (!decision) return 'bg-gray-50 border-gray-200 dark:bg-gray-900/20 dark:border-gray-800'
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
                    {response.agent || 'Unknown Agent'}
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    response.decision && response.confidence !== undefined ? (
                      response.confidence > 0.7
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : response.confidence > 0.5
                        ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                        : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                    ) : 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
                  }`}>
                    {response.decision && response.confidence !== undefined ? (response.confidence * 100).toFixed(0) + '%' : 'N/A'}
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {response.timestamp ? new Date(response.timestamp).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' }) : '—'}
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
                    {new Date(response.timestamp).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })}
                  </span>
                </div>
              </div>

              {response.details && (
                <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                  {(() => {
                    const details = response.details;

                    // Handle different reasoning formats from agents
                    if (details.reasoning) {
                      if (Array.isArray(details.reasoning)) {
                        return details.reasoning.join('. ');
                      }
                      // Skip generic "Decision made" - fall back to other fields
                      if (details.reasoning !== "Decision made") {
                        return details.reasoning;
                      }
                    }

                    // Fallback to other meaningful fields
                    if (details.decision_basis) {
                      return `Decision basis: ${details.decision_basis}`;
                    }

                    if (details.thesis) {
                      return `Thesis: ${details.thesis}`;
                    }

                    if (details.note) {
                      return `Note: ${details.note}`;
                    }

                    if (details.status) {
                      return `Status: ${details.status}`;
                    }

                    // For complex nested structures, try to extract meaningful info
                    if (details.research_plan) {
                      return `Plan: ${details.research_plan}`;
                    }

                    if (details.debate_summary?.summary) {
                      return `Debate: ${details.debate_summary.summary}`;
                    }

                    if (details.bull_thesis?.thesis && details.bear_thesis?.thesis) {
                      return `Bull: ${details.bull_thesis.thesis.substring(0, 30)}... Bear: ${details.bear_thesis.thesis.substring(0, 30)}...`;
                    }

                    if (details.strategy) {
                      return `Strategy: ${details.strategy}`;
                    }

                    // Last resort - show a summary of available fields
                    const keys = Object.keys(details).filter(key => key !== 'agent' && key !== 'timestamp');
                    if (keys.length > 0) {
                      return `Analysis includes: ${keys.slice(0, 3).join(', ')}${keys.length > 3 ? '...' : ''}`;
                    }

                    return 'Analysis completed';
                  })()}
                </div>
              )}

              {/* Show input data used for analysis */}
              {response.input_data && (
                <div className="text-xs text-gray-500 dark:text-gray-500 mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                  <div className="font-medium mb-1">Analysis Inputs:</div>
                  <div className="space-y-1">
                    {(() => {
                      const inputData = response.input_data;
                      const inputLines = [];

                      // Show different input data based on agent type
                      if (inputData.technical_indicators_available) {
                        inputLines.push(`Technical Indicators: ${inputData.technical_indicators_available.join(', ')}`);
                      }
                      if (inputData.current_price) {
                        inputLines.push(`Current Price: ₹${inputData.current_price}`);
                      }
                      if (inputData.rsi_value !== undefined) {
                        inputLines.push(`RSI: ${inputData.rsi_value?.toFixed(1)}`);
                      }
                      if (inputData.earnings_surprise !== undefined) {
                        inputLines.push(`Earnings Surprise: ${inputData.earnings_surprise?.toFixed(1)}%`);
                      }
                      if (inputData.revenue_growth !== undefined) {
                        inputLines.push(`Revenue Growth: ${inputData.revenue_growth?.toFixed(1)}%`);
                      }
                      if (inputData.pe_ratio !== undefined) {
                        inputLines.push(`P/E Ratio: ${inputData.pe_ratio?.toFixed(1)}`);
                      }
                      if (inputData.roe !== undefined) {
                        inputLines.push(`ROE: ${inputData.roe?.toFixed(1)}%`);
                      }

                      // Show error information if any
                      if (inputData.error_occurred) {
                        inputLines.push("⚠️ Analysis Error Occurred");
                      }
                      if (inputData.technical_indicators_available?.length === 0) {
                        inputLines.push("⚠️ No Technical Indicators Available");
                      }

                      return inputLines.map((line, idx) => (
                        <div key={idx}>{line}</div>
                      ));
                    })()}
                  </div>
                </div>
              )}

              <div className="flex flex-wrap gap-2 text-xs">
                {response.details?.entry_price && (
                  <span className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 px-2 py-1 rounded">
                    Entry: ₹{response.details.entry_price.toFixed(2)}
                  </span>
                )}
                {response.details?.stop_loss && (
                  <span className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200 px-2 py-1 rounded">
                    Stop: ₹{response.details.stop_loss.toFixed(2)}
                  </span>
                )}
                {response.details?.take_profit && (
                  <span className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 px-2 py-1 rounded">
                    Target: ₹{response.details.take_profit.toFixed(2)}
                  </span>
                )}

                {/* Technical indicators */}
                {response.details?.rsi !== undefined && response.details.rsi !== null && (
                  <span className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200 px-2 py-1 rounded">
                    RSI: {Number(response.details.rsi).toFixed(1)}
                  </span>
                )}
                {response.details?.rsi_status && (
                  <span className="bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200 px-2 py-1 rounded">
                    {response.details.rsi_status}
                  </span>
                )}
                {response.details?.trend_direction && (
                  <span className="bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200 px-2 py-1 rounded">
                    {response.details.trend_direction}
                  </span>
                )}

                {/* Strategy-specific info */}
                {response.details?.strategy && (
                  <span className="bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200 px-2 py-1 rounded">
                    {response.details.strategy.replace('_', ' ')}
                  </span>
                )}
                {response.details?.macro_regime && (
                  <span className="bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200 px-2 py-1 rounded">
                    {response.details.macro_regime}
                  </span>
                )}

                <div className="ml-auto">
                  <a className="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700" href={`/agents/${encodeURIComponent(response.agent) }?response=${encodeURIComponent(response._id || response.response_id || '')}`}>
                    Open in Agent Page
                  </a>
                </div>

                {/* Risk assessment */}
                {response.details?.risk && (
                  <span className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200 px-2 py-1 rounded">
                    Risk: {response.details.risk}
                  </span>
                )}

                {/* Research Manager specific fields */}
                {response.details?.debate_summary?.bull_confidence !== undefined && (
                  <span className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 px-2 py-1 rounded">
                    Bull: {(response.details.debate_summary.bull_confidence * 100).toFixed(0)}%
                  </span>
                )}
                {response.details?.debate_summary?.bear_confidence !== undefined && (
                  <span className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200 px-2 py-1 rounded">
                    Bear: {(response.details.debate_summary.bear_confidence * 100).toFixed(0)}%
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