import redis, os
r = redis.Redis(host=os.getenv('REDIS_HOST','localhost'), port=int(os.getenv('REDIS_PORT','6379')), db=0, decode_responses=True)
keys = list(r.scan_iter(match='price:*'))
print('price keys:', keys)
for k in keys:
    print(k, '->', r.get(k))
keys2 = list(r.scan_iter(match='depth:*'))
print('depth keys:', keys2)
for k in keys2:
    print(k, '->', r.get(k))
