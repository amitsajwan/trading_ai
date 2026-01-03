"""ARCHIVED: The original check script was archived and the archive folder was later removed (2026-01-03).
The compressed backup for this file was permanently deleted on 2026-01-03 per repository cleanup."""

print("This check script's original content was archived and the compressed backup was permanently deleted on 2026-01-03. Contact maintainers to request restoration.")

try:
    import redis
    from config.settings import settings
    r = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        socket_connect_timeout=2,
        socket_timeout=2
    )
    r.ping()
    print('REDIS_OK')
    sys.exit(0)
except ImportError:
    print('REDIS_MODULE_MISSING')
    sys.exit(1)
except Exception as e:
    print('REDIS_ERROR', str(e)[:50])
    sys.exit(1)
