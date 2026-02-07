#!/usr/bin/env python3
from pymongo import MongoClient
from datetime import datetime, timedelta
client = MongoClient('mongodb://localhost:27017/')
db = client.zerodha_trading
cutoff = datetime.utcnow() - timedelta(days=7)
collections = ['agent_decisions','agent_discussions','trades_executed','ohlc_history','signals']
for coll in collections:
    col = db[coll]
    try:
        count = col.count_documents({'timestamp': {'$lt': cutoff.isoformat()}})
    except Exception:
        # fallback if timestamps are stored as datetimes
        count = col.count_documents({'timestamp': {'$lt': cutoff}})
    print(f"{coll}: {count} docs older than 7 days")
