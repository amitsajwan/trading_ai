#!/usr/bin/env python3
"""Check timestamp synchronization"""

import redis
import datetime
from datetime import timezone

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

print('TIME SYNCHRONIZATION CHECK')
print('=' * 40)

# Get current time
now = datetime.datetime.now()
ist_offset = datetime.timedelta(hours=5, minutes=30)
ist_now = now + ist_offset

print(f'Current system time (IST): {ist_now.strftime("%H:%M:%S")}')

# Check Redis timestamps
price = r.get('price:BANKNIFTY:latest')
ts_str = r.get('price:BANKNIFTY:latest_ts')

print(f'Latest price: {price}')
print(f'Timestamp from Redis: {ts_str}')

if ts_str:
    try:
        # Parse the timestamp
        ts = datetime.datetime.fromisoformat(ts_str)
        print(f'Parsed timestamp: {ts}')
        print(f'Timezone info: {ts.tzinfo}')

        # Calculate age
        if ts.tzinfo is None:
            # Assume it's already IST (as stored)
            ts_ist = ts
        else:
            # Convert to IST
            ts_ist = ts.astimezone(timezone.utc) + ist_offset

        age = ist_now - ts_ist
        print(f'Data age: {age.total_seconds():.1f} seconds')

        if age.total_seconds() < 60:  # Less than 1 minute old
            print('STATUS: Data is FRESH')
        elif age.total_seconds() < 300:  # Less than 5 minutes old
            print('STATUS: Data is RECENT')
        else:
            print('STATUS: Data is STALE')

    except Exception as e:
        print(f'Error parsing timestamp: {e}')
else:
    print('ERROR: No timestamp found in Redis')