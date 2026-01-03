from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings
from datetime import datetime
mc = get_mongo_client()
db = mc[settings.mongodb_db_name]
dbg = get_collection(db,'agent_debug')
res=dbg.insert_one({'test':1,'ts':datetime.now().isoformat()})
print('inserted id', res.inserted_id)
print('count', dbg.count_documents({}))
