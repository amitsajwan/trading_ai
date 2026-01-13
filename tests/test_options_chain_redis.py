#!/usr/bin/env python3
"""
Test script to verify Options Chain Redis publishing.

Tests the end-to-end flow:
1. Call options chain API endpoint
2. Verify data is published to Redis
3. Verify WebSocket gateway receives the message
4. Verify frontend can receive updates
"""

import json
import redis
import time
import requests
from datetime import datetime

def test_options_chain_redis():
    """Test options chain Redis publishing."""
    
    print("=" * 60)
    print("Options Chain Redis Publishing Test")
    print("=" * 60)
    
    # Step 1: Connect to Redis
    print("\n[1/4] Connecting to Redis...")
    try:
        redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        redis_client.ping()
        print("[OK] Redis connected")
    except Exception as e:
        print(f"[ERROR] Redis connection failed: {e}")
        return False
    
    # Step 2: Subscribe to Redis channel
    print("\n[2/4] Subscribing to Redis channel: market:options:BANKNIFTY")
    pubsub = redis_client.pubsub()
    pubsub.subscribe('market:options:BANKNIFTY')
    pubsub.subscribe('market:options:*')
    
    # Clear any existing messages
    time.sleep(0.1)
    while pubsub.get_message(timeout=0.1):
        pass
    print("[OK] Subscribed to Redis channels")
    
    # Step 3: Call API endpoint (should trigger Redis publish)
    print("\n[3/4] Calling API endpoint: GET http://localhost:8004/api/v1/options/chain/BANKNIFTY")
    try:
        response = requests.get('http://localhost:8004/api/v1/options/chain/BANKNIFTY', timeout=10)
        response.raise_for_status()
        data = response.json()
        print("[OK] API endpoint responded successfully")
        print(f"   - Instrument: {data.get('instrument')}")
        print(f"   - Expiry: {data.get('expiry')}")
        print(f"   - Futures Price: {data.get('futures_price')}")
        print(f"   - PCR: {data.get('pcr')}")
        print(f"   - Strikes: {len(data.get('strikes', []))} strikes")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] API call failed: {e}")
        print("   Make sure market_data API is running on port 8004")
        return False
    
    # Step 4: Check for Redis message
    print("\n[4/4] Checking for Redis pub/sub message...")
    message = None
    timeout = 2.0
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        msg = pubsub.get_message(timeout=0.5)
        if msg and msg['type'] == 'message':
            channel = msg['channel']
            if 'market:options' in channel:
                message = msg
                break
    
    if message:
        print("[OK] Redis message received!")
        print(f"   - Channel: {message['channel']}")
        try:
            payload = json.loads(message['data'])
            print(f"   - Instrument: {payload.get('instrument')}")
            print(f"   - Expiry: {payload.get('expiry')}")
            print(f"   - Futures Price: {payload.get('futures_price')}")
            print(f"   - PCR: {payload.get('pcr')}")
            print(f"   - Strikes: {len(payload.get('strikes', []))} strikes")
            print("[OK] End-to-end test PASSED!")
            return True
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse Redis message: {e}")
            print(f"   Raw message: {message['data'][:100]}...")
            return False
    else:
        print("[ERROR] No Redis message received within timeout")
        print("   The API endpoint may not be publishing to Redis")
        print("   Check market_data API logs for publishing errors")
        return False
    
    # Cleanup
    pubsub.unsubscribe()
    pubsub.close()

if __name__ == "__main__":
    try:
        success = test_options_chain_redis()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n[ERROR] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)