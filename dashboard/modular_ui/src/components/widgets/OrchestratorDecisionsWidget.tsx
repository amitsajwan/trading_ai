import React, { useState } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { Crown, TrendingUp, TrendingDown, Minus, Users, CheckCircle, XCircle, Play, Loader2 } from 'lucide-react'
import { RootState } from '../../store'
import { fetchOrchestratorAnalysis } from '../../store/slices/tradingSlice'

export const OrchestratorDecisionsWidget: React.FC = () => {
  const dispatch = useDispatch()
  const { orchestratorDecisions, loading } = useSelector((state: RootState) => state.trading)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const handleRunAnalysis = async () => {
    setIsAnalyzing(true)
    try {
      await dispatch(fetchOrchestratorAnalysis({
        instrument: 'BANKNIFTY',
        context: {}
      }) as any)
    } catch (error) {
      console.error('Failed to run orchestrator analysis:', error)
    } finally {
      setIsAnalyzing(false)
    }
  }

  const getDecisionIcon = (decision: string) => {
    switch (decision.toUpperCase()) {
      case 'BUY':
        return <TrendingUp className="w-5 h-5 text-green-500" />
      case 'SELL':
        return <TrendingDown className="w-5 h-5 text-red-500" />
      default:
        return <Minus className="w-5 h-5 text-gray-500" />
    }
  }

  const getDecisionColor = (decision: string) => {
    if (!decision) return 'bg-gray-50 border-gray-200 dark:bg-gray-900/20 dark:border-gray-800'

    switch (decision.toUpperCase()) {
      case 'BUY':
        return 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
      case 'SELL':
        return 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
      case 'IRON_CONDOR':
      case 'BULL_CALL_SPREAD':
      case 'BEAR_PUT_SPREAD':
        return 'bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800'
      default:
        return 'bg-gray-50 border-gray-200 dark:bg-gray-900/20 dark:border-gray-800'
    }
  }

  if (loading.orchestrator) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Orchestrator Decisions</h3>
        <div className="animate-pulse">
          <div className="h-24 bg-gray-200 dark:bg-gray-700 rounded mb-3"></div>
          <div className="h-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Orchestrator Decisions</h3>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Research-First Architecture: EnhancedResearchManager → Supporting Agents → Risk Assessment
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={handleRunAnalysis}
            disabled={isAnalyzing}
            className="flex items-center px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-md transition-colors"
          >
            {isAnalyzing ? (
              <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
            ) : (
              <Play className="w-4 h-4 mr-1.5" />
            )}
            {isAnalyzing ? 'Analyzing...' : 'Run Analysis'}
          </button>
          <div className="flex items-center space-x-2">
            <Crown className="w-4 h-4 text-yellow-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {orchestratorDecisions.length} research decisions
            </span>
          </div>
        </div>
      </div>

      <div className="space-y-4 max-h-96 overflow-y-auto">
        {orchestratorDecisions.length === 0 ? (
          <div className="text-center text-gray-500 dark:text-gray-400 py-8">
            <Crown className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No orchestrator decisions received yet</p>
            <p className="text-xs mt-1">Waiting for agent analysis aggregation</p>
          </div>
        ) : (
          orchestratorDecisions.map((decision) => (
            <div
              key={decision.decision_id}
              className={`p-4 rounded-lg border ${getDecisionColor(decision.final_decision)}`}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-3">
                  {getDecisionIcon(decision.final_decision)}
                  <div>
                    <div className="font-semibold text-gray-900 dark:text-white">
                      {decision.final_decision} {decision.instrument}
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      Confidence: {(decision.confidence * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  {decision.signal_created ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-gray-400" />
                  )}
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {new Date(decision.timestamp).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })}
                  </span>
                </div>
              </div>

              {decision.reasoning && (
                <div className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                  {decision.reasoning}
                </div>
              )}

              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Users className="w-4 h-4 text-blue-500" />
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    {decision.agent_responses.length} agent responses aggregated
                  </span>
                </div>
                {decision.signal_id && (
                  <div className="text-xs text-blue-600 dark:text-blue-400">
                    Signal ID: {decision.signal_id}
                  </div>
                )}
              </div>

              {/* Research-First Agent Hierarchy */}
              <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-2 flex items-center">
                  <Crown className="w-3 h-3 mr-1 text-yellow-500" />
                  Research-First Hierarchy:
                </div>
                <div className="space-y-2">
                  {/* Research Manager (Primary) */}
                  {decision.agent_responses
                    .filter(response => response.agent === 'EnhancedResearchManager')
                    .map((response, index) => (
                      <div key={`research-${index}`} className="flex items-center justify-between bg-gradient-to-r from-yellow-50 to-amber-50 dark:from-yellow-900/20 dark:to-amber-900/20 p-2 rounded border border-yellow-200 dark:border-yellow-700">
                        <div className="flex items-center space-x-2">
                          <Crown className="w-4 h-4 text-yellow-600" />
                          <span className="text-sm font-semibold text-yellow-800 dark:text-yellow-200">PRIMARY: {response.agent}</span>
                        </div>
                        <div className="text-sm font-medium text-yellow-700 dark:text-yellow-300">
                          {response.decision} ({(response.confidence * 100).toFixed(0)}%)
                        </div>
                      </div>
                    ))}

                  {/* Supporting Agents */}
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Supporting Agents:</div>
                  <div className="flex flex-wrap gap-1">
                    {decision.agent_responses
                      .filter(response => response.agent !== 'EnhancedResearchManager')
                      .map((response, index) => (
                        <span
                          key={`supporting-${index}`}
                          className={`px-2 py-1 rounded text-xs ${
                            response.decision === decision.final_decision
                              ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 border border-green-300'
                              : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                          }`}
                        >
                          {response.agent}: {response.decision} ({(response.confidence * 100).toFixed(0)}%)
                        </span>
                      ))}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}