#!/usr/bin/env python3
"""Test actual indicator calculations with real data from the system."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "market_data", "src"))

from market_data.technical_indicators_service import TechnicalIndicatorsService
import pandas as pd

def test_indicator_calculation():
    """Test indicator calculation with sample data."""

    # Create sample OHLC data (simulating 1 day of 1-minute bars)
    import numpy as np

    # Generate realistic price data
    np.random.seed(42)
    base_price = 59450.0
    timestamps = pd.date_range('2024-01-12 09:15:00', periods=300, freq='1min')  # 5 hours of data

    # Generate OHLC data with some trend and noise
    price_changes = np.random.normal(0, 5, len(timestamps))  # Small random changes
    trend = np.linspace(0, 20, len(timestamps))  # Slight upward trend
    prices = base_price + trend + np.cumsum(price_changes)

    # Create OHLC bars
    ohlc_data = []
    for i, ts in enumerate(timestamps):
        price = prices[i]
        high = price + abs(np.random.normal(0, 2))
        low = price - abs(np.random.normal(0, 2))
        open_price = prices[i-1] if i > 0 else price
        close = price

        ohlc_data.append({
            'start_at': ts.isoformat(),
            'open': open_price,
            'high': max(open_price, high),
            'low': min(open_price, low),
            'close': close,
            'volume': np.random.randint(100, 1000)
        })

    print(f"Generated {len(ohlc_data)} OHLC bars")
    print(f"First bar: {ohlc_data[0]}")
    print(f"Last bar: {ohlc_data[-1]}")

    # Initialize service
    service = TechnicalIndicatorsService(window_size=200)

    # Load OHLC data
    instrument = "BANKNIFTY"
    service.initialize_with_ohlc_data(instrument, ohlc_data)

    # Calculate indicators
    indicators = service.get_indicators_dict(instrument)

    print("\n=== INDICATOR RESULTS ===")
    print(f"Total indicators: {len(indicators)}")

    # Check key indicators
    key_indicators = ['rsi_14', 'macd_value', 'adx_14', 'atr_14', 'atr_20', 'bollinger_upper', 'bollinger_middle', 'bollinger_lower']

    for indicator in key_indicators:
        value = indicators.get(indicator)
        print(f"  {indicator}: {value}")

    # Check ATR specifically
    atr_14 = indicators.get('atr_14')
    atr_20 = indicators.get('atr_20')
    print(f"\nATR Analysis:")
    print(f"  atr_14: {atr_14}")
    print(f"  atr_20: {atr_20}")
    print(f"  atr_14 type: {type(atr_14)}")
    print(f"  atr_20 type: {type(atr_20)}")

    # Check if ATR values are reasonable
    if atr_14 and atr_20:
        print(f"  ATR ratio (20/14): {atr_20/atr_14:.2f} (should be > 1)")
        print(f"  ATR as % of price: {(atr_14/base_price)*100:.2f}%")

    return indicators

if __name__ == "__main__":
    test_indicator_calculation()