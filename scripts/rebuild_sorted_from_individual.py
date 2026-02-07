#!/usr/bin/env python3
import redis, json, time
from datetime import datetime

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
inst = 'BANKNIFTY26JANFUT'
frame = '1min'
sorted_key = f'ohlc_sorted:{inst}:{frame}'
tmp_key = sorted_key + ':rebuild'
backup_key = sorted_key + ':backup_' + str(int(time.time()))

print('Counts before:', r.zcount(sorted_key, '-inf', '+inf'), len(r.keys(f'ohlc:{inst}:{frame}:*')))
# Backup original
if r.exists(sorted_key):
    r.rename(sorted_key, backup_key)
    print('Backed up sorted set to', backup_key)

# Ensure tmp empty
if r.exists(tmp_key):
    r.delete(tmp_key)

# Rebuild from individual keys
keys = r.keys(f'ohlc:{inst}:{frame}:*')
added = 0
for k in keys:
    try:
        data = r.get(k)
        if not data:
            continue
        bar = json.loads(data)
        ts = bar.get('timestamp')
        score = None
        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                score = dt.timestamp()
            except Exception:
                score = time.time()
        else:
            try:
                score = float(ts)
            except Exception:
                score = time.time()
        r.zadd(tmp_key, {json.dumps(bar, default=str): score})
        added += 1
    except Exception as e:
        print('skip', k, e)

print('Added to tmp:', added)
# Finalize: rename tmp to sorted_key
if r.exists(tmp_key):
    # Remove if existing sorted set key (should have been renamed already to backup)
    if r.exists(sorted_key):
        r.delete(sorted_key)
    r.rename(tmp_key, sorted_key)

print('Counts after:', r.zcount(sorted_key, '-inf', '+inf'), len(r.keys(f'ohlc:{inst}:{frame}:*')))
print('Done')
