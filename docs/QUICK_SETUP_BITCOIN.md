# Quick Setup: Bitcoin Trading

## Step-by-Step Guide

### 1. Run Bitcoin Configuration Script

```bash
python scripts/setup_bitcoin_config.py
```

This automatically adds/updates these variables in your `.env`:

```bash
# Bitcoin Configuration
INSTRUMENT_SYMBOL=BTC-USD
INSTRUMENT_NAME=Bitcoin
INSTRUMENT_EXCHANGE=CRYPTO
DATA_SOURCE=CRYPTO
NEWS_QUERY=Bitcoin OR BTC OR cryptocurrency
NEWS_KEYWORDS=Bitcoin,BTC,cryptocurrency,crypto
MACRO_DATA_ENABLED=false
MARKET_24_7=true
MARKET_OPEN_TIME=00:00:00
MARKET_CLOSE_TIME=23:59:59
```

### 2. Verify Your `.env` File

Open `.env` and check these are set:

**Required for Bitcoin:**
- ✅ `DATA_SOURCE=CRYPTO` (enables Binance WebSocket)
- ✅ `INSTRUMENT_SYMBOL=BTC-USD` (or BTCUSD, BTC)
- ✅ `INSTRUMENT_NAME=Bitcoin`
- ✅ `MARKET_24_7=true` (crypto trades 24/7)

**Optional but Recommended:**
- `NEWS_API_KEY=your_key` (for news sentiment)
- `LLM_PROVIDER=ollama` (or groq, gemini, etc.)
- `OLLAMA_BASE_URL=http://localhost:11434` (if using local LLM)

### 3. Install Dependencies

```bash
pip install websockets
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

### 4. Start the System

```bash
python scripts/start_all.py
```

Or manually:
```bash
# Terminal 1: Dashboard
python -m monitoring.dashboard

# Terminal 2: Trading Service (auto-detects crypto feed)
python -m services.trading_service
```

### 5. Verify It's Working

**Check Logs:**
- Look for: `✅ Crypto data feed (Binance WebSocket) started`
- Look for: `✅ Connected to Binance WebSocket for BTCUSDT`
- Look for: `Processed tick: BTCUSDT @ [price]`

**Check Dashboard:**
- Open: http://localhost:8888
- Should show Bitcoin price updating in real-time

**Check Redis:**
```python
from data.market_memory import MarketMemory
mm = MarketMemory()
price = mm.get_current_price("BTCUSD")
print(f"BTC Price: ${price}")
```

## Complete `.env` Example for Bitcoin

```bash
# ============================================
# BITCOIN CONFIGURATION
# ============================================
INSTRUMENT_SYMBOL=BTC-USD
INSTRUMENT_NAME=Bitcoin
INSTRUMENT_EXCHANGE=CRYPTO
DATA_SOURCE=CRYPTO

# News Configuration
NEWS_QUERY=Bitcoin OR BTC OR cryptocurrency
NEWS_KEYWORDS=Bitcoin,BTC,cryptocurrency,crypto
NEWS_API_KEY=your_news_api_key_here

# Market Hours (24/7 for crypto)
MARKET_24_7=true
MARKET_OPEN_TIME=00:00:00
MARKET_CLOSE_TIME=23:59:59

# Macro Data (disabled for crypto)
MACRO_DATA_ENABLED=false

# ============================================
# LLM CONFIGURATION
# ============================================
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
# OR use cloud providers:
# GROQ_API_KEY=your_groq_key
# GOOGLE_API_KEY=your_gemini_key
# OPENROUTER_API_KEY=your_openrouter_key

# ============================================
# DATABASE CONFIGURATION
# ============================================
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB_NAME=zerodha_trading
REDIS_HOST=localhost
REDIS_PORT=6379

# ============================================
# TRADING CONFIGURATION
# ============================================
PAPER_TRADING_MODE=true
MAX_POSITION_SIZE_PCT=5.0
DEFAULT_STOP_LOSS_PCT=1.5
DEFAULT_TAKE_PROFIT_PCT=3.0
```

## Troubleshooting

### No Data Received

1. **Check DATA_SOURCE:**
   ```bash
   # Should be CRYPTO, not ZERODHA
   DATA_SOURCE=CRYPTO
   ```

2. **Check Symbol:**
   ```bash
   # Valid formats: BTC-USD, BTCUSD, BTC
   INSTRUMENT_SYMBOL=BTC-USD
   ```

3. **Check Internet Connection:**
   - Binance WebSocket requires internet
   - Check: https://www.binance.com/en/support/announcement

4. **Check Logs:**
   - Look for WebSocket connection errors
   - Look for "Connected to Binance WebSocket"

### Wrong Feed Used

If you see "Zerodha WebSocket" instead of "Binance WebSocket":
- Verify `DATA_SOURCE=CRYPTO` in `.env`
- Restart the system
- Check logs for data source detection

### Price Not Updating

1. **Check Redis:**
   ```bash
   redis-cli
   KEYS price:*
   GET price:BTCUSD:latest
   ```

2. **Check MongoDB:**
   ```python
   from mongodb_schema import get_mongo_client, get_collection
   client = get_mongo_client()
   db = client["zerodha_trading"]
   ohlc = get_collection(db, "ohlc_history")
   latest = ohlc.find_one({"instrument": "BTC-USD"}, sort=[("timestamp", -1)])
   print(latest)
   ```

## Switching Back to Bank Nifty

```bash
python scripts/setup_banknifty_config.py
```

This will change:
- `DATA_SOURCE=ZERODHA`
- `INSTRUMENT_SYMBOL=NIFTY BANK`
- `MARKET_24_7=false`
- `MACRO_DATA_ENABLED=true`

## Next Steps

1. ✅ Configure `.env` for Bitcoin
2. ✅ Install dependencies (`pip install websockets`)
3. ✅ Start system (`python scripts/start_all.py`)
4. ✅ Verify data feed is working
5. ✅ Monitor dashboard for real-time prices
6. ✅ Let agents analyze Bitcoin market

**That's it! No code changes needed - just `.env` configuration!**

