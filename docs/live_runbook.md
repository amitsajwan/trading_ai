# Live Market Runbook (Zerodha stack)

Authoritative steps to switch from historical replay/mock to **live** market data, validate health, and roll back if needed.

## 1) Prerequisites
- `market_data/.env.banknifty` contains `KITE_API_KEY` and a valid `access_token` (or you’re ready to run the auth flow).
- `INSTRUMENT_SYMBOL` set to the live contract you want (current default: `BANKNIFTY26FEBFUT`).
- No mock publisher running; Redis reachable.
- Timezone: stack assumes IST for market hours.

## 2) Fast path (automated)
- Run **one command**: `python start_unified.py --live`
- This now does the following automatically:
  - Stops historical replay.
  - Clears virtual time flags in Redis.
  - Wipes OHLC for `INSTRUMENT_SYMBOL` (default `BANKNIFTY26FEBFUT`) so you don’t see stale historical bars.
  - Starts live docker services: `redis`, `redis-ws-gateway`, `market-data-api`, `market-data-dashboard`, `ltp-collector-banknifty`.
  - Tries Kite auth: validates existing token; if missing/expired, triggers interactive login (falls back to legacy prompt if helper unavailable).

## 3) Manual path (if you prefer explicit steps)
1. Stop historical replay: `docker-compose stop historical-replay-service`
2. Stop any mock publishers (if running) and the mock data collector, if applicable.
3. Clear virtual time flags (only if historical replay was using virtual time):
   - `docker-compose exec redis redis-cli DEL system:virtual_time:enabled system:virtual_time:current`
4. Clear old OHLC data for a clean live-only view:
   - `docker-compose exec redis redis-cli DEL ohlc_sorted:<INSTRUMENT>:1min`
   - `docker-compose exec redis sh -c "redis-cli KEYS 'ohlc:<INSTRUMENT>:1min:*' | xargs -r redis-cli DEL"`
5. Ensure env is live (no virtual time): `ENV=LIVE`, `DATA_SOURCE=ZERODHA`, `USE_VIRTUAL_TIME` unset/0.
6. Start required services:
   - `docker-compose up -d redis redis-ws-gateway market-data-api market-data-dashboard ltp-collector-banknifty`
   - Or use the unified script: `python start_unified.py --live`
7. If Kite token is expired/missing and the unified script couldn’t auto-refresh, run:
   - `python kite_auth_service.py` (or `python -m market_data.tools.kite_auth`) to update `credentials.json`.

## 4) Verify data is flowing
- Collector logs: `docker logs zerodha-ltp-collector-banknifty --tail 50`
- Quick tick check: `python monitor_raw_ticks.py`
- API health: `curl http://localhost:8008/api/market-data/status` (should show non-stale, recent timestamps)
- OHLC check: `curl "http://localhost:8004/api/v1/market/ohlc/BANKNIFTY26FEBFUT?timeframe=minute&limit=200&order=desc"`

## 5) Dashboard / Price Chart
- Open dashboard (port 8008). It auto-refreshes via WebSocket; no manual refresh needed.
- Charts request ascending OHLC with large limits; full session should render once live bars arrive.

## 6) Troubleshooting
- **Status stays stale**: ensure collector is running and credentials/token are valid; check Redis connectivity in collector logs.
- **401/403 from Kite**: refresh access token via auth flow; restart collector.
- **No WebSocket updates**: confirm `redis-ws-gateway` is running and reachable (port 8889). Fallback: reload dashboard; data still loads via REST.
- **Old virtual time persists**: delete `system:virtual_time:enabled` and `system:virtual_time:current` keys in Redis.
- **Need fresh dataset**: clear OHLC keys as in step 2.4, then restart live stack.

## 7) Switching back to historical (reference)
- Stop live collector if desired: `docker-compose stop ltp-collector-banknifty`
- Start historical replay with date: `python start_unified.py --historical --date YYYY-MM-DD` **or** `docker-compose up -d historical-replay-service`
- If using virtual time, set `USE_VIRTUAL_TIME=1` and ensure dashboard filters by virtual time (already supported). Remember to clear virtual time keys before returning to live.

Keep this file updated when changing service names, ports, or env flags.
