# Quick Start: Autonomous Trading System

## Prerequisites
- Docker containers running (BTC, BANKNIFTY, NIFTY)
- MongoDB running on port 27018
- Redis running on port 6380
- Valid Zerodha access_token in credentials.json (for BANKNIFTY/NIFTY)

## Start Trading (BANKNIFTY Example)

### 1. Verify System Health
```bash
curl http://localhost:8002/api/system-health | jq
```

**Expected output**:
```json
{
  "overall_status": "healthy",
  "components": {
    "data_freshness": {"status": "healthy", "age_seconds": 15.2},
    "recent_trades": {"status": "healthy", "total_count": 5},
    "circuit_breakers": {"status": "healthy", "daily_pnl": 250.50}
  }
}
```

### 2. Check Decision Context
```bash
curl http://localhost:8002/api/decision-context | jq
```

**Expected output**:
```json
{
  "timestamp": "2025-01-05T...",
  "market": {
    "price": 50123.45,
    "vwap": 50100.00
  },
  "order_flow": {
    "available": true,
    "imbalance": {"imbalance_status": "BUY_PRESSURE"}
  },
  "options_chain": {
    "available": true,
    "futures_price": 50150.00
  },
  "recent_pnl": 1250.50,
  "win_rate": 65.5
}
```

### 3. Monitor Trading Loop
```bash
# View live logs (watch for agent decisions)
docker logs -f zerodha-trading-bot-banknifty-1

# Or tail the log file
tail -f logs/trading_service.log
```

**Look for**:
```
🎯 [TRADING_LOOP] Executing Agent Analysis Pipeline...
✅ [LOOP #1] Analysis completed in 45.2s
TRADING DECISION: BUY
Signal: BUY
Position Size: 25
Entry Price: 50123.45
```

### 4. Monitor Strategies
```bash
# Check for detected strategies in logs
docker logs zerodha-trading-bot-banknifty-1 | grep "Detected.*strategies"
```

**Expected**:
```
Detected 1 option strategies
Strategy: iron_condor, strikes: [50000, 50100, 50200, 50300], credit: 130.0
```

### 5. Check Recent Trades (MongoDB)
```bash
# Connect to MongoDB
docker exec -it zerodha-mongodb-1 mongosh --port 27017

# In mongosh:
use trading_db
db.trades_executed.find().sort({entry_timestamp: -1}).limit(5).pretty()
```

## Monitoring Dashboard

### Open Dashboard
```
http://localhost:8002
```

### Key Metrics to Watch
1. **Current Price**: Real-time price updates
2. **Order Flow Card**: Shows buy/sell imbalance, spread, depth
3. **Options Chain Card**: Shows CE/PE premiums and OI
4. **Recent Trades**: Last 5 trades with PnL
5. **Win Rate**: Percentage of profitable trades

## Autonomous Loop Status

### How Often?
- **Every 15 minutes** (default: `trading_loop_interval_seconds = 900`)

### What Happens?
1. ✅ Fetch market data (price, OHLC, volume)
2. ✅ Fetch order-flow (imbalance, spread, depth)
3. ✅ Fetch options chain (CE/PE LTP/OI) - NFO only
4. ✅ Run agent analysis (technical, fundamental, sentiment, macro)
5. ✅ Detect strategies (iron condor, spreads)
6. ✅ Portfolio manager decides (BUY/SELL/HOLD)
7. ✅ Pre-trade risk check (position size, price, circuit breakers)
8. ✅ Execute trade (if approved)
9. ✅ Health monitor checks (freshness, trades, limits)

## Troubleshooting

### No Decision Context?
```bash
# Check if dashboard is running
curl http://localhost:8002/api/health

# Check if data feed is running
docker logs zerodha-trading-bot-banknifty-1 | grep "WebSocket connected"
```

### Stale Data?
```bash
# Check freshness
curl http://localhost:8002/api/system-health | jq '.components.data_freshness'

# Restart data feed
docker restart zerodha-trading-bot-banknifty-1
```

### No Options Chain?
**Normal for BTC** (crypto has no options on Binance)
**For BANKNIFTY/NIFTY**: Ensure:
1. Valid Zerodha token
2. NFO exchange configured
3. Market hours (9:15 AM - 3:30 PM IST)

### Circuit Breaker Triggered?
```bash
# Check status
curl http://localhost:8002/api/system-health | jq '.components.circuit_breakers'

# Reset (if appropriate):
# 1. Review trades to understand loss
# 2. Adjust strategy/risk parameters
# 3. Restart trading service
docker restart zerodha-trading-bot-banknifty-1
```

## Configuration

### Change Loop Interval
Edit `config/settings.py`:
```python
trading_loop_interval_seconds = 300  # 5 minutes instead of 15
```

### Change Circuit Breaker Threshold
Edit `config/settings.py`:
```python
max_daily_loss = -10000  # ₹10,000 instead of ₹5,000
```

### Enable Paper Trading
Edit `config/settings.py`:
```python
paper_trading = True  # Simulates trades without real orders
```

## API Endpoints

### Decision Context
```bash
GET http://localhost:8002/api/decision-context
```
Comprehensive context for agents (market + order-flow + options + PnL)

### System Health
```bash
GET http://localhost:8002/api/system-health
```
Health checks (freshness, trades, circuit breakers)

### Order Flow
```bash
GET http://localhost:8002/api/order-flow
```
Buy/sell imbalance, spread, depth analysis

### Options Chain
```bash
GET http://localhost:8002/api/options-chain
```
CE/PE LTP/OI for NFO instruments

### Market Data
```bash
GET http://localhost:8002/api/market-data
```
Price, volume, VWAP, 24h high/low

## Performance Benchmarks

### Target Metrics
- **Data freshness**: < 30 seconds (alert if > 90s)
- **Agent analysis**: < 60 seconds per cycle
- **Win rate**: > 50% (target: 60-70%)
- **Daily PnL**: Positive (target: > ₹500/day)

### Current Status
```bash
# Check metrics
curl http://localhost:8002/metrics/trading | jq
curl http://localhost:8002/metrics/risk | jq
```

## Next Actions

1. **Monitor for 1 hour**: Watch logs, check decisions, verify trades
2. **Review strategies**: Check if iron condors are detected correctly
3. **Validate risk checks**: Ensure pre-trade validation works
4. **Test circuit breakers**: Simulate loss scenario (if needed)
5. **Optimize loop interval**: Adjust based on strategy (5min vs 15min)

## Support

**Logs**: `logs/trading_service.log`, `logs/dashboard.log`
**Documentation**: `docs/AUTONOMOUS_TRADING_IMPLEMENTATION.md`
**Health Check**: `http://localhost:8002/api/system-health`

**🚀 System is READY - Autonomous trading active!**
