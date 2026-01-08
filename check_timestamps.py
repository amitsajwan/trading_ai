import redis
import json

r = redis.Redis(host='localhost', port=6379, decode_responses=True)
keys = r.keys('tick:BANKNIFTY:*')
print(f'Found {len(keys)} BANKNIFTY tick keys')

# Sort keys to get chronological order
sorted_keys = sorted(keys)
print("\nFirst 5 timestamps:")
for key in sorted_keys[:5]:
    data = r.get(key)
    if data:
        tick = json.loads(data)
        print(f'{key}: price={tick.get("last_price", "N/A")}, time={tick.get("timestamp", "N/A")}')

print("\nLast 5 timestamps:")
for key in sorted_keys[-5:]:
    data = r.get(key)
    if data:
        tick = json.loads(data)
        print(f'{key}: price={tick.get("last_price", "N/A")}, time={tick.get("timestamp", "N/A")}')