from pymongo import MongoClient
import os
uri=os.getenv('MONGODB_URI','mongodb://localhost:27017/zerodha_trading')
print('Using URI:',uri)
try:
    client=MongoClient(uri, serverSelectionTimeoutMS=3000)
    client.admin.command('ping')
    print('MongoDB ping: OK')
    print('DBs:', client.list_database_names()[:10])
except Exception as e:
    print('MongoDB ping failed:', e)
