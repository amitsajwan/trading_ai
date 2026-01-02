"""Check MongoDB connection."""
import sys
import os
sys.path.insert(0, os.getcwd())

try:
    import pymongo
    from config.settings import settings
    client = pymongo.MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=2000
    )
    client.server_info()
    print('MONGODB_OK')
    sys.exit(0)
except ImportError:
    print('MONGODB_MODULE_MISSING')
    sys.exit(1)
except Exception as e:
    print('MONGODB_ERROR', str(e)[:50])
    sys.exit(1)

