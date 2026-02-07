import redis, json, time
r_pub = redis.Redis(host='localhost', port=6380, decode_responses=False)
r_sub = redis.Redis(host='localhost', port=6380, decode_responses=False)
p = r_sub.pubsub()
p.subscribe('raw_ticks:BANKNIFTY26FEBFUT')
print('Subscribed locally, waiting for SUBSCRIBE confirmation...')
# wait for subscription confirmation
start = time.time()
while time.time() - start < 2:
    m = p.get_message(timeout=0.5)
    if m and m.get('type') == 'subscribe':
        print('SUBSCRIBE confirmed:', m)
        break

msg_to_send = json.dumps({"instrument":"BANKNIFTY26FEBFUT","last_price":45000.0,"timestamp":"2026-01-30T10:36:00+05:30"})
print('Publishing:', msg_to_send)
r_pub.publish('raw_ticks:BANKNIFTY26FEBFUT', msg_to_send)
# wait for the published message
start = time.time()
while time.time() - start < 2:
    m = p.get_message(timeout=0.5)
    if m and m.get('type') == 'message':
        print('Received MSG:', m)
        break
else:
    print('No message received after publish')

if m and 'data' in m:
    d = m['data']
    print('TYPE:', type(d))
    print('REPR:', repr(d))
    try:
        if isinstance(d, bytes):
            print('JSON LOADS:', json.loads(d.decode('utf-8')))
        else:
            print('JSON LOADS:', json.loads(d))
    except Exception as e:
        print('json.loads error', e)
