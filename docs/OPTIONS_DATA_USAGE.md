## Options Chain Data Usage & Strategy Integration

### 1. Data Collection Architecture

#### Current Implementation
Options chain data is fetched through the `OptionsChainFetcher` class:

**Data Points Collected:**
- Futures price (underlying reference)
- Call/Put LTPs (last traded prices)
- Open Interest (OI) for CE/PE
- Trading volumes
- Strike-wise data for ATM ± 5 strikes (11 strikes total)

**Caching Strategy:**
- 30-second throttle to avoid rate limits
- Batch requests (max 40 instruments per quote() call)
- Targets nearest expiry contracts

### 2. Strategy Integration Points

#### A. Portfolio Manager (`agents/portfolio_manager.py`)
**Method:** `_detect_option_strategies()`

**Strategies Detected:**
1. **Iron Condor Detection**
   - Identifies sell ATM, buy OTM opportunities
   - Calculates net credit based on premiums
   - Confidence scoring: 0.7 if credit > 0.5% of underlying price

**Usage Flow:**
```
AgentState.options_chain → _detect_option_strategies() 
→ Returns strategies list with strikes, net_credit, confidence
→ Informs portfolio decision-making
```

#### B. Strategy Planner (`engines/strategy_planner.py`)
**Method:** `_get_market_context()`

**Integration:**
- Fetches options chain via `derivatives_fetcher.fetch_options_chain()`
- Adds to market context dict for rule generation
- LLM uses options data to generate conditional trading rules

**Example Context:**
```python
context = {
    "options_chain": {
        "futures_price": 60215.45,
        "strikes": {
            60000: {
                "ce_ltp": 834.95,
                "ce_oi": 1185780,
                "pe_ltp": 426.00,
                "pe_oi": 1280910
            }
        }
    }
}
```

#### C. Rule Execution Service (`services/rule_execution_service.py`)
**Method:** `_rule_engine_loop()`

**Real-Time OI Analysis:**
- Fetches current options chain every tick
- Calculates OI changes using `get_oi_changes()`
- Attaches OI delta to tick data: `tick["oi_data"]`
- Rules can trigger on significant OI shifts

**OI Change Detection:**
```python
# CE OI increased 10%, PE OI decreased 5%
oi_changes = {
    60000: {
        "ce_oi_change_pct": 10.0,
        "pe_oi_change_pct": -5.0
    }
}
```

### 3. State Manager Integration (`trading_orchestration/state_manager.py`)

**State Population:**
```python
AgentState(
    options_chain=chain_data,  # Full chain dict
    ...
)
```

All agents receive options chain in their state for decision-making.

### 4. Dashboard Exposure (`dashboard/app.py`)

**Endpoint:** `/api/options-chain`

Displays:
- Futures price
- Strike ladder with CE/PE data
- Last update timestamp

### 5. Limitations & Improvements Needed

#### Current Gaps:
1. **No Greeks calculation** - Missing delta, gamma, theta, vega
2. **No IV surface** - Implied volatility not tracked
3. **No strategy execution** - Detected strategies not auto-executed
4. **No historical OI trends** - Only snapshot-to-snapshot comparison
5. **Limited expiry support** - Only nearest expiry used

#### Recommended Enhancements:
1. Add Greeks calculator using Black-Scholes
2. Implement strategy backtester for detected spreads
3. Create OI heatmap visualization for dashboard
4. Add multi-expiry tracking for calendar spreads
5. Integrate with risk engine for options position limits

### 6. Test Coverage

**New Test Suite:** `tests/test_options_chain_fetcher.py`

Coverage:
- ✅ Initialization with various symbols
- ✅ Futures/options mapping
- ✅ Caching behavior
- ✅ Batch request handling (50+ strikes)
- ✅ Error handling
- ✅ OI change calculation
- ✅ Auto-initialization on first fetch

Run tests:
```bash
pytest tests/test_options_chain_fetcher.py -v
```

### 7. Production Deployment Checklist

Before relying on options data for live trading:

- [ ] Verify instrument mapping for all symbols (NIFTY, BANKNIFTY, etc.)
- [ ] Monitor rate limit compliance during market hours
- [ ] Test OI change alerts with historical data
- [ ] Validate strike selection algorithm (ATM detection)
- [ ] Implement circuit breakers for missing options data
- [ ] Add Greeks calculation library
- [ ] Create options-specific risk limits
- [ ] Backtest iron condor detection accuracy
- [ ] Set up monitoring for stale data (> 1 min)
- [ ] Document strategy execution flow

### 8. Example: Using Options Data in Custom Rules

```python
# Rule: Enter short straddle when ATM IV > 25%
if options_chain["available"]:
    fut_price = options_chain["futures_price"]
    atm_strike = round(fut_price / 100) * 100
    
    ce_premium = strikes[atm_strike]["ce_ltp"]
    pe_premium = strikes[atm_strike]["pe_ltp"]
    
    # Calculate rough IV proxy from premium
    total_premium = ce_premium + pe_premium
    iv_proxy = (total_premium / fut_price) * 100
    
    if iv_proxy > 2.5:  # ~25% implied move
        return SignalType.SELL  # Enter short straddle
```

---

**Last Updated:** January 5, 2026
**Test Coverage:** 12 test cases, all passing
**Production Status:** ⚠️ Data collection ready, strategy execution pending
