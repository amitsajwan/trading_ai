"""Verify system setup and configuration."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
import requests

print("=" * 60)
print("System Configuration Verification")
print("=" * 60)
print()

# Check LLM Configuration
print("LLM Configuration:")
print(f"  Provider: {settings.llm_provider}")
print(f"  Model: {settings.llm_model}")
print(f"  Groq API Key: {'[OK] Configured' if settings.groq_api_key else '[FAIL] Not configured'}")
print()

# Check Redis
try:
    import redis
    r = redis.Redis(host=settings.redis_host, port=settings.redis_port, db=settings.redis_db, socket_connect_timeout=2)
    r.ping()
    print("Redis:")
    print("  [OK] Connected")
    keys = r.keys("*")
    print(f"  Keys: {len(keys)}")
except Exception as e:
    print("Redis:")
    print(f"  [FAIL] Not connected: {e}")
print()

# Check MongoDB
try:
    from core_kernel.mongodb_schema import get_mongo_client
    client = get_mongo_client()
    client.server_info()
    print("MongoDB:")
    print("  [OK] Connected")
    db = client[settings.mongodb_db_name]
    collections = db.list_collection_names()
    print(f"  Collections: {len(collections)}")
except Exception as e:
    print("MongoDB:")
    print(f"  [FAIL] Not connected: {e}")
print()

# Check Data Feed Sources
from pathlib import Path
zerodha_configured = Path("credentials.json").exists()

print("Data Feed:")
print(f"  Zerodha: {'[OK] Configured' if zerodha_configured else '[FAIL] Not configured (run: python auto_login.py)'}")
if not zerodha_configured:
    print("  [WARN] Zerodha credentials required! Run: python auto_login.py")
print()

# Check Dashboard
try:
    r = requests.get("http://localhost:8888/api/system-health", timeout=5)
    if r.status_code == 200:
        health = r.json()
        print("Dashboard:")
        print("  [OK] Running")
        print(f"  Overall Status: {health.get('overall_status', 'unknown')}")
        print()
        print("Component Status:")
        for comp_name, comp_data in health.get("components", {}).items():
            status = comp_data.get("status", "unknown")
            message = comp_data.get("message", "")[:50]
            status_icon = "[OK]" if status == "healthy" else "[WARN]" if status == "degraded" else "[FAIL]"
            print(f"  {status_icon} {comp_name:20} {status:10} - {message}")
    else:
        print("Dashboard:")
        print(f"  [WARN] Status code: {r.status_code}")
except Exception as e:
    print("Dashboard:")
    print(f"  [FAIL] Not accessible: {e}")
print()

print("=" * 60)
print("Setup Verification Complete")
print("=" * 60)

