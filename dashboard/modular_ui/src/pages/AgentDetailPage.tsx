import React, { useEffect } from 'react'
import { useParams, useLocation } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { RootState } from '../store'
import { fetchAgentDetails, fetchAgentHistory, fetchAgentMemory } from '../store/slices/tradingSlice'
import AgentFullReportModal from '../components/agents/AgentFullReportModal'
import AgentDependencyPanel from '../components/agents/AgentDependencyPanel'
import AgentConfigEditor from '../components/agents/AgentConfigEditor'
import { getAgentCommentary, getAgentExecutiveSummary } from '../utils/agentNarrative'

const asText = (value: any): string => (value === undefined || value === null ? '' : String(value).trim())

const formatTs = (ts?: string) => {
  if (!ts) return '-'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  return d.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })
}

const toEpoch = (ts?: string) => {
  if (!ts) return 0
  const d = new Date(ts)
  return Number.isNaN(d.getTime()) ? 0 : d.getTime()
}

const humanize = (key: string): string =>
  key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^./, (m) => m.toUpperCase())

const formatValue = (value: any): string => {
  if (value === undefined || value === null || value === '') return '-'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2)
  if (Array.isArray(value)) return value.length ? value.join(', ') : '-'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

const prettyJson = (value: any): string => {
  if (value === undefined || value === null) return '-'
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const isPlainObject = (value: any): value is Record<string, any> =>
  !!value && typeof value === 'object' && !Array.isArray(value)

const getInputSnapshot = (row: any) => {
  const details = (row?.details && typeof row.details === 'object') ? row.details : {}
  return (
    row?.input_data ||
    row?.agent_input_snapshot ||
    details?.agent_input_snapshot ||
    details?.decision_contract?.deterministic_inputs ||
    {}
  )
}

const getFeatureMap = (row: any): Record<string, any> => {
  const inputSnapshot: any = getInputSnapshot(row)
  return (inputSnapshot?.features && typeof inputSnapshot.features === 'object') ? inputSnapshot.features : {}
}

const getAnalysisSections = (row: any): Array<{ title: string; value: any }> => {
  const details = (row?.details && typeof row.details === 'object') ? row.details : {}
  const sections: Array<{ title: string; value: any }> = []
  const candidates: Array<[string, any]> = [
    ['Recommendation', details?.recommendation],
    ['Narrative Sections', details?.analysis_sections],
    ['Market Conditions', details?.market_conditions],
    ['Consensus', details?.consensus],
    ['Risk Assessment', details?.risk_assessment],
    ['Validation', details?.validation_result],
    ['Key Factors', details?.key_factors],
    ['Reason', details?.reason || details?.exclusion_reason || row?.reason],
  ]
  candidates.forEach(([title, value]) => {
    if (value !== undefined && value !== null && value !== '') sections.push({ title, value })
  })
  return sections
}

const getHighlightSummary = (row: any): string => {
  const details = (row?.details && typeof row.details === 'object') ? row.details : {}
  const recommendation = details?.recommendation
  if (isPlainObject(recommendation) && asText(recommendation?.plain_english)) {
    return asText(recommendation.plain_english)
  }
  const narrative = details?.analysis_sections
  if (isPlainObject(narrative) && asText(narrative?.decision_rationale)) {
    return asText(narrative.decision_rationale)
  }
  return ''
}

const toLabeledRows = (value: any): Array<{ label: string; value: string }> => {
  if (!isPlainObject(value)) return []
  return Object.entries(value)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => ({ label: humanize(k), value: formatValue(v) }))
}

export const AgentDetailPage: React.FC = () => {
  const { agentName } = useParams<{ agentName: string }>()
  const dispatch = useDispatch()
  const state = useSelector((s: RootState) => s.trading)
  const { search } = useLocation()

  const [reportModalOpen, setReportModalOpen] = React.useState(false)
  const [activeResponseId, setActiveResponseId] = React.useState<string | undefined>(undefined)

  useEffect(() => {
    if (!agentName) return
    dispatch(fetchAgentDetails(agentName) as any)
    dispatch(fetchAgentHistory({ agentName, limit: 50 }) as any)
    dispatch(fetchAgentMemory({ agentName, limit: 10 }) as any)

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

  const liveResponses = state.agentResponses.filter(r => r.agent === agentName)
  const agentStatus = state.agentStatuses.find(a => a.name === agentName)
  const isResearchManager = agentName === 'EnhancedResearchManager'
  const researchThesis = liveResponses.find(r => r.details?.research_thesis)?.details?.research_thesis
  const latestLive = liveResponses
    .slice()
    .sort((a: any, b: any) => toEpoch(b.timestamp) - toEpoch(a.timestamp))[0]
  const latestHistory = agentHistory[0]
  const latestLiveTs = toEpoch(latestLive?.timestamp)
  const latestHistoryTs = toEpoch(latestHistory?.timestamp || latestHistory?.created_at)
  const latestFromLive = !!latestLive && latestLiveTs >= latestHistoryTs
  const latestResponse: any = latestFromLive ? latestLive : latestHistory
  const latestResponseSource = latestFromLive ? 'live' : 'history'
  const latestResponseTs = latestResponse?.timestamp || latestResponse?.created_at
  const recentHistory = agentHistory.slice(latestFromLive ? 0 : 1, 20)
  const latestExecutiveSummary = getAgentExecutiveSummary(latestResponse)
  const latestCommentary =
    getAgentCommentary(latestResponse) ||
    asText(latestResponse?.details?.reasoning) ||
    asText(latestResponse?.reasoning)
  const latestInputSnapshot: any = getInputSnapshot(latestResponse)
  const latestFeatures = getFeatureMap(latestResponse)
  const latestAnalysisSections = getAnalysisSections(latestResponse)
  const qualityFlags = Array.isArray(latestInputSnapshot?.quality_flags) ? latestInputSnapshot.quality_flags : []
  const highlightSummary = getHighlightSummary(latestResponse)

  const renderSectionValue = (value: any) => {
    if (Array.isArray(value)) {
      if (!value.length) return <div className="text-xs text-gray-500">None</div>
      return (
        <div className="flex flex-wrap gap-1">
          {value.map((item, idx) => (
            <span key={idx} className="text-xs px-2 py-1 bg-slate-100 dark:bg-slate-700 rounded-full">
              {formatValue(item)}
            </span>
          ))}
        </div>
      )
    }
    if (isPlainObject(value)) {
      const rows = toLabeledRows(value)
      if (!rows.length) return <div className="text-xs text-gray-500">None</div>
      return (
        <div className="space-y-1">
          {rows.map((row) => (
            <div key={row.label} className="text-xs">
              <span className="text-gray-500">{row.label}:</span>{' '}
              <span className="text-gray-800 dark:text-gray-200">{row.value}</span>
            </div>
          ))}
        </div>
      )
    }
    return <div className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{formatValue(value)}</div>
  }

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
              <span className="px-3 py-1 bg-yellow-200 dark:bg-yellow-700 text-yellow-800 dark:text-yellow-200 text-sm font-bold rounded-full">
                PRIMARY DECISION MAKER
              </span>
            )}
          </div>
          <div className="text-sm text-gray-500 mt-1">
            {agentDetails?.config ? 'Config loaded' : 'No config'}
            {isResearchManager && ' - Research-First Architecture Core'}
          </div>
          {researchThesis && (
            <div className="mt-2 p-2 bg-yellow-100 dark:bg-yellow-900/50 rounded text-sm">
              <strong>Current Thesis:</strong> {researchThesis.decision} ({(researchThesis.confidence * 100).toFixed(0)}% confidence)
            </div>
          )}
        </div>
        <div className="text-right">
          <div className="text-sm">Status: <strong className={isResearchManager ? 'text-amber-700 dark:text-amber-300' : ''}>{agentStatus?.status || 'unknown'}</strong></div>
          <div className="text-sm">Last: {formatTs(agentStatus?.last_update)}</div>
          {isResearchManager && (
            <div className="text-xs text-amber-600 dark:text-amber-400 mt-1">
              Establishes primary market thesis
            </div>
          )}
        </div>
      </div>

      <section className="bg-white dark:bg-gray-800 rounded-lg p-4 mb-4">
        <h2 className="text-lg font-medium mb-2">Latest Response</h2>
        {!latestResponse ? (
          <div className="text-sm text-gray-500">No responses available yet for this agent.</div>
        ) : (
          <div className="p-3 border rounded-lg bg-gradient-to-b from-white to-slate-50 dark:from-gray-800 dark:to-gray-900">
            <div className="flex flex-wrap justify-between items-center gap-2 mb-2">
              <div className="font-medium">{latestResponse.agent || latestResponse.agent_name || agentName}</div>
              <div className="text-xs text-gray-500">
                {formatTs(latestResponseTs)}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-sm mb-3">
              <div className="rounded-lg border p-2 bg-white dark:bg-gray-800">
                <div className="text-[11px] uppercase tracking-wide text-gray-500">Decision</div>
                <div className="font-semibold">{latestResponse.decision || latestResponse.signal || '-'}</div>
              </div>
              <div className="rounded-lg border p-2 bg-white dark:bg-gray-800">
                <div className="text-[11px] uppercase tracking-wide text-gray-500">Confidence</div>
                <div className="font-semibold">{(Number(latestResponse.confidence || 0) * 100).toFixed(0)}%</div>
              </div>
              <div className="rounded-lg border p-2 bg-white dark:bg-gray-800">
                <div className="text-[11px] uppercase tracking-wide text-gray-500">Source</div>
                <div className="font-semibold">{latestResponseSource.toUpperCase()}</div>
              </div>
              <div className="rounded-lg border p-2 bg-white dark:bg-gray-800">
                <div className="text-[11px] uppercase tracking-wide text-gray-500">Response Id</div>
                <div className="font-mono text-xs truncate">{latestResponse?.response_id || latestResponse?._id || latestResponse?.details?.response_id || '-'}</div>
              </div>
            </div>

            <div className="mb-3 p-2 bg-indigo-50 dark:bg-indigo-900/20 rounded">
              <div className="text-xs font-semibold text-indigo-700 dark:text-indigo-300 mb-1">Executive Summary</div>
              <div className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                {latestExecutiveSummary || 'No executive summary captured for this run.'}
              </div>
            </div>

            <div className="mb-3 p-2 bg-slate-50 dark:bg-slate-900/20 rounded">
              <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Analyst Commentary</div>
              <div className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                {latestCommentary || 'No narrative commentary captured for this run.'}
              </div>
            </div>

            {highlightSummary && (
              <div className="mb-3 p-3 rounded border border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-900/20">
                <div className="text-xs font-semibold text-emerald-700 dark:text-emerald-300 mb-1">What This Means</div>
                <div className="text-sm text-emerald-900 dark:text-emerald-100">{highlightSummary}</div>
              </div>
            )}

            <div className="mb-3 text-xs text-gray-500 dark:text-gray-400">
              Context: instrument={latestResponse.instrument || '-'} | mode={latestResponse.mode || '-'} | run={latestResponse.run_id || '-'} | cycle={latestResponse.cycle_id || '-'}
            </div>

            <div className="mb-3 p-2 bg-gray-50 dark:bg-gray-900/20 rounded">
              <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Inputs Used</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                <div><span className="font-medium">Instrument:</span> {formatValue(latestInputSnapshot?.instrument || latestResponse.instrument)}</div>
                <div><span className="font-medium">Input Timestamp:</span> {formatValue(latestInputSnapshot?.timestamp)}</div>
                <div className="md:col-span-2">
                  <span className="font-medium">Quality Flags:</span> {qualityFlags.length ? qualityFlags.join(', ') : 'None'}
                </div>
              </div>
              {Object.keys(latestFeatures).length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mt-2">
                  {Object.entries(latestFeatures).map(([k, v]) => (
                    <div key={k} className="border rounded p-2 text-xs bg-white dark:bg-gray-800">
                      <div className="text-gray-500">{humanize(k)}</div>
                      <div className="font-medium text-gray-800 dark:text-gray-200 break-words">
                        {typeof v === 'number' ? formatValue(v) : formatValue(v).slice(0, 120)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="p-2 bg-blue-50 dark:bg-blue-900/20 rounded">
              <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Analysis Output</div>
              {latestAnalysisSections.length === 0 ? (
                <div className="text-xs text-gray-600 dark:text-gray-400">No structured analysis fields were captured.</div>
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
                  {latestAnalysisSections.map((section) => (
                    <div key={section.title} className="border rounded p-2 bg-white dark:bg-gray-800">
                      <div className="text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">{section.title}</div>
                      {renderSectionValue(section.value)}
                      {isPlainObject(section.value) && (
                        <details className="mt-2">
                          <summary className="text-[11px] text-gray-500 cursor-pointer">Raw JSON</summary>
                          <pre className="mt-1 text-[11px] text-gray-600 dark:text-gray-300 whitespace-pre-wrap break-words max-h-40 overflow-y-auto">
                            {prettyJson(section.value)}
                          </pre>
                        </details>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-3 text-right">
              <button
                className="px-2 py-1 bg-gray-200 rounded text-xs"
                onClick={() => {
                  setActiveResponseId(latestResponse?._id || latestResponse?.response_id || latestResponse?.details?.response_id)
                  setReportModalOpen(true)
                }}
              >
                View Full Report
              </button>
            </div>
          </div>
        )}
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2">
          <section className="bg-white dark:bg-gray-800 rounded-lg p-4">
            <h2 className="text-lg font-medium mb-2">Past Runs</h2>
            {recentHistory.length === 0 ? (
              <div className="text-sm text-gray-500">No previous runs available.</div>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {recentHistory.map((h: any, idx: number) => (
                  <div key={String(h._id || h.response_id || idx)} className="p-3 border rounded">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-medium">
                        {h.decision || h.signal || h.final_decision || 'N/A'}
                        <span className="ml-2 text-xs text-gray-500">
                          {(Number(h.confidence || 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="text-xs text-gray-500">{formatTs(h.timestamp || h.created_at)}</div>
                    </div>
                    <div className="text-xs text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">
                      {getAgentCommentary(h) || 'Commentary not provided by agent.'}
                    </div>
                  </div>
                ))}
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
                    <div className="text-sm mt-1">{m.document ? m.document.substring(0, 220) : JSON.stringify(m.metadata)}</div>
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

      <AgentFullReportModal
        agentName={agentName}
        responseId={activeResponseId}
        isOpen={reportModalOpen}
        onClose={() => setReportModalOpen(false)}
      />
    </div>
  )
}

export default AgentDetailPage
