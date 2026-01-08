# Trading Cockpit

Complete user interface documentation for the Trading AI System dashboard.

## Overview

The Trading Cockpit is a professional web-based control panel for managing the autonomous trading system. It provides real-time monitoring, manual controls, and performance analytics.

## Quick Start

### Starting the Dashboard

```bash
# Local development
cd dashboard
python app.py

# Docker
docker-compose up dashboard-service

# Access at
http://localhost:8000
```

### Default View

The dashboard loads with:
- Current trading mode indicator
- System time & market status
- Active positions
- Recent trades
- Agent analysis feed
- System health metrics

## Main Interface Sections

### 1. Time & Market Status

**Location**: Top card

**Displays**:
- Current system time (IST)
- Time mode: Real-Time or Virtual (color-coded)
- Market status: OPEN or CLOSED
- Market hours: 9:15 AM - 3:30 PM IST
- Latest market data timestamp

**Color Coding**:
- 🟢 Green: Market open, real-time mode
- 🟡 Yellow: Virtual time active
- 🔴 Red: Market closed

### 2. Trading Mode Control

**Location**: Control Panel section

**Modes**:
- **Live**: Real trading with real money
- **Paper Live**: Paper trading with live data
- **Paper Mock**: Paper trading with historical or synthetic data

**Switching Modes**:
```bash
POST /api/control/mode/switch
{
    "mode": "paper_mock",
    "confirm": true,
    "historical_start_date": "2024-01-15"  # Optional
}
```

**Safety**:
- Requires confirmation for live mode
- Warns before mode switch
- Shows current mode prominently

### 3. Historical Replay Controls

**Location**: Historical Replay section (when in paper_mock)

**Features**:
- Date range selection
- Playback speed control (1x, 2x, 5x, 10x)
- Pause/Resume
- Skip ahead
- Reset to start

**Starting Replay**:
1. Switch to Paper Mock mode
2. Select start date
3. Set playback speed
4. Click "Start Replay"

**During Replay**:
- Virtual time displayed prominently
- Market data shows historical timestamps
- Agents analyze historical data
- All trades are simulated

### 4. Active Positions

**Location**: Positions panel

**Displays per position**:
- Instrument name
- Side (LONG/SHORT)
- Quantity
- Entry price
- Current price
- P&L (absolute and %)
- Duration (time held)
- Unrealized P&L

**Actions**:
- Close position (market order)
- Partial exit
- Update stop loss
- View position history

### 5. Trading Signals

**Location**: Signals panel

**Signal Information**:
- Signal ID
- Instrument
- Action (BUY/SELL)
- Condition (e.g., "RSI > 32")
- Current indicator value
- Status: Waiting / Triggered / Expired
- Created timestamp

**Signal States**:
- 🟡 **Waiting**: Condition not yet met
- 🟢 **Ready**: Condition met, can execute
- 🔵 **Executing**: Trade being placed
- ✅ **Triggered**: Trade executed
- ⏰ **Expired**: Time limit reached
- ❌ **Cancelled**: Manually cancelled

**Actions**:
- Execute manually
- Cancel signal
- Modify condition
- View details

### 6. Agent Analysis Feed

**Location**: Agent Output panel

**Displays**:
- Timestamp
- Agent name (Momentum/Trend/MeanRev/Volume)
- Decision (BUY/SELL/HOLD)
- Confidence level (0-100%)
- Reasoning
- Key indicators used

**Example**:
```
[10:15:32] Momentum Agent - BUY (85%)
  Reasoning: Strong upward momentum with volume confirmation
  RSI: 72.4, Volume Ratio: 1.8x, MACD: Positive crossover
```

**Filtering**:
- By agent type
- By decision type
- By confidence level
- By time range

### 7. Recent Trades

**Location**: Trades History panel

**Trade Details**:
- Trade ID
- Timestamp
- Instrument
- Side (BUY/SELL)
- Quantity
- Entry price
- Exit price (if closed)
- P&L
- Status
- Agent that triggered

**Export**:
- CSV export
- PDF report
- Excel format

### 8. System Health

**Location**: Health Metrics panel

**Metrics**:
- MongoDB: Connected/Disconnected
- Redis: Connected/Disconnected
- Kite API: Active/Inactive
- Orchestrator: Running/Stopped
- Historical Replay: Active/Inactive

**Error Indicators**:
- 🔴 Red: Critical error, requires attention
- 🟡 Yellow: Warning, degraded performance
- 🟢 Green: All systems operational

### 9. Performance Analytics

**Location**: Analytics section

**Charts**:
- Equity curve
- Daily P&L
- Win rate over time
- Sharpe ratio
- Drawdown

**Statistics**:
- Total trades
- Win rate
- Average win/loss
- Profit factor
- Max drawdown
- Sharpe ratio
- Sortino ratio

## API Endpoints

### Trading Control

```bash
# Get current mode
GET /api/control/mode

# Switch mode
POST /api/control/mode/switch
{
    "mode": "paper_mock",
    "confirm": true
}

# Stop trading
POST /api/control/stop
```

### Positions

```bash
# Get all positions
GET /api/positions

# Close position
POST /api/positions/{position_id}/close

# Partial exit
POST /api/positions/{position_id}/exit
{
    "quantity": 25
}
```

### Signals

```bash
# Get active signals
GET /api/signals/active

# Create signal
POST /api/signals
{
    "instrument": "BANKNIFTY",
    "condition": "rsi_14 > 50",
    "action": "BUY"
}

# Cancel signal
DELETE /api/signals/{signal_id}
```

### Historical Replay

```bash
# Start replay
POST /api/historical/start
{
    "start_date": "2024-01-15",
    "end_date": "2024-01-31",
    "speed": 10
}

# Control playback
POST /api/historical/pause
POST /api/historical/resume
POST /api/historical/stop
```

### System Time

```bash
# Get current time
GET /api/system-time

# Set virtual time
POST /api/system-time/set
{
    "datetime": "2026-01-06T10:00:00"
}

# Clear virtual time
POST /api/system-time/clear
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+S` | Toggle signals panel |
| `Ctrl+P` | Toggle positions panel |
| `Ctrl+H` | Toggle historical replay |
| `Ctrl+R` | Refresh data |
| `Space` | Pause/Resume orchestrator |
| `Esc` | Close modal dialogs |

## Mobile View

Dashboard is responsive and works on mobile devices:

- Collapsed sidebar
- Stacked panels
- Touch-friendly controls
- Simplified charts
- Essential info only

## Customization

### Theme

Toggle between light/dark mode in Settings.

### Panel Layout

Drag and drop panels to rearrange:
1. Click panel header
2. Drag to new position
3. Release to drop
4. Layout saved automatically

### Refresh Rate

Configure update frequency:
- Real-time (100ms)
- Fast (500ms)
- Normal (1s)
- Slow (5s)

## WebSocket Connection

Dashboard uses WebSocket for real-time updates:

```javascript
// Connect
const ws = new WebSocket('ws://localhost:8000/ws');

// Receive updates
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'tick') {
        updatePrice(data.instrument, data.price);
    } else if (data.type === 'signal_triggered') {
        showNotification(data.signal);
    } else if (data.type === 'trade_executed') {
        addTrade(data.trade);
    }
};
```

## Troubleshooting

### Dashboard not loading

1. Check if service is running:
   ```bash
   docker ps | grep dashboard
   ```

2. Check logs:
   ```bash
   docker logs zerodha-dashboard-service
   ```

3. Verify port not in use:
   ```bash
   netstat -ano | findstr :8000
   ```

### Data not updating

1. Check WebSocket connection in browser console
2. Verify orchestrator is running
3. Check Redis connection
4. Verify market hours (no updates when market closed)

### Mode switch not working

1. Verify confirmation parameter sent
2. Check current mode allows switching
3. Review orchestrator logs
4. Ensure no active positions (for live mode)

### Historical replay not starting

1. Verify date range is valid
2. Check historical data service running
3. Verify MongoDB has historical data
4. Check virtual time is set correctly

## Advanced Features

### Signal Templates

Save commonly used signal conditions:

```python
# Save template
POST /api/signals/templates
{
    "name": "RSI Oversold Buy",
    "condition": "rsi_14 < 30 AND volume_ratio > 1.5",
    "action": "BUY"
}

# Use template
POST /api/signals/from-template
{
    "template_name": "RSI Oversold Buy",
    "instrument": "BANKNIFTY"
}
```

### Alert Notifications

Configure alerts:

```python
POST /api/alerts
{
    "type": "signal_triggered",
    "channels": ["email", "telegram"],
    "conditions": {
        "confidence": "> 80%"
    }
}
```

### Backtesting from UI

Run backtest directly from dashboard:

```python
POST /api/backtest/run
{
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "strategy": "multi_agent",
    "initial_capital": 100000
}
```

Results displayed in Analytics section.

## Best Practices

1. **Monitor System Health**: Check health panel regularly
2. **Review Agent Analysis**: Understand why decisions are made
3. **Track P&L**: Monitor performance metrics
4. **Use Paper Trading First**: Test strategies before going live
5. **Set Stop Losses**: Always have risk management
6. **Check Virtual Time**: Ensure correct time mode active
7. **Review Logs**: Check for errors or warnings
8. **Backup Settings**: Export configuration regularly

## Configuration Files

### dashboard/config.py

```python
# Server settings
HOST = "0.0.0.0"
PORT = 8000

# Database
MONGODB_URI = "mongodb://localhost:27017"
REDIS_HOST = "localhost"
REDIS_PORT = 6379

# Update rates
TICK_UPDATE_MS = 100
POSITION_UPDATE_MS = 1000
AGENT_UPDATE_MS = 15000

# Features
ENABLE_HISTORICAL_REPLAY = True
ENABLE_WEBSOCKET = True
ENABLE_BACKTESTING = True
```

### Environment Variables

```bash
# Trading mode
TRADING_MODE=paper_mock

# Kite credentials
KITE_API_KEY=your_key
KITE_ACCESS_TOKEN=your_token

# Database
MONGODB_URI=mongodb://localhost:27017
REDIS_HOST=localhost
REDIS_PORT=6379

# Features
ENABLE_LIVE_TRADING=false
```

## Screenshots Reference

### Main Dashboard
- Top: Time & Market Status
- Left: Positions & Signals
- Center: Agent Feed & Charts
- Right: System Health & Stats

### Historical Replay View
- Timeline scrubber
- Playback controls
- Virtual time indicator
- Speed selector

### Analytics View
- Equity curve chart
- Trade distribution
- Win/loss breakdown
- Risk metrics

