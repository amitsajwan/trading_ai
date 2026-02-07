import React from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { RootState } from '../../store'
import { fetchAgentResponse } from '../../store/slices/tradingSlice'

interface Props {
  agentName: string | undefined
  responseId?: string
  isOpen: boolean
  onClose: () => void
}

export const AgentFullReportModal: React.FC<Props> = ({ agentName, responseId, isOpen, onClose }) => {
  const dispatch = useDispatch()
  const state = useSelector((s: RootState) => s.trading)
  const full = (state as any).agentFullResponse

  React.useEffect(() => {
    if (isOpen && agentName && responseId) {
      dispatch(fetchAgentResponse({ agentName, responseId }) as any)
    }
  }, [isOpen, agentName, responseId, dispatch])

  if (!isOpen) return null

  if (!full) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-3xl w-full p-6">
          <div className="text-center">Loading full report...</div>
          <div className="mt-4 text-right">
            <button onClick={onClose} className="px-4 py-2 bg-gray-200 rounded">Close</button>
          </div>
        </div>
      </div>
    )
  }

  const sr = full.details?.structured_report || full.structured_report || full.details

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-3xl w-full max-h-[85vh] overflow-y-auto">
        <div className="p-6 border-b">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-xl font-semibold">Full Report — {full.agent_name || agentName}</h3>
              <div className="text-sm text-gray-500">{full.timestamp}</div>
            </div>
            <div>
              <button onClick={onClose} className="px-3 py-1 bg-blue-600 text-white rounded">Close</button>
            </div>
          </div>
        </div>

        <div className="p-6">
          <h4 className="text-lg font-medium mb-2">Decision</h4>
          <div className="mb-4">{full.decision || full.signal || '-' } — Confidence: {(full.confidence || 0) * 100}%</div>

          <h4 className="text-lg font-medium mb-2">Structured Report</h4>
          {sr ? (
            <pre className="text-sm whitespace-pre-wrap bg-gray-50 dark:bg-gray-700 p-3 rounded">{JSON.stringify(sr, null, 2)}</pre>
          ) : (
            <div className="text-sm text-gray-500">No structured report found in this response.</div>
          )}

          <h4 className="text-lg font-medium mt-6 mb-2">Raw Response</h4>
          <pre className="text-sm whitespace-pre-wrap bg-gray-50 dark:bg-gray-700 p-3 rounded mt-2">{JSON.stringify(full, null, 2)}</pre>
        </div>

      </div>
    </div>
  )
}

export default AgentFullReportModal
