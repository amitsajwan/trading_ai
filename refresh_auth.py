#!/usr/bin/env python3
"""Refresh Zerodha credentials with interactive login"""

from market_data.tools.kite_auth_service import KiteAuthService
import redis

print("🔐 Refreshing Zerodha credentials...")
svc = KiteAuthService('credentials.json')

print("\n📱 Triggering interactive login...")
print("You have 120 seconds to complete the login in your browser")

success = svc.trigger_interactive_login(timeout=120)

if success:
    print("\n✅ Login successful!")
    creds = svc.load_credentials()
    token = creds.get('access_token', '')
    user_id = creds.get('user_id', '')
    
    print(f"   Token: {token[:20]}...")
    print(f"   User: {user_id}")
    
    print("\n💾 Saving to Redis...")
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.set('kite:access_token', token)
        r.set('kite:user_id', user_id)
        print("   ✓ Redis updated")
    except Exception as e:
        print(f"   ⚠️ Redis error: {e}")
    
    print("\n🚀 Restarting WebSocket collector...")
    import subprocess
    subprocess.run(['docker-compose', 'restart', 'websocket-tick-collector-banknifty'], check=False)
else:
    print("\n❌ Login failed or timed out")
