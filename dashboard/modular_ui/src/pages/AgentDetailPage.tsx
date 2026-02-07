import React, { useEffect } from 'react'
import { useParams, useLocation } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { RootState } from '../store'
import { fetchAgentDetails, fetchAgentHistory, fetchAgentMemory } from '../store/slices/tradingSlice'
import AgentFullReportModal from '../components/agents/AgentFullReportModal'
import AgentDependencyPanel from '../components/agents/AgentDependencyPanel'
import AgentConfigEditor from '../components/agents/AgentConfigEditor'

export const AgentDetailPage: React.FC = () => {
  const { agentName } = useParams<{ agentName: string }>()
  const dispatch = useDispatch()
  const state = useSelector((s: RootState) => s.trading)
  const { search } = useLocation()

  useEffect(() => {
    if (!agentName) return
    dispatch(fetchAgentDetails(agentName) as any)
    dispatch(fetchAgentHistory({ agentName, limit: 50 }) as any)
    dispatch(fetchAgentMemory({ agentName, limit: 10 }) as any)

    // Check for response query param to auto-open full report
    const params = new URLSearchParams(search)
    const responseId = params.get('response')
    if (responseId) {
      setActiveResponseId(responseId)
      setReportModalOpen(true)
    }
  }, [agentName, dispatch, search])

  const agentDetails = (state as any).agentDetails
  const agentHistory = (state as any).agentHistory || []
  const agentMemory = (state as any).agentMemory || []

  // Live responses come via WebSocket -> agentResponses store
  const liveResponses = state.agentResponses.filter(r => r.agent === agentName)
  const agentStatus = state.agentStatuses.find(a => a.name === agentName)

  // Research-First Context
  const isResearchManager = agentName === 'EnhancedResearchManager'
  const researchThesis = liveResponses.find(r => r.details?.research_thesis)?.details?.research_thesis

  const [reportModalOpen, setReportModalOpen] = React.useState(false)
  const [activeResponseId, setActiveResponseId] = React.useState<string | undefined>(undefined)

  return (
    <div className="p-6">
      <div className={`flex items-center justify-between mb-4 p-4 rounded-lg border-2 ${
        isResearchManager
          ? 'bg-gradient-to-r from-yellow-50 to-amber-50 dark:from-yellow-900/20 dark:to-amber-900/20 border-yellow-300 dark:border-yellow-600'
          : 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700'
      }`}>
        <div>
          <div className="flex items-center space-x-3">
            <h1 className={`text-2xl font-semibold ${isResearchManager ? 'text-amber-800 dark:text-amber-200' : ''}`}>
              {agentName}
            </h1>
            {isResearchManager && (
              <span className="px-3 py-1 bg-yellow-200 dark:bg-yellow-700 text-yellow-800 dark:text-yellow-200 text-sm font-bold rounded-full flex items-center">
                PRIMARY DECISION MAKER
              </span>
            )}
          </div>
          <div className="text-sm text-gray-500 mt-1">
            {agentDetails?.config ? 'Config loaded' : 'No config'}
            {isResearchManager && ' • Research-First Architecture Core'}
          </div>
          {researchThesis && (
            <div className="mt-2 p-2 bg-yellow-100 dark:bg-yellow-900/50 rounded text-sm">
              <strong>Current Thesis:</strong> {researchThesis.decision} ({(researchThesis.confidence * 100).toFixed(0)}% confidence)
            </div>
          )}
        </div>
        <div className="text-right">
          <div className="text-sm">Status: <strong className={isResearchManager ? 'text-amber-700 dark:text-amber-300' : ''}>{agentStatus?.status || 'unknown'}</strong></div>
          <div className="text-sm">Last: {agentStatus?.last_update || '—'}</div>
          {isResearchManager && (
            <div className="text-xs text-amber-600 dark:text-amber-400 mt-1">
              Establishes primary market thesis
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="col-span-2">
          <section className="bg-white dark:bg-gray-800 rounded-lg p-4 mb-4">
            <h2 className="text-lg font-medium mb-2">Live Feed</h2>
            <div className="space-y-3 max-h-64 overflow-y-auto">
              {liveResponses.length === 0 ? (
                <div className="text-sm text-gray-500">No live responses yet.</div>
              ) : (
                liveResponses.slice().reverse().map((r, i) => (
                  <div key={`${r.agent}-${r.timestamp}-${i}`} className="p-3 border rounded">
                    <div className="flex justify-between items-center">
                      <div className="font-medium">{r.agent}</div>
                      <div className="text-xs text-gray-500">{new Date(r.timestamp).toLocaleString()}</div>
                    </div>
                    <div className="text-sm text-gray-700 mt-1">{r.details?.reasoning || r.details?.thesis || '-'}</div>
                    {r.details && (
                      <pre className="text-xs text-gray-600 mt-2 whitespace-pre-wrap">{JSON.stringify(r.details, null, 2)}</pre>
                    )}
                    <div className="mt-2 text-right">
                      <button className="px-2 py-1 bg-gray-200 rounded text-xs" onClick={() => { setActiveResponseId(r.details?.response_id || r._id || r.response_id); setReportModalOpen(true) }}>
                        View Full Report
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="bg-white dark:bg-gray-800 rounded-lg p-4">
            <h2 className="text-lg font-medium mb-2">Latest Full Decision</h2>
            {agentHistory.length === 0 ? (
              <div className="text-sm text-gray-500">No saved decisions for this agent yet.</div>
            ) : (
              <div>
                {/* Show most recent history entry */}
                <div className="p-3 border rounded">
                  <div className="flex justify-between items-center mb-2">
                    <div className="font-medium">{agentHistory[0].agent_name || agentName}</div>
                    <div className="text-xs text-gray-500">{agentHistory[0].timestamp || agentHistory[0].created_at || '-'}</div>
                  </div>
                  <div className="text-sm text-gray-700">Decision: <strong>{agentHistory[0].decision || agentHistory[0].signal || '-'}</strong></div>
                  <div className="text-sm text-gray-700">Confidence: <strong>{(agentHistory[0].confidence || 0) * 100}%</strong></div>
                  <div className="mt-2 text-sm text-gray-600">{agentHistory[0].reasoning || agentHistory[0].thesis || JSON.stringify(agentHistory[0].indicators || {}, null, 2)}</div>
                  <div className="mt-2 text-right">
                    <button className="px-2 py-1 bg-gray-200 rounded text-xs" onClick={() => { setActiveResponseId(agentHistory[0]._id || agentHistory[0].response_id); setReportModalOpen(true) }}>
                      View Full Report
                    </button>
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>

        <aside>
          <section className="bg-white dark:bg-gray-800 rounded-lg p-4 mb-4">
            <h3 className="text-md font-medium mb-2">Memory / Recent Experiences</h3>
            {agentMemory.length === 0 ? (
              <div className="text-sm text-gray-500">No memory found.</div>
            ) : (
              <div className="space-y-2 text-sm text-gray-700 max-h-64 overflow-y-auto">
                {agentMemory.map((m: any, i: number) => (
                  <div key={i} className="p-2 border rounded">
                    <div className="text-xs text-gray-500">{m.metadata?.timestamp || ''}</div>
                    <div className="text-sm mt-1">{m.document ? m.document.substring(0, 200) : JSON.stringify(m.metadata)}</div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="bg-white dark:bg-gray-800 rounded-lg p-4 mb-4">
            <h3 className="text-md font-medium mb-2">Agent Config</h3>
            {agentDetails?.config ? (
              <div>
                <pre className="text-xs text-gray-600 whitespace-pre-wrap mb-2">{JSON.stringify(agentDetails.config, null, 2)}</pre>
                {/* Config editor */}
                <div className="mt-2">
                  <AgentConfigEditor agentName={agentName || ''} initialConfig={agentDetails.config} />
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-500">No config available</div>
            )}
          </section>

          <section className="bg-white dark:bg-gray-800 rounded-lg p-4">
            <h3 className="text-md font-medium mb-2">Dependencies</h3>
            <AgentDependencyPanel />
          </section>
        </aside>
      </div>

      <AgentFullReportModal agentName={agentName} responseId={activeResponseId} isOpen={reportModalOpen} onClose={() => setReportModalOpen(false)} />
    </div>
  )
}

export default AgentDetailPage
