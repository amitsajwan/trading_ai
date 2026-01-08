import redis
r = redis.Redis(host="redis", port=6379, db=0)
print("Redis ping:", r.ping())
print("NIFTYBANK ts:", r.get("price:NIFTYBANK:latest_ts"))
print("BANKNIFTY ts:", r.get("price:BANKNIFTY:latest_ts"))
