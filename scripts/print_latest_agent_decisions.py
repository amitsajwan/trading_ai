from pymongo import MongoClient
import pprint

c = MongoClient('mongodb://localhost:27017/')
db = c['zerodha_trading']
col = db['agent_decisions']
print('count', col.count_documents({}))
if col.count_documents({}) > 0:
    doc = col.find_one(sort=[('timestamp', -1)])
    print('latest timestamp', doc.get('timestamp'))
    print('agents:', list(doc.get('agent_decisions', {}).keys()))
    pprint.pprint(doc.get('agent_decisions', {}).get('technical'))
else:
    print('No agent_decisions documents found')
