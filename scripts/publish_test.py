import redis, json
r = redis.Redis(host='localhost', port=6380)
msg = json.dumps({"instrument":"BANKNIFTY26FEBFUT","last_price":45000.0,"timestamp":"2026-01-30T10:37:00+05:30"})
print('Publishing via redis-py:', repr(msg))
r.publish('raw_ticks:BANKNIFTY26FEBFUT', msg)
