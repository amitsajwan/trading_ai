# Trading System TODO List

## ✅ Completed Tasks
- [x] Stop historical-replay-service (not needed in LIVE mode)
- [x] Fix orchestrator-service logging crash (empty LOG_FILE)
- [x] Fix trading-bot-nifty import error (missing services.trading_service)
- [x] Fix trading-bot-btc import error (missing services.trading_service)
- [x] Fix backend-btc import path error (dashboard_pro:app)
- [x] Fix news-api syntax error (type annotations)
- [x] Fix market-data-api JSON encoding error (-inf values)
- [x] Start market-data-dashboard service (port 8008)
- [x] Verify all services running (15/15 confirmed running)
- [x] Test market-data-api indicators endpoint (✅ working - 40+ indicators)
- [x] Test WebSocket gateway health (✅ working)
- [x] Enable historical mode with virtual time (28 Jan 2026)
- [x] Access BANKNIFTY data for 28 Jan 2026 (✅ working - OHLC + indicators)

## 🔄 Current Status
- All 15 services are running successfully in HISTORICAL mode
- Virtual time set to 28 Jan 2026 09:15 IST
- Market data dashboard accessible at http://localhost:8008
- BANKNIFTY data available with 40+ technical indicators
- System is stable for historical data analysis

## 📋 Next Steps (Priority Order)
- [x] Start dashboard UI service (port 8888) - ✅ UI now running at http://localhost:8888
- [ ] Verify live data flow in browser
  - Open http://localhost:8888 (UI is now running)
  - Confirm WebSocket LTP updates
  - Test /api/v1/technical/indicators/BANKNIFTY endpoint (✅ working)
  - Check for CORS/WebSocket CSP errors
- [ ] Monitor orchestrator cycles for runtime issues
  - Check logs for TradingDecision attribute errors
- [ ] Re-enable automatic-trading-service
  - Only after full live verification
  - Add safeguards (rate limits, dry-run mode)
- [ ] Add service health checks
  - Implement proper health endpoints
  - Add monitoring dashboard
- [ ] Test complete trading cycle
  - Verify signal generation
  - Confirm decision publishing
  - Test order execution (dry-run first)

## 🔍 Known Issues to Monitor
- TradingDecision attribute errors in orchestrator logs (non-fatal)
- JSON encoding of -inf values in technical indicators
- Dashboard shim may need refinement

## 🛠️ Maintenance Tasks
- [ ] Update requirements.txt if needed
- [ ] Review and optimize Docker resource usage
- [ ] Add proper error handling and retries
- [ ] Implement backup strategies for MongoDB/Redis

## 📊 Service Ports (Reference)
- market-data-api: 8004
- backend-btc: 8001
- news-api: 8005
- redis-ws-gateway: 8889
- dashboard: 3000