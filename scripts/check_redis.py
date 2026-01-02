"""Check Redis connection and provide setup instructions."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis
from config.settings import settings

print("=" * 60)
print("Redis Connection Check")
print("=" * 60)
print(f"Host: {settings.redis_host}")
print(f"Port: {settings.redis_port}")
print(f"DB: {settings.redis_db}")
print()

try:
    r = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=True,
        socket_connect_timeout=2
    )
    r.ping()
    print("SUCCESS: Redis is connected!")
    print()
    
    # Check for data
    keys = r.keys("*")
    print(f"Keys in Redis: {len(keys)}")
    if keys:
        print("Sample keys:", keys[:5])
    
    # Test write/read
    r.set("test_key", "test_value", ex=10)
    value = r.get("test_key")
    if value == "test_value":
        print("Read/Write test: PASSED")
    else:
        print("Read/Write test: FAILED")
    
    print()
    print("Redis is ready to use!")
    sys.exit(0)
    
except redis.ConnectionError as e:
    print("ERROR: Cannot connect to Redis")
    print(f"Error: {e}")
    print()
    print("To start Redis:")
    print("1. Using Docker (recommended):")
    print("   docker run -d --name redis -p 6379:6379 redis:7-alpine")
    print()
    print("2. Or start Docker Desktop and run:")
    print("   powershell -ExecutionPolicy Bypass -File scripts/start_redis.ps1")
    print()
    print("3. Or install Redis for Windows:")
    print("   https://github.com/microsoftarchive/redis/releases")
    print()
    print("Note: System will work in fallback mode without Redis")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

