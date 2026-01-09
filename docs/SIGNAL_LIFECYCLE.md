# Signal Lifecycle & Real-time Integration

This document describes the signal lifecycle (engine decisions → conditional signals → real-time monitoring → execution) and the Redis pub/sub and key conventions used for real-time integration.

## High-level lifecycle

1. Orchestrator runs a 15-minute analysis cycle and emits an AnalysisResult.
2. `signal_creator.create_signals_from_decision()` converts the AnalysisResult into one or more `TradingCondition` objects and saves them to MongoDB (`signals` collection) with `status: "pending"`.
3. A lightweight message containing the signal is published to Redis (channel `engine:signal` and `engine:signal:{instrument}`) for UI and monitoring consumers.
4. `SignalMonitor` is responsible for monitoring `TradingCondition`s and evaluating them against the latest technical indicators.
5. `RealtimeSignalProcessor` subscribes to Redis indicator updates and calls `SignalMonitor.check_signals(instrument)` on each update.
6. When a signal triggers (`CROSSES_ABOVE`, `GREATER_THAN`, ...), a `SignalTriggerEvent` is created and an execution callback is invoked.
7. The executor posts the trade to the `user_module` (or engine fallback) and the signal is marked executed in MongoDB.

---

## Redis key & channel conventions

- Indicator keys (TTL: 5 minutes)
  - Key: `indicators:{INSTRUMENT}:{INDICATOR_NAME}`
  - Example: `indicators:BANKNIFTY:rsi_14` = `32.5`

- Indicator publish channel (pub/sub)
  - Channel: `indicators:{INSTRUMENT}` (JSON payload)
  - Example message payload (JSON):
    {
      "instrument": "BANKNIFTY",
      "timestamp": "2026-01-09T10:00:00",
      "current_price": 45050.0,
      "rsi_14": 32.5,
      "macd_value": 12.3,
      "macd_signal": 11.1,
      "adx_14": 27.5
    }

- Persisted previous indicator value (used for CROSSES detection) — TTL configurable (default 4 hours)
  - Key: `indicators_prev:{INSTRUMENT}:{INDICATOR_NAME}`
  - Purpose: store previous value across restarts so `CROSSES_ABOVE`/`CROSSES_BELOW` logic is robust
  - Example: `indicators_prev:BANKNIFTY:rsi_14` = `29.0`

- Engine signal pub/sub topics
  - Signal publish channels: `engine:signal` (global) and `engine:signal:{INSTRUMENT}`
  - Messages carry the saved `signal_id` (Mongo `_id`) and condition details

---

## New/Updated API Endpoints (Engine)

- `GET /api/v1/signals/{instrument}` — Fetch recent signals (existing)
- `GET /api/v1/signals/by-id/{signal_id}` — Fetch full signal document by `_id` or `condition_id` (new)
- `POST /api/v1/signals/mark-executed` — Mark a saved signal as executed (new)

Dashboard endpoints updated:
- `POST /api/trading/execute/{signal_id}` — Now fetches the full signal, builds a trade payload, sends to `user_module` and marks the signal executed on success.
- `POST /api/trading/execute-when-ready/{signal_id}` — Syncs the signal to the local SignalMonitor so it will be monitored and executed automatically.

---

## Notes on robust cross detection

- `CROSSES_ABOVE` / `CROSSES_BELOW` rely on a previous value; previously this was stored only in memory (lost on restart).
- We persist previous indicator value to Redis key `indicators_prev:{instrument}:{indicator}` with TTL (default 4 hours) to survive process restarts and support multi-worker setups.

---

## Implementation references

- Signal creation: `engine_module/src/engine_module/signal_creator.py`
- Signal monitor and evaluation: `engine_module/src/engine_module/signal_monitor.py`
- Realtime integration and pub/sub listener: `engine_module/src/engine_module/realtime_signal_integration.py`
- Technical indicators publishing: `market_data/src/market_data/technical_indicators_service.py`
- Dashboard execute wiring: `dashboard/api/trading.py`

---

## Testing & Validation

- Unit tests added: `tests/unit/test_signal_pubsub_and_cross.py` (covers pub/sub publishing and cross-detection persistence)
- Integration tests should exercise: indicator publish → SignalMonitor subscription → trigger → executor → `signals` document marked executed

---

## Quick troubleshooting

- If signals never trigger: ensure `indicators:{instrument}` messages are being published and that `indicators_prev:` keys are either present or update correctly.
- Check Redis connectivity (REDIS_HOST/REDIS_PORT env vars)
- Check MongoDB connectivity and ensure `signals` collection is present

---

For any further refinements (e.g., Redis Streams for durability), suggest creating an enhancement ticket and we can follow up with a streams-based consumer group implementation.