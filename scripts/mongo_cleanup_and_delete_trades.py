#!/usr/bin/env python3
from pymongo import MongoClient
from datetime import datetime, timedelta
import json
from pathlib import Path
import time

client = MongoClient('mongodb://localhost:27017/')
db = client.zerodha_trading
cutoff = datetime.utcnow() - timedelta(days=7)
collection = db.trades_executed

# Find docs
try:
    docs = list(collection.find({'timestamp': {'$lt': cutoff.isoformat()}}))
except Exception:
    docs = list(collection.find({'timestamp': {'$lt': cutoff}}))

backup_dir = Path('backups')
backup_dir.mkdir(exist_ok=True)
backup_file = backup_dir / f'trades_executed_backup_{int(time.time())}.json'
with open(backup_file, 'w', encoding='utf-8') as f:
    json.dump(docs, f, default=str, indent=2)
print(f'Backed up {len(docs)} docs to {backup_file}')

# Delete docs
if docs:
    try:
        try:
            res = collection.delete_many({'timestamp': {'$lt': cutoff.isoformat()}})
        except Exception:
            res = collection.delete_many({'timestamp': {'$lt': cutoff}})
        print(f'Deleted {res.deleted_count} documents from trades_executed')
    except Exception as e:
        print('Delete failed:', e)
else:
    print('No documents to delete')
