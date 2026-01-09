import React, { useEffect } from 'react'
import { useGetAgentStatusQuery } from '../../api/dashboardApi'

export const AgentStatusWidget: React.FC = () => {
  const { data, isLoading, isError, isFetching, refetch } = useGetAgentStatusQuery()
  
  // Listen for refresh events from QuickActionsWidget
  useEffect(() => {
    const handleRefresh = () => {
      setTimeout(() => refetch(), 500)
    }
    window.addEventListener('refresh-agent-status', handleRefresh)
    return () => window.removeEventListener('refresh-agent-status', handleRefresh)
  }, [refetch])
  
  // Auto-refetch every 5 seconds when not fetching
  useEffect(() => {
    if (!isFetching) {
      const interval = setInterval(() => {
        refetch()
      }, 5000)
      return () => clearInterval(interval)
    }
  }, [isFetching, refetch])

  // Compute latest updated_at across agents (call unconditionally to preserve hook order)
  const lastChecked = React.useMemo(() => {
    if (!Array.isArray(data) || data.length === 0) return null
    const timestamps = data.map((a: any) => Date.parse(a.updated_at)).filter(Boolean)
    if (!timestamps.length) return null
    return new Date(Math.max(...timestamps))
  }, [data])

  if (isLoading) {
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

  if (isError || !data) {
    return (
      <section aria-labelledby="agent-status-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 id="agent-status-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Agent Status</h3>
        <div className="mt-4 text-sm text-gray-500">Unable to load agent status</div>
      </section>
    )
  }

  return (
    <section aria-labelledby="agent-status-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between">
        <h3 id="agent-status-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Agent Status</h3>
        {isFetching && <span className="text-xs text-gray-500">Refreshing…</span>}
      </div>

      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        {data.map((agent: any) => (
          <div key={agent.name} className="p-3 bg-gray-50 dark:bg-gray-700 rounded">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-gray-900 dark:text-white">{agent.name}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">State: <span className="font-semibold">{agent.state}</span></div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Last decision: {agent.last_decision ?? '—'}</div>
              </div>
              <div className="text-xs text-gray-500">{agent.updated_at ? new Date(agent.updated_at).toLocaleTimeString() : '—'}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 text-xs text-gray-500">Last checked: {lastChecked ? lastChecked.toLocaleTimeString() : '—'}</div>
    </section>
  )
}
