import React from 'react'
import { CheckCircle, XCircle, AlertCircle, Clock } from 'lucide-react'
import { useGetApprovalHistoryQuery, useGetApprovalStatsQuery } from '../../api/dashboardApi'

export const ApprovalHistoryWidget: React.FC = () => {
  const { data: history, isLoading, error } = useGetApprovalHistoryQuery({ limit: 10 })
  const { data: stats, isLoading: statsLoading } = useGetApprovalStatsQuery()

  if (isLoading || statsLoading) {
    return (
      <section aria-labelledby="approval-history-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 id="approval-history-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Approval History</h3>
        <div className="mt-4 animate-pulse">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-3"></div>
          <div className="h-40 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </section>
    )
  }

  if (error || !history) {
    return (
      <section aria-labelledby="approval-history-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 id="approval-history-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Approval History</h3>
        <div className="mt-4 text-sm text-gray-500 dark:text-gray-400">
          Unable to load approval history
        </div>
      </section>
    )
  }

  const getDecisionIcon = (decision: string) => {
    switch (decision.toLowerCase()) {
      case 'approved':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'rejected':
        return <XCircle className="w-4 h-4 text-red-500" />
      case 'reduced':
        return <AlertCircle className="w-4 h-4 text-yellow-500" />
      default:
        return <Clock className="w-4 h-4 text-gray-500" />
    }
  }

  const getDecisionColor = (decision: string) => {
    switch (decision.toLowerCase()) {
      case 'approved':
        return 'text-green-600 dark:text-green-400'
      case 'rejected':
        return 'text-red-600 dark:text-red-400'
      case 'reduced':
        return 'text-yellow-600 dark:text-yellow-400'
      default:
        return 'text-gray-600 dark:text-gray-400'
    }
  }

  return (
    <section 
      aria-labelledby="approval-history-heading" 
      data-testid="widget-approval-history"
      className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 id="approval-history-heading" className="text-lg font-semibold text-gray-900 dark:text-white">
          Approval History
        </h3>
        {stats && (
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {stats.total_reviews} reviews
          </span>
        )}
      </div>

      {history.history.length === 0 ? (
        <div className="mt-4 text-sm text-gray-500 dark:text-gray-400 text-center py-8">
          No approval history available
        </div>
      ) : (
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {history.history.map((item, index) => (
            <div
              key={index}
              className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
            >
              <div className="mt-0.5">
                {getDecisionIcon(item.decision)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-sm font-semibold ${getDecisionColor(item.decision)}`}>
                    {item.decision.toUpperCase()}
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {new Date(item.timestamp).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })}
                  </span>
                </div>
                <div className="text-xs text-gray-600 dark:text-gray-400 mb-1">
                  Reason: {item.reason.replace(/_/g, ' ')}
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Quantity:</span>
                    <span className="ml-1 font-semibold text-gray-900 dark:text-white">
                      {item.approved_quantity}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Kelly:</span>
                    <span className="ml-1 font-semibold text-gray-900 dark:text-white">
                      {(item.kelly_percentage * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Risk:</span>
                    <span className="ml-1 font-semibold text-gray-900 dark:text-white">
                      ₹{item.risk_amount.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {stats && (
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Approval Rate</p>
              <p className="text-lg font-semibold text-green-600">
                {(stats.approval_rate * 100).toFixed(0)}%
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Rejection Rate</p>
              <p className="text-lg font-semibold text-red-600">
                {(stats.rejection_rate * 100).toFixed(0)}%
              </p>
            </div>
            {stats.reduction_rate !== undefined && (
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Reduction Rate</p>
                <p className="text-lg font-semibold text-yellow-600">
                  {(stats.reduction_rate * 100).toFixed(0)}%
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
