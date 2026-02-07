#!/usr/bin/env python3
"""Check if live market data is fresh"""

import redis
import datetime
from datetime import timezone

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

print('LIVE DATA FRESHNESS CHECK')
print('=' * 40)

# Get current time (system local time, assuming IST)
current_time = datetime.datetime.now()

print(f'Current Time (System): {current_time.strftime("%H:%M:%S")}')

# Check latest market data
latest_price = r.get('price:BANKNIFTY:latest')
latest_ts_str = r.get('price:BANKNIFTY:latest_ts')

if latest_ts_str and latest_price:
    try:
        # Parse the stored timestamp (already in IST from collector)
        latest_ts = datetime.datetime.fromisoformat(latest_ts_str)

        # Calculate time difference directly
        time_diff = current_time - latest_ts
        seconds_old = time_diff.total_seconds()
        minutes_old = seconds_old / 60

        print(f'Last Data Update: {latest_ts.strftime("%H:%M:%S")}')
        print(f'Data Age: {seconds_old:.1f} seconds ({minutes_old:.1f} minutes)')
        print(f'Last Price: Rs.{latest_price}')

        if seconds_old < 10:  # Less than 10 seconds old
            print('[SUCCESS] Data is VERY FRESH')
        elif seconds_old < 60:  # Less than 1 minute old
            print('[SUCCESS] Data is FRESH')
        elif minutes_old < 15:  # Less than 15 minutes old
            print('[WARNING] Data is getting old')
        else:
            print('[ERROR] Data is STALE')

    except Exception as e:
        print(f'Error parsing data: {e}')
else:
    print('ERROR: No market data found')

# Check market hours
current_hour = current_time.hour
current_minute = current_time.minute
current_time_minutes = current_hour * 60 + current_minute

market_open = 9 * 60 + 15  # 9:15 AM
market_close = 15 * 60 + 30  # 3:30 PM

print()
if current_time_minutes < market_open:
    print('MARKET STATUS: Not open yet')
elif current_time_minutes > market_close:
    print('MARKET STATUS: Closed')
else:
    print('MARKET STATUS: Open')

print(f'Market hours: 9:15 AM - 3:30 PM IST')