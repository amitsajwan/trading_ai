#!/usr/bin/env python
"""Populate Docker MongoDB with Bitcoin demo data."""

from mongodb_schema import get_mongo_client
import requests
from datetime import datetime, timedelta
import uuid

print("Starting data population...")

# Connect to MongoDB
db = get_mongo_client()['zerodha_trading']
print("✅ Connected to MongoDB")

# Fetch Bitcoin data from Binance
print("Fetching Bitcoin data from Binance...")
response = requests.get('https://api.binance.com/api/v3/klines', params={
    'symbol': 'BTCUSDT',
    'interval': '1h',
    'limit': 168
})
klines = response.json()
print(f"Got {len(klines)} candles from Binance")

# Store OHLC data
print("Storing candles to MongoDB...")
for k in klines:
    db.ohlc_history.update_one(
        {
            'instrument': 'BTC-USD',
            'timestamp': datetime.fromtimestamp(k[0]/1000),
            'interval': '1h'
        },
        {'$set': {
            'instrument': 'BTC-USD',
            'timestamp': datetime.fromtimestamp(k[0]/1000),
            'open': float(k[1]),
            'high': float(k[2]),
            'low': float(k[3]),
            'close': float(k[4]),
            'volume': float(k[5]),
            'interval': '1h'
        }},
        upsert=True
    )

print(f'✅ Loaded {len(klines)} candles')

# Create demo trades
print("Creating demo trades...")
now = datetime.now()

db.trades_executed.delete_many({})

trades = [
    {
        'trade_id': str(uuid.uuid4()),
        'instrument': 'BTC-USD',
        'entry_timestamp': now - timedelta(hours=24),
        'entry_price': 90500.0,
        'exit_timestamp': now - timedelta(hours=20),
        'exit_price': 91200.0,
        'quantity': 0.1,
        'pnl': 70.0,
        'status': 'CLOSED',
        'side': 'BUY'
    },
    {
        'trade_id': str(uuid.uuid4()),
        'instrument': 'BTC-USD',
        'entry_timestamp': now - timedelta(hours=18),
        'entry_price': 91000.0,
        'exit_timestamp': now - timedelta(hours=15),
        'exit_price': 90200.0,
        'quantity': 0.1,
        'pnl': -80.0,
        'status': 'CLOSED',
        'side': 'BUY'
    },
    {
        'trade_id': str(uuid.uuid4()),
        'instrument': 'BTC-USD',
        'entry_timestamp': now - timedelta(hours=12),
        'entry_price': 90800.0,
        'exit_timestamp': now - timedelta(hours=8),
        'exit_price': 91500.0,
        'quantity': 0.15,
        'pnl': 105.0,
        'status': 'CLOSED',
        'side': 'BUY'
    },
    {
        'trade_id': str(uuid.uuid4()),
        'instrument': 'BTC-USD',
        'entry_timestamp': now - timedelta(hours=6),
        'entry_price': 91300.0,
        'exit_timestamp': now - timedelta(hours=3),
        'exit_price': 91800.0,
        'quantity': 0.12,
        'pnl': 60.0,
        'status': 'CLOSED',
        'side': 'BUY'
    },
    {
        'trade_id': str(uuid.uuid4()),
        'instrument': 'BTC-USD',
        'entry_timestamp': now - timedelta(hours=2),
        'entry_price': 91600.0,
        'quantity': 0.1,
        'pnl': 0.0,
        'status': 'OPEN',
        'side': 'BUY'
    }
]

for trade in trades:
    db.trades_executed.insert_one(trade)

print(f'✅ Created {len(trades)} demo trades (4 closed, 1 open)')
print("\n" + "="*70)
print("DATABASE POPULATION COMPLETE!")
print(f"  - {len(klines)} hourly Bitcoin candles loaded")
print(f"  - {len(trades)} demo trades created")
print("  - Refresh your dashboard to see the data!")
print("="*70)
