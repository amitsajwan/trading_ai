import redis
import json

r = redis.Redis(host='localhost', port=6379, decode_responses=True)
keys = r.keys('tick:BANKNIFTY:*')
print(f'Found {len(keys)} BANKNIFTY tick keys')

if keys:
    sorted_keys = sorted(keys)
    print(f'First key: {sorted_keys[0]}')

    data = r.get(sorted_keys[0])
    if data:
        tick = json.loads(data)
        print(f'First tick timestamp: {tick.get("timestamp", "N/A")}')
        print(f'First tick price: {tick.get("last_price", "N/A")}')

        # Check if it's actually market hours
        ts = tick.get("timestamp", "")
        if ts and "09:15" in ts:
            print("SUCCESS: Timestamp shows market open time (9:15 AM)!")
        elif ts and "00:00" in ts:
            print("ISSUE: Timestamp still shows midnight (00:00)")
        else:
            print(f"OTHER: Timestamp is {ts}")