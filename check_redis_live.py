import os
import sys
import json
import textwrap

try:
    import redis
except Exception as e:
    print('Missing dependency redis:', e)
    sys.exit(2)

SHORT = 400


def trunc(s, width=SHORT):
    if s is None:
        return "<nil>"
    if isinstance(s, (bytes, bytearray)):
        try:
            s = s.decode('utf-8', errors='replace')
        except Exception:
            s = str(s)
    return textwrap.shorten(str(s), width=width, placeholder='...')


def sample_key(r, key):
    try:
        t = r.type(key)
        if isinstance(t, bytes):
            t = t.decode()
    except Exception:
        t = 'unknown'

    print(f"\nKey: {key} (type={t})")

    try:
        if t == 'string':
            v = r.get(key)
            print('  value:', trunc(v))

        elif t == 'zset':
            count = r.zcard(key)
            print(f'  zcard: {count}')
            sample = r.zrange(key, -3, -1)
            print(f'  last {len(sample)} entries:')
            for s in sample:
                try:
                    obj = json.loads(s)
                    pretty = json.dumps(obj, indent=2, ensure_ascii=False)
                    print('   -', trunc(pretty, 1000))
                except Exception:
                    print('   -', trunc(s))

        elif t == 'hash':
            h = r.hgetall(key)
            keys = list(h.keys())[:10]
            print('  hash fields sample:', keys)
            for k in keys:
                print('   ', k, '=', trunc(h.get(k)))

        elif t == 'list':
            items = r.lrange(key, -5, -1)
            print(f'  last {len(items)} items:')
            for it in items:
                try:
                    obj = json.loads(it)
                    print('   -', trunc(json.dumps(obj, ensure_ascii=False), 1000))
                except Exception:
                    print('   -', trunc(it))

        elif t == 'set':
            members = list(r.smembers(key))[:10]
            print('  members sample:', members)

        else:
            print('  (unhandled type or empty)')

    except Exception as e:
        print('  error reading key:', e)


def scan_pattern(r, pattern):
    keys = list(r.scan_iter(match=pattern, count=200))
    print(f"\nPattern '{pattern}' -> {len(keys)} keys")
    for k in keys:
        sample_key(r, k)
    return len(keys)


def main():
    host = os.getenv('REDIS_HOST', 'localhost')
    port = int(os.getenv('REDIS_PORT', '6380'))
    db = int(os.getenv('REDIS_DB', '0'))

    try:
        r = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        r.ping()
    except Exception as e:
        print(f'Failed to connect to Redis at {host}:{port} db={db}: {e}')
        sys.exit(3)

    print(f'Connected to Redis @ {host}:{port} db={db}')

    try:
        mode = r.get('system:execution_mode')
        print('system:execution_mode ->', mode)
    except Exception:
        pass

    live_keys = list(r.scan_iter(match='live:*', count=500))
    print('Total live-prefixed keys found:', len(live_keys))

    patterns = [
        'live:ohlc_sorted:*:*',
        'live:ohlc:*:*',
        'live:websocket:tick:*:latest',
        'live:price:*:latest',
        'live:enhanced_ticks:*',
        'live:indicators:*:*',
        'live:options:*',
        'live:depth:*:*',
    ]

    summary = {}
    for pat in patterns:
        cnt = scan_pattern(r, pat)
        summary[pat] = cnt

    print('\nSummary (non-zero patterns):')
    for pat, cnt in summary.items():
        if cnt > 0:
            print(f' - {pat}: {cnt}')

    if not live_keys:
        print('\nNo live-prefixed keys found in Redis. Data ingestion may not be writing to live namespace.')
    else:
        print('\nSample of live keys (first 30):')
        for k in live_keys[:30]:
            print(' -', k)


if __name__ == '__main__':
    main()
