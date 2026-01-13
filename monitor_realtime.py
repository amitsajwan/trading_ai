#!/usr/bin/env python3
"""
Real-time monitoring of the trading system data feed.
"""

import requests
import time
from datetime import datetime

def monitor_realtime():
    """Monitor real-time market data feed."""
    print('🔄 REAL-TIME MARKET DATA MONITORING')
    print('=' * 50)
    print('Monitoring BANKNIFTY price feed for 20 seconds...')
    print()

    start_time = time.time()
    last_price = None
    updates = 0

    while time.time() - start_time < 20:
        try:
            response = requests.get('http://localhost:8004/api/v1/market/tick/BANKNIFTY', timeout=2)
            if response.status_code == 200:
                data = response.json()
                current_price = data['last_price']

                if current_price != last_price:
                    timestamp = datetime.fromisoformat(data['timestamp'].replace('+05:30', ''))
                    print(f'📈 {timestamp.strftime("%H:%M:%S")}: ₹{current_price:.2f} (Vol: {data["volume"]})')
                    last_price = current_price
                    updates += 1

            time.sleep(1)

        except Exception as e:
            print(f'⚠️  Error: {e}')
            time.sleep(1)

    print()
    print(f'✅ Monitoring completed: {updates} price updates observed')

if __name__ == "__main__":
    monitor_realtime()