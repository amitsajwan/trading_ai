import redis
import time
import json

r = redis.Redis(host='localhost', port=6380, decode_responses=False)
p = r.pubsub()
p.subscribe('raw_ticks:BANKNIFTY26FEBFUT')
print('Subscribed, waiting up to 10s...')
start = time.time()
msg = None
while time.time() - start < 10:
    msg = p.get_message(timeout=0.5)
    if msg:
        break
print('MSG:', msg)
if msg and 'data' in msg:
    data = msg['data']
    print('TYPE:', type(data))
    print('REPR:', repr(data))
    try:
        # decode if bytes
        if isinstance(data, bytes):
            d = data.decode('utf-8')
        else:
            d = data
        print('JSON LOADS ->', json.loads(d))
    except Exception as e:
        print('json.loads error:', e)
