# Agent API — WebSocket Messages & REST Contracts

This document describes the WebSocket message schemas and REST API contracts for the Agent UI (TechnicalAgent first, extensible to others).

## WebSocket (Redis WS Gateway)

Messages are delivered with envelope { type, channel?, data? } from the gateway.

- agent:response:partial
  - Purpose: streaming partial text/analysis
  - Example:
    {
      "type": "data",
      "channel": "engine:agent:response:partial:TechnicalAgent",
      "data": {
        "type": "agent:response:partial",
        "agent": "TechnicalAgent",
        "response_id": "r-20260119-0001",
        "part_index": 1,
        "total_parts": 3,
        "partial_text": "Calculating RSI...",
        "timestamp": "2026-01-19T09:45:12Z"
      }
    }

- agent:response:final
  - Purpose: final result summary (lightweight)
  - Example:
    {
      "type": "data",
      "channel": "engine:agent:response:final:TechnicalAgent",
      "data": {
        "type": "agent:response:final",
        "agent": "TechnicalAgent",
        "response_id": "r-20260119-0001",
        "decision": "BUY",
        "confidence": 0.72,
        "summary": "RSI oversold + price above 50 SMA",
        "timestamp": "2026-01-19T09:45:15Z"
      }
    }

- agent:status
  - Purpose: heartbeat and status updates
  - Example:
    {"type":"agent:status","agent":"TechnicalAgent","status":"active","last_update":"..."}

Notes:
- WS payloads should be kept small; large structured reports should be referenced by `response_id` and fetched via REST.

## REST Endpoints

- GET /api/engine/agents
  - Returns: [{ name, description, has_memory }]

- GET /api/engine/agents/{agent_name}/details
  - Returns: { agent_name, latest_decision, config }

- GET /api/engine/agents/{agent_name}/history?limit=50
  - Returns: array of saved responses (agent_discussions) most recent first
  - Each item includes: { _id, timestamp, agent_name, signal/decision, confidence, reasoning, details }

- GET /api/engine/agents/{agent_name}/responses/{response_id}
  - Returns full saved response document (raw) — used by UI to display full `structured_report`

- GET /api/engine/agents/{agent_name}/responses/{response_id}/structured_report
  - Convenience endpoint returning only the `structured_report` field

- GET /api/engine/agents/{agent_name}/memory?q=&limit=
  - Uses ChromaDB memory to run similarity search or return recent experiences

- GET /api/engine/agents/dependencies
  - Returns: { nodes: [{id,label}], edges: [{from,to,type}] }

- POST /api/engine/agents/{agent_name}/config
  - Body: JSON config dict
  - Behavior: update in-memory agent config if present, persist to Mongo `agent_configs`
  - Returns: { success: true, updated_in_memory: bool }

## UI Behavior Patterns

- Live feed: subscribe to `engine:agent` / `engine:decision` via WS; show `partial` streaming then `final` summary.
- When user requests full details, fetch via `/responses/{response_id}` or `/structured_report`.
- Dependencies graph fetched from `/agents/dependencies` and visualized on the agent page.

---

This document is intended as a concise single-source reference for the frontend and backend teams while building the per-agent UI.
