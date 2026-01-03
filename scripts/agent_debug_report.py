from pymongo import MongoClient

c = MongoClient('mongodb://localhost:27017/')
found = False
for dbname in c.list_database_names():
    db = c[dbname]
    if 'agent_debug' in db.list_collection_names():
        col = db['agent_debug']
        print(dbname, col.count_documents({}))
        found = True
        for doc in col.find().sort([('_id', -1)]).limit(5):
            print('---')
            print('agent:', doc.get('agent'), 'type:', doc.get('type'), 'ts:', doc.get('timestamp'))
            txt = doc.get('response_text')
            if txt:
                print('response_text (first 200 chars):', txt[:200])
            else:
                print('no response_text')
if not found:
    print('No agent_debug collections found')
