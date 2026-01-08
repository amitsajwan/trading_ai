# UI Verification Checklist - Market Data APIs Dashboard

## ✅ What to Verify on the Dashboard

### 1. Open Dashboard
- **URL**: http://localhost:8888/
- **Tab**: Click on **"📈 Market Data APIs"** tab in the navigation

---

### 2. Price Data API Section
**What to Check:**
- ✅ **Price**: Should show **~₹60,170** (NOT ₹45,250)
  - If showing `None` or incorrect price, check health endpoint
- ✅ **Volume**: Should show a number (e.g., 624)
- ✅ **Status**: Should show **"Live"** (green) or **"After Hours (Stale)"** (yellow)
- ✅ **Timestamp**: Should show a recent timestamp
- ✅ **Raw JSON**: Click to expand - verify structure

**Expected Response:**
```json
{
  "instrument": "BANKNIFTY",
  "price": 60170.0,
  "volume": 624,
  "timestamp": "2026-01-15T01:09:54+05:30",
  "is_stale": false
}
```

---

### 3. Options Chain API Section
**What to Check:**
- ✅ **Strikes Available**: Should show a count (e.g., 138)
- ✅ **Expiry**: Should show an expiry date (e.g., "2026-01-15")
- ✅ **Options Table**: Should display strikes with CE/PE prices
  - CE Price, CE OI, PE Price, PE OI columns
  - Data should not be all "--" (should have prices)

**Expected Response:**
- Table with multiple rows of strikes
- Each row has Strike, CE Price, CE OI, PE Price, PE OI
- Prices should be real numbers (not null)

---

### 4. Technical Indicators API Section
**What to Check:**
- ✅ **RSI (14)**: Should show a number between 0-100 (e.g., 52.34)
- ✅ **MACD**: Should show a number (e.g., -123.45)
- ✅ **SMA (20)**: Should show a number (e.g., 59,850.50)
- ✅ **EMA (20)**: Should show a number
- ✅ **Bollinger Bands**: Upper and Lower should show numbers
- ✅ **ATR (14)**: Should show a number
- ✅ **CCI (20)**: Should show a number

**Expected Response:**
- All indicators should have values (not all "--")
- Values should be reasonable (RSI 0-100, prices ~60k range)

---

### 5. System Health API Section
**What to Check:**
- ✅ **Status**: Should show **"healthy"** or **"degraded"**
- ✅ **Redis**: Should show **"healthy"**
- ✅ **Data Availability**: Should show one of:
  - `fresh_data_for_BANKNIFTY` ✅ (good)
  - `missing_price_data_for_BANKNIFTY` ⚠️ (needs data loading)
  - `stale_data_for_BANKNIFTY_age_XXXs` ⚠️ (data too old)

**Expected Response:**
```json
{
  "status": "healthy",
  "dependencies": {
    "redis": "healthy",
    "store": "initialized",
    "data_availability": "fresh_data_for_BANKNIFTY"
  }
}
```

---

### 6. Market Depth API Section
**What to Check:**
- ✅ **Raw JSON**: Should show buy/sell depth data
- ✅ **Structure**: Should have `buy` and `sell` arrays

---

### 7. OHLC Data API Section
**What to Check:**
- ✅ **Raw JSON**: Should show OHLC candles
- ✅ **Structure**: Should have timestamp, open, high, low, close, volume

---

### 8. Auto-Refresh
**What to Check:**
- ✅ **Auto-refresh**: Data should update every 30 seconds automatically
- ✅ **Manual refresh**: Click "🔄 Refresh" button - should update immediately
- ✅ **Last updated**: Footer should show "Last updated: [timestamp]"

---

## ⚠️ Common Issues & Solutions

### Issue: Price showing `None` or incorrect value
**Solution:**
1. Check health endpoint: http://127.0.0.1:8006/health
2. If `data_availability` shows `missing_price_data_for_BANKNIFTY`:
   - Historical data may not be loaded yet
   - Wait for `start_market_data_server.py` to finish loading data
   - Check server logs for data loading status

### Issue: All indicators showing "--"
**Solution:**
1. Technical indicators need OHLC data to calculate
2. Wait for historical data to load and OHLC candles to be created
3. Check if `technical_indicators_service` is processing ticks

### Issue: Options Chain showing no strikes
**Solution:**
1. Check if Zerodha credentials are loaded correctly
2. Check if Kite API is accessible
3. Options chain uses `MockOptionsChainAdapter` which fetches from Kite

### Issue: Health showing "degraded"
**Solution:**
1. Check `data_availability` field in health response
2. If `missing_price_data_for_BANKNIFTY`: Data not loaded yet
3. If `stale_data_for_BANKNIFTY`: Data is older than 2 minutes (expected in after-hours)

---

## 🎯 Success Criteria

**All systems working correctly when:**
- ✅ Price shows ~₹60,170 (correct Zerodha historical data)
- ✅ Options chain shows strikes with real prices
- ✅ Technical indicators show calculated values (not all "--")
- ✅ Health shows `healthy` or `fresh_data_for_BANKNIFTY`
- ✅ Auto-refresh works every 30 seconds
- ✅ No errors in browser console (F12)

---

## 📍 Direct API Test URLs

For quick verification, you can also test APIs directly:

- **Health**: http://127.0.0.1:8006/health
- **Price**: http://127.0.0.1:8006/api/v1/market/price/BANKNIFTY
- **Options**: http://127.0.0.1:8006/api/v1/options/chain/BANKNIFTY
- **Indicators**: http://127.0.0.1:8006/api/v1/technical/indicators/BANKNIFTY

