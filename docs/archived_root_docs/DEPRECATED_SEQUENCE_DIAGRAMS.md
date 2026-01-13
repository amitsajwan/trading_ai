# Sequence Diagrams - Realtime Integration Plan

## 1. Signal Creation and Publishing Flow

```
┌─────────────┐    ┌─────────────────┐    ┌─────────────┐    ┌─────────────┐
│   Agent     │    │  Signal Creator │    │   MongoDB   │    │    Redis    │
│  Analysis   │    │                 │    │             │    │  Pub/Sub    │
└──────┬──────┘    └───────┬─────────┘    └──────┬──────┘    └──────┬──────┘
       │                   │                     │                   │
       │ 1. Analysis       │                     │                   │
       │    Complete       │                     │                   │
       │------------------>│                     │                   │
       │                   │                     │                   │
       │                   │ 2. Create Signals   │                   │
       │                   │    from Decision    │                   │
       │                   │---------------------│                   │
       │                   │                     │                   │
       │                   │ 3. Save to MongoDB │                   │
       │                   │-------------------->│                   │
       │                   │                     │                   │
       │                   │ 4. Publish to Redis │                   │
       │                   │-------------------->│                   │
       │                   │                     │                   │
┌─────────────┐    ┌─────────────────┐    ┌─────────────┐    ┌─────────────┐
│ WS Gateway  │    │   Frontend      │    │   Redux     │    │     UI      │
│             │    │   useWebSocket  │    │   Store     │    │             │
└──────┬──────┘    └───────┬─────────┘    └──────┬──────┘    └──────┬──────┘
       │                   │                     │                   │
       │ 5. Forward to WS  │                     │                   │
       │<-------------------│                     │                   │
       │                   │                     │                   │
       │                   │ 6. Receive Message  │                   │
       │                   │-------------------->│                   │
       │                   │                     │                   │
       │                   │ 7. Update Redux     │                   │
       │                   │-------------------->│                   │
       │                   │                     │                   │
       │                   │ 8. Re-render UI     │                   │
       │                   │-------------------->│                   │
```

**Timing:** Steps 1-4: ~50ms, Steps 5-8: ~100ms
**Total Latency:** <200ms end-to-end

---

## 2. Real-time Signal Monitoring and Execution Flow

```
┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐
│ Market Data │    │ Indicators      │    │  SignalMonitor  │    │   Trade     │
│   Tick      │    │   Service       │    │                 │    │  Execution  │
└──────┬──────┘    └───────┬─────────┘    └───────┬─────────┘    └──────┬──────┘
       │                   │                     │                     │
       │ 1. Tick Arrives   │                     │                     │
       │ (100-200ms)       │                     │                     │
       │------------------>│                     │                     │
       │                   │                     │                     │
       │                   │ 2. Update           │                     │
       │                   │    Indicators       │                     │
       │                   │---------------------│                     │
       │                   │                     │                     │
       │                   │ 3. Check Signals    │                     │
       │                   │-------------------->│                     │
       │                   │                     │                     │
       │                   │ 4. Condition Met?   │                     │
       │                   │<--------------------│                     │
       │                   │                     │                     │
       │                   │ 5. Execute Trade    │                     │
       │                   │-------------------->│                     │
       │                   │                     │                     │
┌─────────────┐    ┌─────────────────┐    ┌─────────────┐    ┌─────────────┐
│    Redis    │    │  WS Gateway     │    │  Frontend   │    │    UI       │
│  Pub/Sub    │    │                 │    │             │    │  Feedback   │
└──────┬──────┘    └───────┬─────────┘    └──────┬──────┘    └──────┬──────┘
       │                   │                     │                   │
       │ 6. Publish Status │                     │                   │
       │<------------------│                     │                   │
       │                   │                     │                   │
       │                   │ 7. Forward Update   │                   │
       │                   │-------------------->│                   │
       │                   │                     │                   │
       │                   │ 8. Update UI        │                   │
       │                   │-------------------->│                   │
       │                   │                     │                   │
       │                   │ 9. Show Execution   │                   │
       │                   │-------------------->│                   │
```

**Timing:** Steps 1-5: <50ms, Steps 6-9: <100ms
**Total Latency:** <200ms for signal execution feedback

---

## 3. WebSocket Connection and Reconnection Flow

```
┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐
│  Frontend   │    │  WS Gateway     │    │    Redis       │    │   UI State   │
│             │    │                 │    │  Pub/Sub       │    │             │
└──────┬──────┘    └───────┬─────────┘    └──────┬─────────┘    └──────┬──────┘
       │                   │                     │                     │
       │ 1. Connect WS     │                     │                     │
       │------------------>│                     │                     │
       │                   │                     │                     │
       │ 2. Authenticate    │                     │                     │
       │<------------------│                     │                     │
       │                   │                     │                     │
       │ 3. Subscribe       │                     │                     │
       │------------------>│                     │                     │
       │                   │                     │                     │
       │ 4. Start Heartbeat │                     │                     │
       │<------------------>│                     │                     │
       │                   │                     │                     │
       │ 5. Forward Messages│                     │                     │
       │<------------------│                     │                     │
       │                   │                     │                     │
       │                   │ 6. Connection Lost  │                     │
       │                   │---------------------│                     │
       │                   │                     │                     │
       │ 7. Show Reconnecting│                    │                     │
       │------------------>│                     │                     │
       │                   │                     │                     │
       │ 8. Exponential      │                    │                     │
       │    Backoff          │                     │                     │
       │---------------------│                     │                     │
       │                   │                     │                     │
       │ 9. Reconnect        │                     │                     │
       │------------------>│                     │                     │
       │                   │                     │                     │
       │ 10. Resubscribe     │                     │                     │
       │------------------>│                     │                     │
       │                   │                     │                     │
       │ 11. Resume Updates  │                    │                    │
       │<------------------│                     │                     │
```

**Timing:** Normal operation: continuous, Reconnection: 1s-30s exponential backoff

---

## 4. Error Handling and Fallback Flow

```
┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐
│   System    │    │   WebSocket     │    │   Frontend      │    │   Fallback   │
│   Issue     │    │   Gateway       │    │                 │    │   Polling    │
└──────┬──────┘    └───────┬─────────┘    └──────┬──────┘    └──────┬──────┘
       │                   │                     │                   │
       │ 1. WS Gateway     │                     │                   │
       │    Down           │                     │                   │
       │------------------>│                     │                   │
       │                   │                     │                   │
       │                   │ 2. Connection Fail  │                   │
       │                   │-------------------->│                   │
       │                   │                     │                   │
       │                   │ 3. Reconnection     │                   │
       │                   │    Attempts         │                   │
       │                   │<--------------------│                   │
       │                   │                     │                   │
       │                   │ 4. Max Attempts     │                   │
       │                   │    Reached          │                   │
       │                   │-------------------->│                   │
       │                   │                     │                   │
       │                   │ 5. Switch to        │                   │
       │                   │    Polling          │                   │
       │                   │-------------------->│                   │
       │                   │                     │                   │
       │                   │ 6. REST API Calls   │                   │
       │                   │-------------------->│                   │
       │                   │                     │                   │
       │                   │ 7. Reduced Update   │                   │
       │                   │    Frequency        │                   │
       │                   │-------------------->│                   │
       │                   │                     │                   │
       │                   │ 8. Show Degraded    │                   │
       │                   │    Mode Warning     │                   │
       │                   │-------------------->│                   │
```

**Timing:** Detection: <5s, Fallback activation: <30s, Polling interval: 5-30s

---

## 5. High Load and Backpressure Flow

```
┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐
│ High Load   │    │  WS Gateway     │    │   Frontend      │    │   UI        │
│  Scenario   │    │                 │    │                 │    │  Adaptation │
└──────┬──────┘    └───────┬─────────┘    └──────┬──────┘    └──────┬──────┘
       │                   │                     │                   │
       │ 1. Message Storm  │                     │                   │
       │------------------>│                     │                   │
       │                   │                     │                   │
       │                   │ 2. Rate Limiting    │                   │
       │                   │    Applied          │                   │
       │                   │---------------------│                   │
       │                   │                     │                   │
       │                   │ 3. Queue Depth      │                   │
       │                   │    Monitor          │                   │
       │                   │---------------------│                   │
       │                   │                     │                   │
       │                   │ 4. Drop Non-        │                   │
       │                   │    Critical         │                   │
       │                   │---------------------│                   │
       │                   │                     │                   │
       │                   │ 5. Debounce         │                   │
       │                   │    Updates          │                   │
       │                   │-------------------->│                   │
       │                   │                     │                   │
       │                   │ 6. Reduce Update    │                   │
       │                   │    Frequency        │                   │
       │                   │-------------------->│                   │
       │                   │                     │                   │
       │                   │ 7. Show Load        │                   │
       │                   │    Warning          │                   │
       │                   │-------------------->│                   │
       │                   │                     │                   │
       │                   │ 8. Virtual Scrolling│                   │
       │                   │-------------------->│                   │
```

**Timing:** Detection: <1s, Adaptation: <5s, Recovery: automatic when load decreases

---

## Legend

**Actors/Components:**
- **Agent Analysis**: Periodic trading strategy analysis (15-min cycles)
- **Signal Creator**: Converts analysis results to conditional signals
- **MongoDB**: Persistent signal storage
- **Redis Pub/Sub**: Real-time message bus
- **WS Gateway**: WebSocket forwarding service
- **Frontend**: React application
- **SignalMonitor**: Real-time condition evaluation
- **Trade Execution**: Order placement service
- **Indicators Service**: Technical analysis calculations

**Message Types:**
- `------>` : Synchronous call/request
- `----->` : Asynchronous message/publish
- `<-----` : Response/reply
- `<---->` : Bidirectional communication

**Timing Annotations:**
- **<50ms**: Real-time processing
- **<200ms**: UI update latency
- **<500ms**: End-to-end latency target
- **1s-30s**: Reconnection backoff
- **5-30s**: Fallback polling interval</content>
<parameter name="filePath">c:\code\zerodha\SEQUENCE_DIAGRAMS.md