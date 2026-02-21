# Event Derivation Contract (X → Y* → L*)

Defines a simple, explicit event model for this codebase:

- `X`: base source stream (raw market/tick events)
- `Y1/Y2/Y3`: independent derived streams from `X`
- `LY1/LZ1`: low-latency event streams derived from `Y1` or `Z1`

This contract is intentionally stream-first and timestamp-explicit to avoid cross-stream ambiguity.

## Why this exists

We previously had mixed timing semantics (transport freshness vs market-time freshness) across stream consumers.
This contract separates derivations and requires explicit timestamp semantics for every stream.

## Topology

```text
X (base tick/source event)
├── Y1 (canonical OHLC snapshots / candle state)
│   └── LY1 (low-latency candle micro-updates)
├── Y2 (indicator snapshots)
│   └── LZ1 (low-latency indicator updates)
└── Y3 (other independent derivations, e.g., depth/options analytics)
```

> `Y*` streams are independent products of `X` (or a canonical aggregate).
> `L*` streams are high-cadence updates with their own timestamps and ordering.

## Mandatory envelope for ALL events

Every pub/sub payload SHOULD include these fields.

| Field | Type | Meaning |
|---|---|---|
| `event_id` | string | Unique event id (UUID/ULID) |
| `stream` | string | Logical stream name (`X`, `Y1`, `LY1`, etc.) |
| `instrument` | string | Normalized instrument |
| `timeframe` | string/null | Timeframe when applicable (`1min`, `5min`, ...) |
| `event_time` | string (ISO-8601) | Time represented by the data point |
| `emitted_at` | string (ISO-8601) | Time event was published |
| `source_event_id` | string/null | Upstream lineage id |
| `mode` | string | `live` / `historical` / `paper` |
| `run_id` | string/null | Required for replay/backtest lineage |
| `schema_version` | string | Envelope+payload schema version |
| `payload` | object | Stream-specific data |

### Timestamp semantics

- `event_time`: **data time** (market/replay clock).
- `emitted_at`: **processing time** (when this stream emitted).

Never reuse one field for both meanings.

## Current channel mapping in this repo

### Redis channels (observed)

- `auth:status`
- `market:tick:{INSTRUMENT}:{TYPE}`
- `tick:{INSTRUMENT}` (legacy/generic)
- `raw_ticks:{INSTRUMENT}` (legacy/raw)
- `market:ohlc:{INSTRUMENT}:{TIMEFRAME}`
- `indicators:{INSTRUMENT}:{TYPE}`

### STOMP destinations (dashboard bridge)

- `/topic/auth/status` → `auth:status`
- `/topic/market/ohlc/{instrument}` → `market:ohlc:{instrument}:*`
- `/topic/market/ohlc/{instrument}/{timeframe}` → `market:ohlc:{instrument}:{timeframe}`
- `/topic/market/tick/{instrument}` → `market:tick:{instrument}:*`
- `/topic/indicators/{instrument}` → `indicators:{instrument}:*`

## Stream definitions for this system

### X: Base source ticks

- Source: websocket/Kite tick collector
- Channel: `market:tick:{instrument}:{type}`
- Required payload characteristics:
  - raw tick values
  - canonical market timestamp fields
  - `event_time = market_timestamp`
  - `emitted_at = publish time`

### Y1: Canonical candle state (time-bucketed)

- Source: candle aggregation from `X`
- Channel: `market:ohlc:{instrument}:{timeframe}`
- Recommended payload extras:
  - `bucket_start`
  - `candle_closed` (bool)
  - `sequence` (monotonic per instrument+timeframe)

### LY1: Candle low-latency updates

- Source: incremental updates to current open candle from Y1 pipeline
- Suggested channel: `market:ohlc_live:{instrument}:{timeframe}` (or include `intrabar=true` on Y1)
- Notes:
  - own cadence, own ordering, own `emitted_at`
  - same `event_time` bucket semantics as Y1

### Y2: Indicator snapshots

- Source: indicator service from OHLC/ticks
- Channel today: `indicators:{instrument}:{type}`
- Existing useful fields in repo:
  - `intrabar`, `candle_closed`, `update_type`
  - `indicator_stream=Y2`, `indicator_update_type`
  - `market_timestamp`, `indicator_timestamp`
  - mode-aware metadata (`mode`, `run_id`, `timeframe`)

### LZ1: Low-latency indicators

- Source: high-frequency indicator updates (usually tick-derived)
- Suggested representation:
  - either dedicated channel (`indicators_live:{instrument}:{type}`)
  - or explicit `stream = LZ1` and `update_type = tick` in existing indicators channel
- UI semantics:
  - `Source` should map to calculation source (`indicator_source`)
  - `Stream` should map to transport stream (`indicator_stream`)

### Y3: Independent derivations (depth/options/analytics)

- Keep as separate stream family with independent timestamps and freshness SLA.

## Ordering and deduplication rules

For each stream key (`stream + instrument + timeframe`):

1. `sequence` SHOULD be monotonic.
2. Consumer applies last-write-wins by:
   - higher `sequence`, else
   - newer `emitted_at`, else
   - deterministic tie-break (`event_id`).
3. Deduplicate by `event_id` (or payload hash as fallback).

## Thin-frontend contract

Frontend should:

- subscribe/render per-stream payloads
- never infer timestamps across streams
- never merge stream clocks implicitly
- display freshness from stream metadata, not guessed from wall-clock only

## Migration plan (incremental)

1. Add mandatory envelope fields in publisher paths (`tick`, `ohlc`, `indicators`).
2. Keep legacy fields for compatibility during rollout.
3. Add `sequence` per stream-key.
4. Optionally split low-latency streams into dedicated channels (`*_live:*`).
5. Update dashboard reducers to use `stream + sequence + event_time + emitted_at`.

## Practical defaults for this repo

- Keep existing Redis channel names for now.
- Add envelope fields without breaking current consumers.
- Use:
  - `event_time = market_timestamp`
  - `emitted_at = indicator_timestamp` for indicator events
- Preserve existing `intrabar/candle_closed/update_type` fields as stream hints.

---

Last updated: 2026-02-14
