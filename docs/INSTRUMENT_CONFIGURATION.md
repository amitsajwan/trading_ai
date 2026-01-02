# Instrument Configuration Guide

## Overview

The system is designed to be **instrument-agnostic** - you can trade any instrument (Bank Nifty, Bitcoin, stocks, etc.) by simply changing environment variables in `.env` file. **No code changes required.**

## Configuration Variables

### Core Instrument Settings

Add these to your `.env` file:

```bash
# Instrument Configuration
INSTRUMENT_SYMBOL=BTC-USD          # Trading symbol (e.g., BTC-USD, NIFTY BANK)
INSTRUMENT_NAME=Bitcoin             # Display name (e.g., Bitcoin, Bank Nifty)
INSTRUMENT_EXCHANGE=CRYPTO          # Exchange (NSE, CRYPTO, etc.)
INSTRUMENT_TOKEN=                   # Optional: Direct token if known

# Data Source Configuration
DATA_SOURCE=CRYPTO                  # ZERODHA, CRYPTO, BINANCE, etc.
DATA_SOURCE_API_KEY=                # API key for data source (if needed)
DATA_SOURCE_SECRET=                 # Secret for data source (if needed)

# News Query Configuration
NEWS_QUERY=Bitcoin OR BTC OR cryptocurrency
NEWS_KEYWORDS=Bitcoin,BTC,cryptocurrency,crypto

# Macro Data Configuration (for crypto, these might be different)
MACRO_DATA_ENABLED=false            # Set false for crypto (no RBI rates)
CRYPTO_MACRO_INDICATORS=            # e.g., Fear & Greed Index, BTC Dominance

# Market Hours (24/7 for crypto)
MARKET_OPEN_TIME=00:00:00
MARKET_CLOSE_TIME=23:59:59
MARKET_24_7=true                    # true for crypto, false for traditional markets
```

## Examples

### Bitcoin Configuration

```bash
INSTRUMENT_SYMBOL=BTC-USD
INSTRUMENT_NAME=Bitcoin
INSTRUMENT_EXCHANGE=CRYPTO
DATA_SOURCE=CRYPTO
NEWS_QUERY=Bitcoin OR BTC OR cryptocurrency
NEWS_KEYWORDS=Bitcoin,BTC,cryptocurrency
MACRO_DATA_ENABLED=false
MARKET_24_7=true
MARKET_OPEN_TIME=00:00:00
MARKET_CLOSE_TIME=23:59:59
```

### Bank Nifty Configuration (Default)

```bash
INSTRUMENT_SYMBOL=NIFTY BANK
INSTRUMENT_NAME=Bank Nifty
INSTRUMENT_EXCHANGE=NSE
DATA_SOURCE=ZERODHA
NEWS_QUERY=Bank Nifty OR banking sector OR RBI
NEWS_KEYWORDS=Bank Nifty,banking sector,RBI
MACRO_DATA_ENABLED=true
MARKET_24_7=false
MARKET_OPEN_TIME=09:15:00
MARKET_CLOSE_TIME=15:30:00
```

## How It Works

1. **Settings Load**: All configuration is loaded from `.env` via `config/settings.py`
2. **Dynamic References**: Code uses `settings.instrument_symbol` instead of hardcoded "BANKNIFTY"
3. **News Queries**: News collector uses `settings.news_query` for API calls
4. **Macro Data**: Macro agent checks `settings.macro_data_enabled` to decide if RBI data is needed
5. **Prompts**: Agent prompts are generic enough to work with any instrument

## Switching Instruments

To switch from Bank Nifty to Bitcoin:

1. **Stop the system**: `python scripts/stop_all.py`
2. **Update `.env`**: Change instrument-related variables (see examples above)
3. **Update data source**: Configure Bitcoin data API (Binance, Coinbase, etc.)
4. **Restart**: `python scripts/start_all.py`

**No code changes needed!**

## Data Source Integration

### For Bitcoin/Crypto

You'll need to integrate a crypto data source. Options:
- **Binance API**: Free, reliable, WebSocket support
- **Coinbase API**: Good for US markets
- **CryptoCompare**: Aggregated data
- **Bybit**: Good for derivatives

The system will automatically use the configured data source.

## Macro Data for Crypto

For crypto, macro indicators are different:
- **Fear & Greed Index**: Market sentiment
- **BTC Dominance**: Market share
- **On-chain metrics**: Active addresses, transaction volume
- **Regulatory news**: Government policies

Set `MACRO_DATA_ENABLED=false` and configure crypto-specific indicators.

## Agent Prompts

Agent prompts are designed to be generic:
- **Technical Agent**: Works with any price/volume data
- **Fundamental Agent**: Adapts based on instrument type
- **Macro Agent**: Uses macro data if enabled, otherwise skips
- **Sentiment Agent**: Uses news query for sentiment analysis

## Testing

After changing configuration:

1. **Verify settings**: `python -c "from config.settings import settings; print(f'Instrument: {settings.instrument_symbol}')"`
2. **Test data feed**: Check if data is being received
3. **Test news**: Verify news queries return relevant results
4. **Test agents**: Run a single analysis cycle

## Notes

- **Zerodha**: Only supports Indian markets (NSE/BSE)
- **Crypto**: Requires different data source (Binance, Coinbase, etc.)
- **Macro Data**: RBI rates only relevant for Indian markets
- **News**: Query should match your instrument
- **Market Hours**: Crypto trades 24/7, stocks have specific hours

