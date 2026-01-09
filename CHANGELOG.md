# Changelog

## 2026-01-09 — Real-time Signal Robustness & Pub/Sub Improvements

- Added Redis pub/sub publishing of indicator updates in Market Data (`indicators:{instrument}`) to enable loosely-coupled signal monitoring.
- Persisted previous indicator values for cross detection to Redis key: `indicators_prev:{instrument}:{indicator}` (TTL 4 hours) — used by `SignalMonitor` to evaluate `CROSSES_ABOVE/CROSSES_BELOW` robustly.
- RealtimeSignalProcessor subscribes to `indicators:*` and triggers `SignalMonitor.check_signals(instrument)` on updates (async or threaded fallback).
- Added Engine API endpoints for signals:
  - `GET /api/v1/signals/by-id/{signal_id}`
  - `POST /api/v1/signals/mark-executed`
- Dashboard `POST /api/trading/execute/{signal_id}` now fetches full signal, executes trade via `user_module` and marks the signal executed on success.
- Added unit tests covering pub/sub publishing and cross-detection: `tests/unit/test_signal_pubsub_and_cross.py`.
- Documentation: added `docs/SIGNAL_LIFECYCLE.md`, `docs/SIGNALS_API_USAGE.md`, and updated `README.md`, `engine_module/README.md`, `market_data/EXTERNAL_DEPENDENCIES.md`, and `API_ENDPOINTS_SUMMARY.md`.

Notes: This change improves resilience for cross-conditions and decouples indicator producers and signal consumers via Redis pub/sub. Future improvements may include Redis Streams for durable event replay.