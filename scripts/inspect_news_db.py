import sys
sys.path.insert(0, 'news_module/src')
from news_module.api_service import get_mongo_collection

coll = get_mongo_collection()
print('DB:', coll.database.name)
print('Collection:', coll.name)
print('Total docs:', coll.count_documents({}))
print('\nLatest 5 docs:')
for doc in coll.find().sort('stored_at', -1).limit(5):
    print('-', (doc.get('title') or '')[:120].replace('\n',' '))
    print('  source:', doc.get('source'), 'published_at:', doc.get('published_at'), 'sentiment:', doc.get('sentiment_score'))
