# API Index & Healthcheck Guide

This document consolidates the service API contracts, base URLs, example requests, and recommended Docker healthcheck commands. It's a single source-of-truth for the services the compose stack exposes and how the dashboard/UI and orchestration should validate service availability before declaring containers healthy.

---

## Services Overview

### Market Data API (market_data)
- Base URL: http://localhost:8004
- FastAPI docs: http://localhost:8004/docs  ·  OpenAPI: http://localhost:8004/openapi.json
- Contract: `market_data/API_CONTRACT.md`

Key endpoints:
- `GET /health` — health + dependencies
- `GET /api/v1/market/tick/{instrument}`
- `GET /api/v1/market/ohlc/{instrument}` (query: `timeframe`, `limit`)
- `GET /api/v1/market/price/{instrument}`
- `GET /api/v1/market/raw/{instrument}` (query: `limit`)
- `GET /api/v1/options/chain/{instrument}` (requires Kite credentials)
- `GET /api/v1/technical/indicators/{instrument}`

Example curl (health):
```bash
curl -sS http://localhost:8004/health | jq .
```
Recommended compose healthcheck (current pattern used in repo):
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request,sys;urllib.request.urlopen('http://localhost:8004/health', timeout=5).read();sys.exit(0)"]
  interval: 30s
  timeout: 10s
  retries: 3
```

---

### News API (news_module)
- Base URL: http://localhost:8005
- FastAPI docs: http://localhost:8005/docs
- Contract: `news_module/API_CONTRACT.md`

Key endpoints:
- `GET /health`
- `GET /api/v1/news/{instrument}` (query: `limit`)
- `GET /api/v1/news/{instrument}/sentiment` (query: `hours`)
- `POST /api/v1/news/collect`

Example curl (news):
```bash
curl -sS "http://localhost:8005/api/v1/news/BANKNIFTY?limit=5" | jq .
```
Suggested healthcheck command for compose (matches existing):
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request,sys;urllib.request.urlopen('http://localhost:8005/health', timeout=5).read();sys.exit(0)"]
```

---

### Engine API (engine_module)
- Base URL: http://localhost:8006
- FastAPI docs: http://localhost:8006/docs
- Contract: `engine_module/API_CONTRACT.md`

Key endpoints:
- `GET /health`
- `POST /api/v1/analyze` (body: { instrument, context })
- `GET /api/v1/signals/{instrument}`
- `POST /api/v1/orchestrator/initialize`

Example curl (signals):
```bash
curl -sS http://localhost:8006/api/v1/signals/BANKNIFTY | jq .
```
Compose healthcheck pattern (already used in repo):
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request,sys;urllib.request.urlopen('http://localhost:8006/health', timeout=5).read();sys.exit(0)"]
```

---

### Dashboard (UI & dashboard_pro)
- UI base: http://localhost:8888 (dashboard-service)
- backend APIs (`dashboard_pro`) also available on ports 8001, 8002, 8003 mapped to container port 8000
- FastAPI UI docs: `http://localhost:8888/docs` and per-backend `http://localhost:8001/docs` (etc.)
- Dashboard contract: not a single `API_CONTRACT.md` (consider adding one); primary endpoints live in `dashboard/app.py`

Important endpoints:
- `GET /api/health` — core health used by orchestrator and compose checks
- `GET /api/latest-analysis`, `/api/latest-signal`, `/api/market-data`
- `GET /api/trading/*` (signals, positions, stats)
- `GET /api/technical-indicators`, `/api/options-chain`

Example health curl (dashboard):
```bash
curl -sS http://localhost:8888/api/health | jq .
```

---

### Background workers & collectors
- LTP collectors, depth collectors, orchestrator, automatic trading service are long-running processes. Some already expose HTTP endpoints (e.g., market-data) and some are process-only (orchestrator).
- For process-only services, current compose uses `pgrep -f 'python.*orchestrator'` style checks — acceptable for ensuring the process is running but does not validate functional health (connectivity to Redis/Mongo/LLMs).

Recommendation:
- Standardize Docker healthchecks to call the HTTP `/health` endpoint for services that expose an HTTP interface (market-data, engine, news, dashboard, backend-*). Keep process checks for services without an HTTP interface (or add a small admin `/health` endpoint) so healthchecks validate functional health rather than only process liveness.

---

## Recommended changes & next steps
1. Create or normalize `API_CONTRACT.md` for `dashboard` (add short listing for public endpoints) — helps consumers and tests. (todo #5)
2. Standardize docker healthchecks to always use `/health` for HTTP-capable services (todo #3). Use the same check pattern used in existing compose file.
3. Add example curl commands and OpenAPI links to each `API_CONTRACT.md` (I can update these files). (todo #4 ongoing)
4. Add integration tests that validate `/health` and 1–2 key endpoints per service (todo #6).

---

## Quick QA checklist (for publishing)
- [ ] All services have `GET /health` or an agreed process check
- [ ] `docker-compose.yml` uses healthchecks calling the right endpoints/commands
- [ ] `API_INDEX.md` and module `API_CONTRACT.md` files are up-to-date and include `/docs` links
- [ ] Automated integration tests validate health and a sample endpoint for each service

---

If this looks good I will:
- Finalize the `API_INDEX.md` (this file) with small edits per your feedback, and
- Continue by updating the `API_CONTRACT.md` files with OpenAPI `/docs` links and sample curl commands, and then
- Propose the concrete `docker-compose.yml` healthcheck edits as a follow-up change (so we can review before applying).

Would you like me to proceed to update the per-module contracts next, or prepare the docker-compose healthcheck edits first?