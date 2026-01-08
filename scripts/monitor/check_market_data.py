"""ARCHIVED: The original check script was archived on 2026-01-03; the compressed backup was permanently deleted on 2026-01-03 per repository cleanup."""

print("This check script's original content was archived and the compressed backup was permanently deleted on 2026-01-03. Contact maintainers to request restoration.")

from data.market_memory import MarketMemory
from core_kernel.config.settings import settings

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


