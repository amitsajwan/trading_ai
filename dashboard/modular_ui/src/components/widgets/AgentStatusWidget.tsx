import React from 'react'
import { useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { RootState } from '../../store'

const MODE_INFO_URL = '/api/control/mode/info'

interface AgentStatusWidgetProps {
  onAgentClick?: (agent: any) => void
  separateByRun?: boolean
  showAuditSection?: boolean
}

const formatEventTime = (value?: string) => {
  if (!value) return '-'
  const d = new Date(value)
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

const formatConfidencePct = (value: unknown): string | null => {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0) return null
  const normalized = n <= 1 ? n : (n <= 100 ? n / 100 : NaN)
  if (!Number.isFinite(normalized) || normalized < 0 || normalized > 1) return null
  return `${(normalized * 100).toFixed(0)}%`
}

export const AgentStatusWidget: React.FC<AgentStatusWidgetProps> = ({ onAgentClick, separateByRun = true, showAuditSection = false }) => {
  const navigate = useNavigate()
  const { agentStatuses, agentResponses, loading } = useSelector((state: RootState) => state.trading)
  const currentRunId = useSelector((state: RootState) => state.ui.executionMode.runId)
  const [runtimeRunId, setRuntimeRunId] = React.useState<string>('')
  const effectiveRunId = React.useMemo(
    () => String(runtimeRunId || currentRunId || '').trim(),
    [runtimeRunId, currentRunId]
  )

  React.useEffect(() => {
    let mounted = true
    const fetchRuntime = async () => {
      try {
        const resp = await fetch(MODE_INFO_URL)
        if (!resp.ok) return
        const data = await resp.json()
        if (!mounted) return
        setRuntimeRunId(String(data?.run_id || '').trim())
      } catch {
        // Best effort only.
      }
    }
    fetchRuntime()
    const timer = setInterval(fetchRuntime, 15000)
    return () => {
      mounted = false
      clearInterval(timer)
    }
  }, [])

  const isResearchManager = (agentName: string) => agentName === 'EnhancedResearchManager'
  const isSupportingAgent = (agentName: string) => !isResearchManager(agentName)

  const enrichedAgentStatuses = React.useMemo(() => {
    const statusMap = new Map<string, any>(
      (agentStatuses || [])
        .filter((s) => s?.name)
        .map((status) => [status.name, status])
    )

    ;(agentResponses || []).forEach((response: any) => {
      const agent = String(response?.agent || '').trim()
      if (!agent || agent.toLowerCase() === 'unknown agent' || agent.toLowerCase() === 'unknown') return

      const existing = statusMap.get(agent) || { name: agent, status: 'active' as const }
      const responseDecision = String(response?.decision || '').toUpperCase()
      const derivedStatus = responseDecision === 'EXCLUDED' ? 'excluded' : (existing.status || 'active')

      statusMap.set(agent, {
        ...existing,
        status: derivedStatus,
        last_update: response.timestamp || existing.last_update,
        signal: response.decision ?? existing.signal,
        confidence: response.confidence ?? existing.confidence,
        summary: response.details ?? existing.summary,
        run_id: response.run_id ?? existing.run_id,
        cycle_id: response.cycle_id ?? existing.cycle_id,
        ran_in_current_run: typeof existing.ran_in_current_run === 'boolean' ? existing.ran_in_current_run : undefined,
      })
    })

    return Array.from(statusMap.values())
      .filter((s) => {
        const n = String(s.name || '').trim().toLowerCase()
        return n && n !== 'unknown agent' && n !== 'unknown'
      })
      .sort((a, b) => {
        if (isResearchManager(a.name) && !isResearchManager(b.name)) return -1
        if (!isResearchManager(a.name) && isResearchManager(b.name)) return 1
        return String(a.name).localeCompare(String(b.name))
      })
  }, [agentStatuses, agentResponses])

  const inCurrentRun = React.useCallback(
    (agent: any) => {
      if (!effectiveRunId) return true
      if (agent?.ran_in_current_run === true) return true
      if (agent?.ran_in_current_run === false) return false
      if (agent?.run_id) return String(agent.run_id).trim() === effectiveRunId
      // Strict behavior: unknown run metadata should not be shown under "Current Run Agents".
      return false
    },
    [effectiveRunId]
  )

  const currentRunAgents = React.useMemo(() => enrichedAgentStatuses.filter(inCurrentRun), [enrichedAgentStatuses, inCurrentRun])
  const otherRunAgents = React.useMemo(() => enrichedAgentStatuses.filter((a) => !inCurrentRun(a)), [enrichedAgentStatuses, inCurrentRun])
  const currentRunDisplayAgents = React.useMemo(
    () =>
      [...currentRunAgents].sort((a, b) => {
        if (isResearchManager(a.name) && !isResearchManager(b.name)) return -1
        if (!isResearchManager(a.name) && isResearchManager(b.name)) return 1
        return String(a.name).localeCompare(String(b.name))
      }),
    [currentRunAgents]
  )
  const hasAnyAgentData = enrichedAgentStatuses.length > 0
  const showLatestSnapshotFallback = Boolean(effectiveRunId) && currentRunDisplayAgents.length === 0 && otherRunAgents.length > 0
  const isRefreshing = loading.agents && hasAnyAgentData

  const statusStyle = (status: string) => {
    switch ((status || '').toLowerCase()) {
      case 'active':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'excluded':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
      case 'stale':
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
      case 'idle':
      case 'inactive':
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
      case 'error':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  const cardStyle = (status: string) => {
    switch ((status || '').toLowerCase()) {
      case 'active':
        return 'bg-gray-50 dark:bg-gray-700 border-gray-200 dark:border-gray-600'
      case 'excluded':
        return 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-300 dark:border-yellow-700'
      case 'stale':
        return 'bg-orange-50 dark:bg-orange-900/20 border-orange-300 dark:border-orange-700'
      case 'idle':
      case 'inactive':
        return 'bg-gray-50 dark:bg-gray-700 border-gray-200 dark:border-gray-600'
      case 'error':
        return 'bg-red-50 dark:bg-red-900/20 border-red-300 dark:border-red-700'
      default:
        return 'bg-gray-50 dark:bg-gray-700 border-gray-200 dark:border-gray-600'
    }
  }

  const renderAgentGrid = (agents: any[]) => (
    <div className="mt-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      {agents.map((agent) => {
        const isPrimary = isResearchManager(agent.name || '')
        return (
          <div
            key={agent.name}
            className={`p-3 rounded cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors border-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              isPrimary
                ? 'bg-gradient-to-r from-yellow-50 to-amber-50 dark:from-yellow-900/20 dark:to-amber-900/20 border-yellow-300 dark:border-yellow-600 shadow-md'
                : cardStyle(agent.status || 'idle')
            }`}
            role="button"
            tabIndex={0}
            onClick={() => {
              if (onAgentClick) {
                onAgentClick(agent)
                return
              }
              if (agent?.name) {
                navigate(`/agents/${encodeURIComponent(String(agent.name))}`)
              }
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                if (onAgentClick) {
                  onAgentClick(agent)
                  return
                }
                if (agent?.name) {
                  navigate(`/agents/${encodeURIComponent(String(agent.name))}`)
                }
              }
            }}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <div className={`text-sm font-medium ${isPrimary ? 'text-amber-800 dark:text-amber-200' : 'text-gray-900 dark:text-white'}`}>
                  {agent.name}
                </div>
                {isPrimary && (
                  <span className="px-2 py-0.5 bg-yellow-200 dark:bg-yellow-700 text-yellow-800 dark:text-yellow-200 text-xs font-bold rounded-full">
                    PRIMARY
                  </span>
                )}
              </div>
              <div className={`px-2 py-1 rounded-full text-xs font-medium ${statusStyle(agent.status || 'idle')}`}>
                {agent.status}
              </div>
            </div>

            <div className="space-y-1 text-xs text-gray-600 dark:text-gray-400">
              {agent.signal && (
                <div>
                  Decision: <span className={`font-medium ${isPrimary ? 'text-amber-700 dark:text-amber-300' : ''}`}>{agent.signal}</span>
                </div>
              )}
              <div>
                Confidence: <span className={`font-medium ${isPrimary ? 'text-amber-700 dark:text-amber-300' : ''}`}>{formatConfidencePct(agent.confidence) ?? 'N/A'}</span>
              </div>
              <div>Last update: {formatEventTime(agent.last_update)}</div>
              {agent.ran_in_current_run === false && <div className="text-orange-600 dark:text-orange-300">Not in current run</div>}
              {effectiveRunId && !agent?.run_id && agent?.ran_in_current_run !== true && (
                <div className="text-slate-500 dark:text-slate-300">Run metadata unavailable</div>
              )}
              {(agent.run_id || agent.cycle_id) && (
                <div>
                  Run: {agent.run_id || '-'} {agent.cycle_id ? `| Cycle: ${agent.cycle_id}` : ''}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )

  // Show full skeleton only when there is no data yet.
  // During periodic polling, keep prior data visible to avoid blank flicker.
  if (loading.agents && !hasAnyAgentData) {
    return (
      <section aria-labelledby="agent-status-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 id="agent-status-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Agent Status</h3>
        <div className="mt-4 rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-900/20">
          <div className="flex items-center gap-3">
            <div className="h-4 w-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
            <div>
              <div className="text-sm font-medium text-gray-700 dark:text-gray-200">Loading agent status...</div>
              <div className="text-xs text-gray-500 dark:text-gray-400">Fetching latest run snapshot from backend</div>
            </div>
          </div>
          <div className="mt-3 animate-pulse">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-2" />
            <div className="h-16 bg-gray-200 dark:bg-gray-700 rounded" />
          </div>
        </div>
      </section>
    )
  }

  return (
    <section aria-labelledby="agent-status-heading" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between">
        <h3 id="agent-status-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Agent Status</h3>
        <div className="text-xs text-green-600 dark:text-green-400 flex items-center gap-2">
          <span>
            {(showLatestSnapshotFallback ? otherRunAgents : currentRunAgents).filter((a) => isResearchManager(a.name)).length} primary - {(showLatestSnapshotFallback ? otherRunAgents : currentRunAgents).filter((a) => isSupportingAgent(a.name)).length} supporting agents
          </span>
          {isRefreshing && <span className="text-gray-500 dark:text-gray-400">Refreshing...</span>}
        </div>
      </div>

      {enrichedAgentStatuses.length === 0 && (
        <div className="mt-4 text-center text-gray-500 dark:text-gray-400 py-8">
          <div className="text-4xl mb-2">AI</div>
          <p>No agent data received yet</p>
          <p className="text-xs mt-1">Waiting for orchestrator to send agent updates</p>
        </div>
      )}

      {enrichedAgentStatuses.length > 0 && (!separateByRun || !effectiveRunId) && renderAgentGrid(enrichedAgentStatuses)}

      {enrichedAgentStatuses.length > 0 && separateByRun && effectiveRunId && (
        <>
          <div className="mt-4 border-t border-gray-200 dark:border-gray-700 pt-3">
            <div className="text-sm font-medium text-gray-900 dark:text-white">Current Run Agents</div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Run: {effectiveRunId}</div>
            {currentRunDisplayAgents.length > 0 ? (
              renderAgentGrid(currentRunDisplayAgents)
            ) : (
              <div className="mt-3 space-y-2">
                <div className="text-sm text-gray-500 dark:text-gray-400">No agents have reported for the current run yet.</div>
                {showLatestSnapshotFallback && (
                  <>
                    <div className="text-xs text-amber-600 dark:text-amber-300">
                      Showing latest available snapshot from a different run while waiting for current-run updates.
                    </div>
                    {renderAgentGrid(otherRunAgents)}
                  </>
                )}
              </div>
            )}
          </div>

          {showAuditSection && (
            <div className="mt-6 border-t border-gray-200 dark:border-gray-700 pt-3">
              <div className="text-sm font-medium text-gray-900 dark:text-white">Audit History (Older Runs)</div>
              <div className="text-xs text-gray-500 dark:text-gray-400">Older or run-mismatched agent records</div>
              {otherRunAgents.length > 0 ? (
                renderAgentGrid(otherRunAgents)
              ) : (
                <div className="mt-3 text-sm text-gray-500 dark:text-gray-400">No older agent records.</div>
              )}
            </div>
          )}
        </>
      )}
    </section>
  )
}
