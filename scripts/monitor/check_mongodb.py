"""ARCHIVED: The original check script was archived and the archive folder was later removed (2026-01-03).
The compressed backup for this file was permanently deleted on 2026-01-03 per repository cleanup."""

print("This check script's original content was archived and the compressed backup was permanently deleted on 2026-01-03. Contact maintainers to request restoration.")

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

