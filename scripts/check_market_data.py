"""Check if market data is available."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.market_memory import MarketMemory
from config.settings import settings

mm = MarketMemory()
key = settings.instrument_symbol.replace('-', '').replace(' ', '').upper()

price = mm.get_current_price(key)
ohlc_1min = mm.get_recent_ohlc(key, '1min', 5)
ohlc_5min = mm.get_recent_ohlc(key, '5min', 5)

print(f"Instrument: {settings.instrument_symbol}")
print(f"Current Price: {price}")
print(f"OHLC 1min candles: {len(ohlc_1min) if ohlc_1min else 0}")
print(f"OHLC 5min candles: {len(ohlc_5min) if ohlc_5min else 0}")

if ohlc_1min:
    print(f"\nSample 1min OHLC: {ohlc_1min[0]}")
else:
    print("\n[WARNING] No OHLC data available!")
    print("Agents need market data to produce meaningful analysis.")

