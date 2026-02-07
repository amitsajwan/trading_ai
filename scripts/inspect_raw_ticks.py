#!/usr/bin/env python3
"""Subscribe to raw_ticks channel and print raw message repr for debugging."""
import redis
import time

CHANNEL = "raw_ticks:BANKNIFTY26FEBFUT"

r = redis.Redis(host='localhost', port=6380, db=0, decode_responses=False)
ps = r.pubsub()
ps.subscribe(CHANNEL)
print(f"Subscribed to {CHANNEL}, listening for up to 5 messages...")
count = 0
try:
    for message in ps.listen():
        print("----MESSAGE-----")
        print("repr(message):", repr(message))
        data = message.get('data')
        print("type(data):", type(data))
        if isinstance(data, (bytes, bytearray)):
            print("data repr:", repr(data))
            try:
                decoded = data.decode('utf-8')
                print("decoded:", decoded)
            except Exception as de:
                print("decode error:", de)
                print("decoded (replace):", data.decode('utf-8', errors='replace'))
        else:
            print("data repr:", repr(data))
        count += 1
        if count >= 5:
            break
except KeyboardInterrupt:
    print("Interrupted")
finally:
    try:
        ps.close()
    except Exception:
        pass

print("Done")
