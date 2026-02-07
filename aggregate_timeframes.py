#!/usr/bin/env python3
"""Quick script to aggregate existing 1min OHLC data into multiple timeframes."""
import redis
import json
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, '.')
from redis_key_manager import get_redis_key

# Default to LIVE mode
os.environ.setdefault("EXECUTION_MODE", "live")

# Connect to Redis
r = redis.Redis(host='localhost', port=6380, decode_responses=False)

# Get all 1-minute bars
redis_key_1min = get_redis_key('ohlc_sorted:BANKNIFTY26FEBFUT:1min')
bars_1min = r.zrange(redis_key_1min, 0, -1)
print(f'✓ Found {len(bars_1min)} 1-minute bars in {redis_key_1min}')

# Initialize aggregation storage
candles = {
    '5min': {},
    '15min': {},
    '1h': {},
    '4h': {}
}

# Timeframe mapping
timeframes = {
    '5min': 5,
    '15min': 15,
    '1h': 60,
    '4h': 240
}

# Process each 1-minute bar
print('Processing 1-minute bars...')
for bar_json in bars_1min:
    bar = json.loads(bar_json.decode('utf-8'))
    
    # Get timestamp
    ts_str = bar.get('timestamp') or bar.get('start_at')
    ts = datetime.fromisoformat(ts_str)
    
    # Aggregate into each timeframe
    for tf_name, tf_minutes in timeframes.items():
        # Calculate candle start time
        minutes_since_midnight = ts.hour * 60 + ts.minute
        candle_start_minute = (minutes_since_midnight // tf_minutes) * tf_minutes
        candle_start = ts.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=candle_start_minute)
        candle_key = candle_start.isoformat()
        
        # Initialize or update candle
        if candle_key not in candles[tf_name]:
            candles[tf_name][candle_key] = {
                'open': bar['open'],
                'high': bar['high'],
                'low': bar['low'],
                'close': bar['close'],
                'volume': bar['volume'],
                'start_at': candle_key,
                'timestamp': candle_key,
                'instrument': 'BANKNIFTY26FEBFUT',
                'timeframe': tf_name,
                '_stored_at': datetime.utcnow().isoformat() + '+00:00',
                '_stored_by': 'aggregate_mtf',
                '_format_version': '2.0'
            }
        else:
            c = candles[tf_name][candle_key]
            c['high'] = max(c['high'], bar['high'])
            c['low'] = min(c['low'], bar['low'])
            c['close'] = bar['close']
            c['volume'] += bar['volume']  # SUM volumes across all 1min bars

# Store aggregated candles in Redis
print('\nStoring aggregated candles...')
total_stored = 0
for tf_name, candles_dict in candles.items():
    redis_key = get_redis_key(f'ohlc_sorted:BANKNIFTY26FEBFUT:{tf_name}')
    
    for candle_key, candle in candles_dict.items():
        score = int(datetime.fromisoformat(candle_key).timestamp())
        r.zadd(redis_key, {json.dumps(candle): score})
        total_stored += 1
    
    count = r.zcard(redis_key)
    print(f'  ✓ {tf_name}: {count} bars stored')

print(f'\n✓ Total {total_stored} aggregated candles stored')
print('\nTimeframe summary:')
for tf_name in timeframes.keys():
    redis_key = get_redis_key(f'ohlc_sorted:BANKNIFTY26FEBFUT:{tf_name}')
    count = r.zcard(redis_key)
    print(f'  {tf_name}: {count} bars in {redis_key}')
