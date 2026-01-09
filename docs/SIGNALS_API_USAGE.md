# Signals API / Integration Notes

This document provides practical examples for interacting with signals APIs and demonstrates how to mark a signal for execution or to check its conditions.

## Fetch a signal by id

GET http://localhost:8006/api/v1/signals/by-id/{signal_id}

Response (example):
```json
{
  "_id": "63d7...",
  "signal_id": "63d7...",
  "condition_id": "BANKNIFTY_BUY_abc123",
  "instrument": "BANKNIFTY",
  "indicator": "rsi_14",
  "operator": ">",
  "threshold": 32.0,
  "action": "BUY",
  "status": "pending",
  "created_at": "2026-01-09T10:00:00",
  "confidence": 0.78
}
```

## Mark a signal executed

POST http://localhost:8006/api/v1/signals/mark-executed?signal_id={signal_id}

Optional JSON body: `{ "execution_info": { "order_id": "...", "executed_price": 45100 } }`

Response: `{ "success": true, "signal_id": "..." }`

## Dashboard: Execute a signal now (example)

POST http://localhost:8888/api/trading/execute/{signal_id}

- The dashboard endpoint fetches the full signal (by-id), constructs a trade payload and calls the `user_module` trade execution endpoint.
- On success, it marks the signal executed in engine MongoDB via `POST /api/v1/signals/mark-executed`.

## Subscribe to indicators (Node / Python)

Example (Python, using redis-py):
```py
import redis, json
r = redis.Redis()
ps = r.pubsub()
ps.psubscribe('indicators:*')
for message in ps.listen():
    if message and message['type'] in ('message', 'pmessage'):
        ch = message['channel']
        raw = message['data']
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {}
        # payload contains instrument, rsi_14, macd_value etc.
        instrument = payload.get('instrument')
        # Trigger check on your monitor for the instrument
```

---

For runbook and tests, see `tests/unit/test_signal_pubsub_and_cross.py` and `docs/SIGNAL_LIFECYCLE.md`.