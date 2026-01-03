"""System setup script for GenAI Trading System."""

import os
import sys
from pathlib import Path

def check_mongodb():
    """Check MongoDB connection."""
    try:
        import pymongo
        client = pymongo.MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=2000)
        client.server_info()
        print("✅ MongoDB: Connected")
        return True
    except Exception as e:
        print(f"❌ MongoDB: Not connected - {e}")
        print("   Please start MongoDB: mongod")
        return False

def check_redis():
    """Check Redis connection."""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0, socket_connect_timeout=2)
        r.ping()
        print("✅ Redis: Connected")
        return True
    except Exception as e:
        print(f"⚠️  Redis: Not connected - {e}")
        print("   Redis is optional for testing but required for full operation.")
        print("   Install Redis: https://redis.io/download")
        print("   Or use Docker: docker run -d -p 6379:6379 redis")
        return False

def check_env_file():
    """Check if .env file exists."""
    env_path = Path(".env")
    env_example = Path(".env.example")
    
    if env_path.exists():
        print("✅ .env file: Exists")
        return True
    else:
        print("⚠️  .env file: Not found")
        if env_example.exists():
            print(f"   Copy {env_example} to .env and configure your API keys")
        else:
            print("   Create .env file with your API keys")
        return False

def check_credentials():
    """Check if credentials.json exists (or credentials.example.json is present)."""
    cred_path = Path("credentials.json")
    example_path = Path("credentials.example.json")
    if cred_path.exists():
        print("✅ credentials.json: Exists")
        return True
    elif example_path.exists():
        print("⚠️  credentials.json: Not found")
        print("   A template `credentials.example.json` is present. Copy it to `credentials.json` and fill in your values, or run: python auto_login.py")
        return False
    else:
        print("⚠️  credentials.json: Not found")
        print("   No credentials template found. Run: python auto_login.py or create credentials.json from your live account data")
        return False

def setup_mongodb_schema():
    """Initialize MongoDB schema."""
    try:
        from mongodb_schema import setup_mongodb
        setup_mongodb()
        print("✅ MongoDB schema: Initialized")
        return True
    except Exception as e:
        print(f"❌ MongoDB schema: Failed - {e}")
        return False

def main():
    """Run system setup checks."""
    print("=" * 60)
    print("GenAI Trading System - Setup Check")
    print("=" * 60)
    print()
    
    checks = {
        "MongoDB": check_mongodb(),
        "Redis": check_redis(),
        ".env file": check_env_file(),
        "credentials.json": check_credentials(),
    }
    
    print()
    print("=" * 60)
    
    if all(checks.values()):
        print("✅ All checks passed! System is ready.")
        print()
        print("Initializing MongoDB schema...")
        if setup_mongodb_schema():
            print()
            print("🚀 You can now run: python trading_orchestration/main.py")
        else:
            print("⚠️  MongoDB schema setup failed. Please check errors above.")
    else:
        print("⚠️  Some checks failed. Please address the issues above.")
        print()
        print("Quick Setup Guide:")
        print("1. MongoDB: Already connected ✅")
        print("2. Redis: Install and start Redis (optional for testing)")
        print("3. .env: Copy .env.example to .env and add your API keys")
        print("4. Credentials: Run 'python auto_login.py' to authenticate with Zerodha")
        print("5. Schema: MongoDB schema will be initialized automatically")
    
    print("=" * 60)

if __name__ == "__main__":
    main()

