import sys, traceback
sys.path.insert(0, './market_data/src')
try:
    from market_data.api import build_store
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    r.ping()
    store = build_store(redis_client=r)
    print('OK', type(store), store)
except Exception:
    traceback.print_exc()