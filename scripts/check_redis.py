"""Check Redis connection."""
import sys
import os
sys.path.insert(0, os.getcwd())

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
