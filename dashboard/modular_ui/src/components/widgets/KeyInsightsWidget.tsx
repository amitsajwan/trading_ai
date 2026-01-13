import React from 'react'
import { useSelector } from 'react-redux'
import { Lightbulb, TrendingUp, TrendingDown, AlertTriangle, Target, BarChart3 } from 'lucide-react'
import { RootState } from '../../store'

export const KeyInsightsWidget: React.FC = () => {
  const { latestDecision, loading } = useSelector((state: RootState) => state.trading)

  // Extract key insights from the latest decision
  const keyInsights = React.useMemo(() => {
    if (!latestDecision?.details?.aggregated_analysis?.key_insights) {
      return []
    }
    return latestDecision.details.aggregated_analysis.key_insights
  }, [latestDecision])

  const marketRegime = latestDecision?.details?.aggregated_analysis?.consensus_direction || 'UNKNOWN'
  const riskAssessment = latestDecision?.details?.aggregated_analysis?.risk_assessment || 'UNKNOWN'

  const getRegimeIcon = (regime: string) => {
    switch (regime.toUpperCase()) {
      case 'BUY':
        return <TrendingUp className="w-5 h-5 text-green-500" />
      case 'SELL':
        return <TrendingDown className="w-5 h-5 text-red-500" />
      case 'HOLD':
        return <Target className="w-5 h-5 text-yellow-500" />
      default:
        return <AlertTriangle className="w-5 h-5 text-gray-500" />
    }
  }

  const getRegimeColor = (regime: string) => {
    switch (regime.toUpperCase()) {
      case 'BUY':
        return 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
      case 'SELL':
        return 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
      case 'HOLD':
        return 'bg-yellow-50 border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800'
      default:
        return 'bg-gray-50 border-gray-200 dark:bg-gray-900/20 dark:border-gray-800'
    }
  }

  const getRiskColor = (risk: string) => {
    if (risk.toUpperCase().includes('LOW')) {
      return 'text-green-600 dark:text-green-400'
    } else if (risk.toUpperCase().includes('HIGH')) {
      return 'text-red-600 dark:text-red-400'
    }
    return 'text-yellow-600 dark:text-yellow-400'
  }

  if (loading.decision) {
    return (
      <section aria-labelledby="insights-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 id="insights-heading" className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Market Intelligence</h3>
        <div className="animate-pulse">
          <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded mb-3"></div>
          <div className="h-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </section>
    )
  }

  return (
    <section aria-labelledby="insights-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 id="insights-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Market Intelligence</h3>
        <div className="flex items-center space-x-2">
          <Lightbulb className="w-4 h-4 text-yellow-500" />
          <span className="text-xs text-gray-500 dark:text-gray-400">AI Analysis</span>
        </div>
      </div>

      {/* Market Regime Summary */}
      <div className={`p-4 rounded-lg border mb-4 ${getRegimeColor(marketRegime)}`}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            {getRegimeIcon(marketRegime)}
            <span className="font-semibold text-gray-900 dark:text-white">Market Regime</span>
          </div>
          <span className="text-sm font-medium text-gray-900 dark:text-white">{marketRegime}</span>
        </div>
        <div className="text-sm text-gray-600 dark:text-gray-400">
          Risk Assessment: <span className={`font-medium ${getRiskColor(riskAssessment)}`}>{riskAssessment}</span>
        </div>
      </div>

      {/* Key Insights */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-gray-900 dark:text-white flex items-center">
          <BarChart3 className="w-4 h-4 mr-2" />
          Key Insights
        </h4>

        {keyInsights.length > 0 ? (
          <div className="space-y-2">
            {keyInsights.map((insight: string, index: number) => (
              <div key={index} className="flex items-start space-x-2 p-3 bg-gray-50 dark:bg-gray-700 rounded">
                <div className="flex-shrink-0 w-2 h-2 bg-blue-500 rounded-full mt-2"></div>
                <p className="text-sm text-gray-700 dark:text-gray-300">{insight}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center text-gray-500 dark:text-gray-400 py-6">
            <Lightbulb className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No insights available yet</p>
            <p className="text-xs mt-1">Insights will appear after AI analysis</p>
          </div>
        )}
      </div>

      {/* Last Analysis Timestamp */}
      {latestDecision?.timestamp && (
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
          <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
            <span>Last analysis:</span>
            <span>{new Date(latestDecision.timestamp).toLocaleString()}</span>
          </div>
        </div>
      )}
    </section>
  )
}