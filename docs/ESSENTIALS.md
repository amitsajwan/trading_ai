Zerodha GenAI Trading — Essentials

Overview
- Purpose: a compact guide to get a developer or operator started quickly.
- Keep this short; for detailed design/history, archived docs were deleted and compressed backups were permanently removed on 2026-01-03. Contact maintainers to request a restore.

Quick Start (Dev)
1. Create a venv and install deps:
   # Windows
   python -m venv .venv
   .\.venv\Scripts\activate
   # macOS/Linux
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

2. Set up essential environment variables and credentials:
   - Copy `.env.example` to `.env` and add your API/LLM keys (e.g. `GROQ_API_KEY`, `OPENAI_API_KEY`)
   - Copy `credentials.example.json` to `credentials.json` and fill Zerodha credentials, or run `python auto_login.py` to fetch them
   - Example values:
     LLM_PROVIDER=groq
     GROQ_API_KEY=...
     MONGODB_URI=mongodb://localhost:27017
     REDIS_HOST=localhost

3. Run tests and lint locally:
   # From project root with venv activated
   python -m pytest -q -s

Run System (local dev)
- Start services for a quick local system (crypto):
  # Recommended (explicit flag):
  python scripts/start_all.py --instrument BTC
  # Backwards-compatible form (still supported):
  python scripts/start_all.py BTC
- To start without verifying live data (useful for testing):
  python scripts/start_all.py --skip-data-verification --instrument BTC
- Check system health (preferred):
  python scripts/monitor/verify_all_components.py
  # Backwards-compatible:
  python scripts/quick_check.py

Prerequisites before starting:
- Ensure `.env` and `credentials.json` are configured (see above).
- Start Redis and MongoDB if running locally (or ensure they are accessible):
  - Redis: `redis-server` or use Docker `docker run -d -p 6379:6379 redis`
  - MongoDB: `mongod` or use Docker
- If using a local Ollama provider, start it with `ollama serve` or set an LLM cloud provider in `.env`.

Important Files
- `docs/IMPLEMENTATION_COMPLETE.md` — authoritative design decisions
- `docs/DEPLOYMENT_CHECKLIST.md` — production steps
- `docs/API.md` — API reference
- `docs/ARCHITECTURE.md` — system architecture

Maintenance
- Keep `docs/ESSENTIALS.md` short and actionable.
- Historical notes, deep investigation docs, and draft proposals were archived; compressed backups were permanently removed on 2026-01-03 to reduce clutter.
- To restore an archived doc, extract the zip and move files back to `docs/`.

Contact
- For doc restores or questions, contact the repository maintainers or open an issue in your project tracking system.
