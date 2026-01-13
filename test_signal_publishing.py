#!/usr/bin/env python3
"""
Test signal publishing mechanism.
"""

import requests
import json
import redis
import time

def test_signal_publishing():
    """Test signal publishing to Redis."""
    print('🔧 Testing Signal Publishing Mechanism')
    print('=' * 45)

    # Connect to Redis
    try:
        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        redis_client.ping()
        print('✅ Redis connection: OK')
    except Exception as e:
        print(f'❌ Redis connection failed: {e}')
        return

    # Clear existing signal keys for clean test
    print('\n1. Clearing existing signal keys...')
    signal_keys = redis_client.keys('signal:*')
    engine_keys = redis_client.keys('engine:signal*')

    if signal_keys:
        redis_client.delete(*signal_keys)
        print(f'   Cleared {len(signal_keys)} signal keys')

    if engine_keys:
        redis_client.delete(*engine_keys)
        print(f'   Cleared {len(engine_keys)} engine signal keys')

    # Check current signals in API
    print('\n2. Checking current signals in API...')
    response = requests.get('http://localhost:8006/api/v1/signals/BANKNIFTY')
    if response.status_code == 200:
        signals = response.json()
        print(f'   API signals: {len(signals)}')
    else:
        print(f'   ❌ API check failed: {response.status_code}')

    # Run analysis to potentially create signals
    print('\n3. Running analysis...')
    response = requests.post('http://localhost:8006/api/v1/analyze', json={'instrument': 'BANKNIFTY'}, timeout=30)
    if response.status_code == 200:
        analysis = response.json()
        print(f'   Analysis result: {analysis["decision"]} ({analysis["confidence"]:.1%})')
    else:
        print(f'   ❌ Analysis failed: {response.status_code}')

    # Check if signals appeared in Redis
    print('\n4. Checking Redis for published signals...')
    time.sleep(1)  # Give it a moment

    patterns = ['signal:*', 'engine:signal*', 'engine:signal:BANKNIFTY*']
    total_keys = 0

    for pattern in patterns:
        keys = redis_client.keys(pattern)
        print(f'   {pattern}: {len(keys)} keys')
        total_keys += len(keys)

        if keys and len(keys) <= 3:  # Show details for small numbers
            for key in keys:
                data = redis_client.get(key)
                if data:
                    try:
                        signal_data = json.loads(data)
                        action = signal_data.get('action', 'unknown')
                        print(f'     • {key}: {action}')
                    except:
                        print(f'     • {key}: {data[:50]}...')

    if total_keys == 0:
        print('   ❌ No signals found in Redis - publishing may be broken')
        print('   💡 Signals exist in API but not being published to Redis pub/sub')
    else:
        print(f'   ✅ Found {total_keys} signal keys in Redis')

    # Check if WebSocket gateway would receive these
    print('\n5. Testing WebSocket gateway signal reception...')
    try:
        import websockets
        import asyncio

        async def test_ws_signals():
            uri = "ws://localhost:8889/ws"
            async with websockets.connect(uri) as websocket:
                # Subscribe to signal channels
                subscribe_msg = {
                    'type': 'subscribe',
                    'channels': ['engine:signal', 'engine:signal:BANKNIFTY']
                }
                await websocket.send(json.dumps(subscribe_msg))

                # Wait for any signal messages
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    data = json.loads(msg)
                    if 'type' in data and 'signal' in data['type'].lower():
                        print(f'   ✅ Signal message received: {data["type"]}')
                    else:
                        print(f'   ℹ️  Message received: {data["type"]}')
                except asyncio.TimeoutError:
                    print('   ℹ️  No signal messages received in 3s (normal if no new signals)')

        asyncio.run(test_ws_signals())

    except Exception as e:
        print(f'   ❌ WebSocket test failed: {e}')

if __name__ == "__main__":
    test_signal_publishing()