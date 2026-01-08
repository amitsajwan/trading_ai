import redis
from datetime import datetime

r = redis.Redis(host="redis", port=6379, db=0)
instrument = "NIFTYBANK"

print("Current time:", datetime.now().isoformat())

latest_ts_data = r.get(f"price:{instrument}:latest_ts")
print("Raw timestamp data:", latest_ts_data)

if latest_ts_data:
    ts_str = latest_ts_data.decode()
    print("Timestamp string:", ts_str)

    data_time = datetime.fromisoformat(ts_str)
    print("Parsed data time:", data_time)
    print("Current time:", datetime.now())

    time_diff = (datetime.now() - data_time).total_seconds()
    print("Time difference (seconds):", time_diff)
    print("Is stale (300s threshold):", time_diff > 300)
