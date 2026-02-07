import React, { useState } from 'react'
import { useDispatch } from 'react-redux'
import { updateAgentConfig } from '../../store/slices/tradingSlice'

interface Props {
  agentName: string
  initialConfig?: any
}

export const AgentConfigEditor: React.FC<Props> = ({ agentName, initialConfig }) => {
  const dispatch = useDispatch()
  const [config, setConfig] = useState<any>(initialConfig || {})
  const [saving, setSaving] = useState(false)

  const onChange = (k: string, v: any) => {
    setConfig((s: any) => ({ ...s, [k]: v }))
  }

  const save = async () => {
    setSaving(true)
    try {
      await dispatch(updateAgentConfig({ agentName, config }) as any)
    } catch (e) {
      // ignore
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="p-4 bg-white dark:bg-gray-800 rounded">
      <h4 className="font-medium mb-2">Edit Config</h4>
      <div className="text-sm text-gray-600 mb-2">Edit JSON config (simple key/value)</div>
      <div className="space-y-2">
        {Object.keys(config || {}).map((k) => (
          <div key={k} className="flex items-center space-x-2">
            <div className="w-32 text-xs text-gray-600">{k}</div>
            <input value={String(config[k] ?? '')} onChange={(e) => onChange(k, e.target.value)} className="flex-1 p-1 border rounded" />
          </div>
        ))}
        <div className="mt-3 text-right">
          <button onClick={save} className={`px-3 py-1 rounded bg-blue-600 text-white ${saving ? 'opacity-60' : ''}`}>Save</button>
        </div>
      </div>
    </div>
  )
}

export default AgentConfigEditor
