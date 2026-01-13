# Real Data vs Mock Data - Clarification

**Important:** Both Real-Time and Historical modes use **REAL Zerodha data**, not mock data!

---

## 📊 Data Sources

### Real-Time (Live) Mode

**All data is REAL from Zerodha:**
- ✅ **LTP/OHLC**: Real-time from Zerodha WebSocket/REST API
- ✅ **Market Depth**: Real-time from Zerodha `kite.quote()` API
- ✅ **Options Chain**: Real-time from Zerodha `kite.quote()` API (bid/ask)
- ✅ **IV/Greeks**: Calculated from real option prices

**Not mock data** - all comes from live Zerodha market data.

---

### Historical Replay Mode

**All data is REAL from Zerodha:**
- ✅ **LTP/OHLC**: Real historical data from Zerodha `kite.historical_data()` API
- ⚠️ **Market Depth**: Synthetic fallback (historical API doesn't provide depth)
- ✅ **Options Chain**: Real data from Zerodha `kite.ltp()` API (last traded price)
- ✅ **IV/Greeks**: Calculated from real option prices

**Not mock data** - historical OHLC and options chain are real Zerodha historical data.

---

## 🔍 Common Misconception

### ZerodhaOptionsChainAdapter - Real Zerodha API

**`ZerodhaOptionsChainAdapter` uses REAL Zerodha API** for options chain data!

**From the code:**
```python
class ZerodhaOptionsChainAdapter(OptionsData):
    """Options chain adapter using Zerodha API.
    
    Uses real Zerodha API (kite.ltp() or kite.quote()) for live data.
    Provides options chain with real market data for both live and historical modes.
    """
```

**How it works:**
- **Live mode:** Uses `kite.quote()` - **REAL Zerodha API** for real-time bid/ask
- **Historical mode:** Uses `kite.ltp()` - **REAL Zerodha API** for last traded price

**Note:** Previously named `MockOptionsChainAdapter` but now correctly renamed to `ZerodhaOptionsChainAdapter` to reflect that it uses real Zerodha API.

---

## 📈 What is Real vs What is Synthetic

### ✅ Real Zerodha Data (Both Modes)

1. **OHLC/Price Data**
   - Real-Time: `kite.quote()`, WebSocket ticks
   - Historical: `kite.historical_data()` API

2. **Options Chain**
   - Real-Time: `kite.quote()` (real-time bid/ask)
   - Historical: `kite.ltp()` (last traded price)

3. **IV/Greeks Calculation**
   - Both modes: Calculated from real option prices using Black-Scholes

4. **Instrument Metadata**
   - Both modes: Real instrument data from `kite.instruments()`

---

### ⚠️ Synthetic/Fallback Data (Historical Mode Only)

1. **Market Depth** (Historical Mode Only)
   - **Why:** Zerodha Historical API doesn't provide order book depth
   - **Fallback:** Synthetic depth generated from latest tick price
   - **Accuracy:** Less accurate (estimated, not real order book)

2. **Options Chain Bid/Ask** (Historical Mode)
   - **Why:** `kite.quote()` requires active market (returns empty after hours)
   - **Fallback:** Uses `kite.ltp()` (last traded price) instead of bid/ask
   - **Accuracy:** Less accurate (shows last price, not current bid/ask)

---

## 🎯 Summary

| Data Type | Real-Time Mode | Historical Mode |
|-----------|----------------|-----------------|
| **OHLC/Price** | ✅ Real (WebSocket/REST) | ✅ Real (Historical API) |
| **Market Depth** | ✅ Real (quote API) | ⚠️ Synthetic (fallback) |
| **Options Chain** | ✅ Real (quote API) | ✅ Real (ltp API) |
| **IV/Greeks** | ✅ Calculated from real prices | ✅ Calculated from real prices |
| **Instrument Data** | ✅ Real (instruments API) | ✅ Real (instruments API) |

---

## 💡 Key Points

1. **Both modes use REAL Zerodha data** for core data (OHLC, prices, options chain)
2. **Only depth in historical mode is synthetic** (because historical API doesn't have it)
3. **`ZerodhaOptionsChainAdapter`** uses real Zerodha API for all data
4. **Historical mode is for backtesting with real historical data**, not mock data
5. **All calculations (IV, Greeks, indicators) use real data** in both modes

---

## 🔧 Code Evidence

### Historical Data is Real

```python
# From historical_tick_replayer.py
historical_data = self.kite.historical_data(
    instrument_token=instrument_token,
    from_date=self.from_date,
    to_date=self.to_date,
    interval=self.interval
)
# This is REAL historical OHLC data from Zerodha, not mock!
```

### Options Chain Uses Real API

```python
# From zerodha_options_chain.py
if self.use_live_quotes:
    # Live mode: REAL Zerodha quote API
    batch_quotes = self.kite.quote(batch)  # REAL API call
else:
    # Historical mode: REAL Zerodha ltp API
    batch_ltp = self.kite.ltp(batch)  # REAL API call
```

---

**Bottom Line:** Both modes give you **real Zerodha market data**, not mock data! The `ZerodhaOptionsChainAdapter` uses real Zerodha API in both modes. 🎯
