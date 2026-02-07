import React, { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { fetchAgentDependencies } from '../../store/slices/tradingSlice'
import { RootState } from '../../store'
import AgentDependencyGraph from './AgentDependencyGraph'

export const AgentDependencyPanel: React.FC = () => {
  const dispatch = useDispatch()
  const state = useSelector((s: RootState) => s.trading)
  const deps = (state as any).agentDependencies
  const loading = (state as any).loadingDependencies

  useEffect(() => {
    dispatch(fetchAgentDependencies() as any)
  }, [dispatch])

  if (loading) {
    return <div className="p-4 bg-white dark:bg-gray-800 rounded">Loading dependencies...</div>
  }

  if (!deps) {
    return (
      <div className="p-4 bg-white dark:bg-gray-800 rounded">
        <div className="text-sm text-gray-600">No dependency data</div>
        { (state as any).error && (
          <div className="text-xs text-red-600 mt-2">Error: {(state as any).error}</div>
        ) }
      </div>
    )
  }

  return (
    <div className="p-4 bg-white dark:bg-gray-800 rounded">
      <h3 className="font-medium mb-2">Agent Dependencies</h3>

      <div className="mb-3">
        <AgentDependencyGraph nodes={deps.nodes || []} edges={deps.edges || []} width={520} height={360} />
      </div>

      <div className="text-sm text-gray-600 mb-2">Edges</div>
      <div className="space-y-2 text-sm">
        {deps.edges?.map((e: any, i: number) => (
          <div key={i} className="p-2 border rounded">{e.from} → {e.to} <span className="text-xs text-gray-500">({e.type})</span></div>
        ))}
      </div>
    </div>
  )
}

export default AgentDependencyPanel
