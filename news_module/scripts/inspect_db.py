#!/usr/bin/env python3
from pymongo import MongoClient
c=MongoClient('mongodb://localhost:27017/zerodha_trading')
db=c.get_database()
print('Total news:', db['news'].count_documents({}))
print('Sample docs (10):')
for d in db['news'].find().sort('published_at',-1).limit(10):
    print('-', d.get('title')[:120], '| instruments=', d.get('instruments'), '| source=', d.get('source'))
