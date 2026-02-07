export interface AgentDetailsApi {
  agent_name: string
  latest_decision?: any
  config?: any
}

export interface AgentHistoryItem {
  _id?: string
  timestamp?: string
  agent_name?: string
  signal?: string
  decision?: string
  confidence?: number
  reasoning?: string
  indicators?: any
}

export interface AgentMemoryItem {
  document: string
  metadata: any
  similarity?: number
}

// WebSocket messages (summary keys)
export interface AgentWSResponseSummary {
  type: 'agent:response:partial' | 'agent:response:final' | 'agent:status' | string
  agent: string
  response_id?: string
  decision?: string
  confidence?: number
  summary?: string
  timestamp?: string
}

export interface AgentStructuredReportResponse {
  response_id: string
  agent_name: string
  structured_report: any
}

export interface AgentDependencies {
  nodes: Array<{ id: string; label: string }>
  edges: Array<{ from: string; to: string; type?: string }>
}
