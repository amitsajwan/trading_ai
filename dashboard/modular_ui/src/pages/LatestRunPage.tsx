import React, { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { RootState } from '../store'
import { fetchAgentStatuses, fetchOrchestratorDecisions, fetchSignals } from '../store/slices/tradingSlice'
import { WidgetShell } from '../components/widgets/WidgetShell'
import { AgentStatusWidget } from '../components/widgets/AgentStatusWidget'
import { OrchestratorDecisionsWidget } from '../components/widgets/OrchestratorDecisionsWidget'
import { AgentResponsesWidget } from '../components/widgets/AgentResponsesWidget'

export const LatestRunPage: React.FC = () => {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { executionMode } = useSelector((state: RootState) => state.ui)
  const { agentStatuses, orchestratorDecisions, agentResponses } = useSelector((state: RootState) => state.trading)
  const runtimeInstrument = executionMode.instrument

  useEffect(() => {
    dispatch(fetchAgentStatuses() as any)
    dispatch(fetchOrchestratorDecisions({ limit: 20, instrument: runtimeInstrument || undefined }) as any)
    dispatch(fetchSignals(runtimeInstrument || undefined) as any)
  }, [dispatch, runtimeInstrument, executionMode.runId])

  useEffect(() => {
    const interval = setInterval(() => {
      dispatch(fetchAgentStatuses() as any)
      dispatch(fetchOrchestratorDecisions({ limit: 20, instrument: runtimeInstrument || undefined }) as any)
      dispatch(fetchSignals(runtimeInstrument || undefined) as any)
    }, 8000)
    return () => clearInterval(interval)
  }, [dispatch, runtimeInstrument])

  const currentRunId = String(executionMode.runId || '').trim()

  const inCurrentRun = (agent: any) => {
    if (!currentRunId) return true
    if (agent?.ran_in_current_run === true) return true
    if (agent?.ran_in_current_run === false) return false
    if (agent?.run_id) return String(agent.run_id).trim() === currentRunId
    return false
  }

  const currentRunAgentCount = agentStatuses.filter((a) => inCurrentRun(a)).length
  const otherRunAgentCount = agentStatuses.filter((a) => !inCurrentRun(a)).length
  const currentRunDecisionCount = currentRunId
    ? orchestratorDecisions.filter((d) => String(d.run_id || '').trim() === currentRunId).length
    : orchestratorDecisions.length
  const currentRunResponseCount = currentRunId
    ? agentResponses.filter((r: any) => String(r.run_id || '').trim() === currentRunId).length
    : agentResponses.length

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Latest Run</h1>
        <p className="text-gray-600 dark:text-gray-400">Single place for the active cycle, with older agent records separated out.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3">
          <div className="text-xs text-gray-500">Mode</div>
          <div className="text-sm font-semibold text-gray-900 dark:text-white">{executionMode.mode || 'UNKNOWN'}</div>
        </div>
        <div className="rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3">
          <div className="text-xs text-gray-500">Run Id</div>
          <div className="text-sm font-semibold text-gray-900 dark:text-white break-all">{currentRunId || 'N/A'}</div>
        </div>
        <div className="rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3">
          <div className="text-xs text-gray-500">Current Run Agents</div>
          <div className="text-sm font-semibold text-gray-900 dark:text-white">{currentRunAgentCount}</div>
          <div className="text-xs text-gray-500">Other runs: {otherRunAgentCount}</div>
        </div>
        <div className="rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3">
          <div className="text-xs text-gray-500">Current Run Decisions</div>
          <div className="text-sm font-semibold text-gray-900 dark:text-white">{currentRunDecisionCount}</div>
          <div className="text-xs text-gray-500">Responses: {currentRunResponseCount}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <WidgetShell id="latest-run-agent-status" title="Agent Status by Run">
          <AgentStatusWidget
            separateByRun
            showAuditSection
            onAgentClick={(agent) => {
              if (agent?.name) {
                navigate(`/agents/${encodeURIComponent(agent.name)}`)
              }
            }}
          />
        </WidgetShell>

        <WidgetShell id="latest-run-orchestrator" title="Orchestrator Decisions (Current Run)">
          <OrchestratorDecisionsWidget />
        </WidgetShell>
      </div>

      <WidgetShell id="latest-run-agent-responses" title="Agent Responses (Current Run)">
        <AgentResponsesWidget currentRunOnly />
      </WidgetShell>
    </div>
  )
}

export default LatestRunPage
