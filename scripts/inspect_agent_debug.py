from mongodb_schema import get_mongo_client, get_collection

mc = get_mongo_client()
db = mc.get_database()
dbg = get_collection(db, 'agent_debug')
print('agent_debug count =', dbg.count_documents({}))
for doc in dbg.find().sort([('_id', -1)]).limit(10):
    print(doc.get('timestamp'), doc.get('agent'), doc.get('type'), list(doc.keys())[:8])
