# engine_module — Trading Orchestrator

**Status:** Active & maintained (docs consolidated on 2026-01-09)

A concise overview of the trading orchestrator used to run multi-agent analysis cycles and produce trading signals.

---

## Quick links
- Code: `engine_module/src/`
- API contract: `engine_module/API_CONTRACT.md`
- Examples & scripts: `scripts/run_one_cycle.py`, `examples/demo_orchestrator.py`
- Tests: `engine_module/tests/` (run with `pytest engine_module/tests/ -v`)
- Archived in-depth docs: `engine_module/docs/archived/` (moved on 2026-01-09)

---

## Quickstart
1. Copy env example:

   ```bash
   cp engine_module/.env.example engine_module/.env
   ```

2. (Optional) Start local services (Redis, MongoDB, market data) via `start_local.py` or Docker compose.

3. Run one cycle (useful for debugging):

   ```bash
   python scripts/run_one_cycle.py
   ```

4. Run orchestrator continuously:

   ```bash
   python run_orchestrator.py
   ```

5. Run tests:

   ```bash
   pytest engine_module/tests/ -v
   ```

---

## Where to find more details
- Implementation & contracts: `engine_module/src/`
- API endpoints: `engine_module/API_CONTRACT.md`
- Examples: `examples/demo_orchestrator.py`, `scripts/debug_llm_override.py`
- Archived deep dives (position-awareness, strategies, test summaries): `engine_module/docs/archived/`

---

*This concise README lives alongside `engine_module/README.md` as the streamlined entry point; detailed design notes were archived into `engine_module/docs/archived/` to reduce duplication and keep docs actionable.*