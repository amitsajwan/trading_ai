"""Test data feed status check."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitoring.system_health import SystemHealthChecker

hc = SystemHealthChecker()
health = hc.check_all()
feed = health['components']['data_feed']

print("=" * 60)
print("Data Feed Status Check")
print("=" * 60)
print(f"Status: {feed['status']}")
print(f"Source: {feed.get('source', 'N/A')}")
print(f"Zerodha Configured: {feed.get('zerodha_configured', False)}")
print(f"Receiving Data: {feed.get('receiving_data', False)}")
print(f"Market Open: {feed.get('market_open', False)}")
print(f"Current Price: {feed.get('current_price', 'N/A')}")
print(f"OHLC Count: {feed.get('ohlc_count', 0)}")
print()
print("Message:")
print(f"  {feed.get('message', 'N/A')}")
print("=" * 60)

