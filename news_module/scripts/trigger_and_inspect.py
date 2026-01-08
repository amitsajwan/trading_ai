#!/usr/bin/env python3
import requests
from pymongo import MongoClient

base='http://localhost:8005'
print('POST /api/v1/news/collect')
r = requests.post(base + '/api/v1/news/collect', json=None, timeout=20)
print('status', r.status_code)
print(r.text)

print('\nGET /api/v1/news/BANKNIFTY')
r2 = requests.get(base + '/api/v1/news/BANKNIFTY?limit=10', timeout=20)
print('status', r2.status_code)
print(r2.text)

print('\nGET /api/v1/news/NIFTY')
r3 = requests.get(base + '/api/v1/news/NIFTY?limit=10', timeout=20)
print('status', r3.status_code)
print(r3.text)

# Inspect MongoDB docs
client = MongoClient('mongodb://localhost:27017/zerodha_trading')
db = client.get_database()
print('\nMongoDB collection count:', db['news'].count_documents({}))
print('Sample docs (limit 10):')
for d in db['news'].find().sort('published_at', -1).limit(10):
    print('-', d.get('title')[:120], '| instruments=', d.get('instruments'))
