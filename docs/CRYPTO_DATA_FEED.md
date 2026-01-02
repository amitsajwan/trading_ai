# Crypto Data Feed Setup

## Overview

The system supports real-time Bitcoin/crypto data via **free Binance WebSocket API**. No API key required for public streams!

## Supported Exchanges

### Binance (Default - Free)
- **WebSocket URL**: `wss://stream.binance.com:9443/ws/{symbol}@ticker`
- **No API Key Required**: Public streams are free
- **Rate Limits**: Very high (thousands of messages per second)
- **Reliability**: Excellent (99.9% uptime)
- **Supported Symbols**: BTCUSDT, ETHUSDT, and 100+ others

### Other Options (Future)
- **Coinbase**: `wss://ws-feed.exchange.coinbase.com`
- **Bybit**: `wss://stream.bybit.com/v5/public/spot`
- **Kraken**: `wss://ws.kraken.com`

## Configuration

### For Bitcoin

1. **Set instrument configuration**:
   ```bash
   python scripts/setup_bitcoin_config.py
   ```

2. **Verify `.env` has**:
   ```bash
   INSTRUMENT_SYMBOL=BTC-USD
   INSTRUMENT_NAME=Bitcoin
   DATA_SOURCE=CRYPTO
   ```

3. **Symbol Mapping**:
   - `BTC-USD` → `BTCUSDT` (Binance)
   - `ETH-USD` → `ETHUSDT` (Binance)
   - Auto-converted automatically

## How It Works

1. **Connection**: Connects to Binance WebSocket public stream
2. **Subscription**: Subscribes to ticker stream for configured symbol
3. **Data Processing**:
   - Receives real-time price updates
   - Aggregates into OHLC candles (1min, 5min, 15min, hourly)
   - Stores in Redis (hot data) and MongoDB (persistent)
4. **Reconnection**: Automatically reconnects on failure

## Data Format

### Ticker Stream (from Binance)
```json
{
  "e": "24hrTicker",
  "s": "BTCUSDT",
  "c": "45000.00",      // Last price
  "v": "1234.56",       // 24h volume
  "h": "46000.00",      // 24h high
  "l": "44000.00",      // 24h low
  "o": "44500.00",      // 24h open
  "P": "1.12",          // Price change %
  "b": "44999.50",      // Best bid
  "a": "45000.50",      // Best ask
  "B": "0.5",           // Best bid qty
  "A": "0.3"            // Best ask qty
}
```

### Stored Tick Data
```json
{
  "instrument_token": "BTCUSDT",
  "last_price": 45000.00,
  "price": 45000.00,
  "volume": 1234.56,
  "timestamp": "2024-01-01T12:00:00",
  "bid_price": 44999.50,
  "ask_price": 45000.50,
  "bid_quantity": 0.5,
  "ask_quantity": 0.3,
  "high_24h": 46000.00,
  "low_24h": 44000.00,
  "change_24h": 1.12
}
```

## Advantages

✅ **Free**: No API key or subscription needed  
✅ **Real-time**: Sub-second latency  
✅ **Reliable**: Binance infrastructure (99.9% uptime)  
✅ **High Rate Limits**: Thousands of messages/second  
✅ **Multiple Symbols**: Supports 100+ crypto pairs  
✅ **No Authentication**: Public streams don't require API keys  

## Testing

### Manual Test
```python
import asyncio
from data.crypto_data_feed import CryptoDataFeed
from data.market_memory import MarketMemory

async def test():
    market_memory = MarketMemory()
    feed = CryptoDataFeed(market_memory)
    await feed.start()

asyncio.run(test())
```

### Check Data Reception
```python
from data.market_memory import MarketMemory

market_memory = MarketMemory()
price = market_memory.get_current_price("BTCUSD")  # or BTC-USD
print(f"Current BTC price: ${price}")
```

## Troubleshooting

### Connection Issues
- **Check internet connection**
- **Verify symbol is correct** (BTC-USD, ETH-USD, etc.)
- **Check Binance status**: https://www.binance.com/en/support/announcement

### No Data Received
- **Verify `.env` has `DATA_SOURCE=CRYPTO`**
- **Check logs for connection errors**
- **Verify symbol mapping** (BTC-USD → BTCUSDT)

### Rate Limits
- **Public streams**: No rate limits for ticker streams
- **If issues occur**: Binance may throttle, wait and retry

## Future Enhancements

- [ ] Support for multiple symbols simultaneously
- [ ] Order book depth (level 2 data)
- [ ] Trade history stream
- [ ] Kline/candle stream (more efficient than ticker)
- [ ] Coinbase integration
- [ ] Bybit integration
- [ ] Aggregated feeds (multiple exchanges)

## References

- **Binance WebSocket Docs**: https://binance-docs.github.io/apidocs/spot/en/#websocket-market-streams
- **Public Streams**: https://binance-docs.github.io/apidocs/spot/en/#websocket-market-streams
- **Symbol List**: https://api.binance.com/api/v3/exchangeInfo

