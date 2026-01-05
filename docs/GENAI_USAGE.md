# GenAI Usage and Enablement Guide

This document explains how GenAI providers are used, how to enable/disable them safely, and the recommended default configuration for this project.

## Where GenAI Is Used

- Agents layer (`agents/`):
  - `portfolio_manager.py` optional LLM veto / reasoning
  - `review_agent.py`, `fundamental_agent.py`, `macro_agent.py` summarization and narrative generation
- Strategy generation:
  - `engines/strategy_planner.py` calls the LLM to propose candidate trading rules based on market context
- Dashboard health:
  - `/api/metrics/llm` surfaces provider health and usage metrics

The system remains fully functional without GenAI for data ingestion, option chain analytics, risk, and UI. GenAI augments analysis and rule generation.

## Recommended Default Provider

- Provider: Groq
- Model: `llama-3.1-8b-instant`
- Reason: Fast, cost-effective for reasoning/summarization; already integrated in `.env.*`

To enable only Groq and keep others disabled:
- Ensure `GROQ_API_KEY` is set
- Leave other provider keys empty or remove them from the environment

## Environment Configuration

Each environment file (`.env.banknifty`, `.env.nifty`, `.env.btc`) supports the following keys:

- `LLM_PROVIDER` (name of preferred provider, e.g., `groq`)
- `LLM_MODEL` (default model for that provider)
- `GROQ_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `COHERE_API_KEY`, `AI21_API_KEY`, `HUGGINGFACE_API_KEY`
- Per-provider model overrides: `GROQ_MODEL`, `OPENAI_MODEL`, etc.
- Daily token limits: `*_LIMIT` for health reporting and throttling

Example (Groq only):

```
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
GROQ_API_KEY=your_groq_key

# Optional: leave others blank to keep disabled
OPENAI_API_KEY=
GOOGLE_API_KEY=
COHERE_API_KEY=
AI21_API_KEY=
HUGGINGFACE_API_KEY=
```

## Enabling/Disabling Providers

- To disable a provider: remove or leave its API key blank. The health checker will mark it as unavailable and exclude it from routing.
- To enable a provider: set the API key and model; it will automatically be discovered by the LLM provider manager and appear in `/api/metrics/llm`.

## Operational Notes

- Health Panel in Dashboard shows provider status, tokens today, and usage percentage.
- Selection strategy defaults to hash/weighted; can be tuned via `LLM_SELECTION_STRATEGY`.
- Circuit breakers in the LLM manager prevent repeated failures from impacting user flows.

## Validation Steps

1. Set the `.env.*` for your service (e.g., `.env.banknifty`) to Groq-only as above.
2. Restart the backend service (e.g., `docker-compose up -d --build backend-banknifty`).
3. Visit `/api/metrics/llm` to verify `groq` is healthy and others are absent or degraded (as expected if empty).
4. Confirm rule generation works in logs (`engines/strategy_planner.py`) and dashboard analysis sections render.

## Security

- Never commit API keys.
- Prefer validating keys via environment or Docker secrets.
- Token usage is tracked and surfaced for transparency; set conservative limits in production.
