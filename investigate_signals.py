#!/usr/bin/env python3
"""
Investigate why signals aren't showing in dashboard.
"""

import requests
import json

def investigate_signals():
    """Investigate signal data flow."""
    print('🔍 Investigating Signal Data Flow')
    print('=' * 40)

    # Check current signals in backend
    print('1. Checking current signals in backend...')
    response = requests.get('http://localhost:8006/api/v1/signals/BANKNIFTY')
    if response.status_code == 200:
        signals = response.json()
        print(f'   Backend signals: {len(signals)}')
        for signal in signals:
            print(f'     • {signal["action"]} (id: {signal["signal_id"][:8]}...)')
            print(f'       Status: {signal["status"]}, Confidence: {signal["confidence"]:.1%}')
    else:
        print(f'   ❌ Signal fetch failed: {response.status_code} - {response.text}')

    # Check if signals are being published to Redis
    print('\n2. Checking Redis for signal publications...')
    try:
        import redis
        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

        # Check signal keys
        signal_keys = redis_client.keys('signal:*')
        print(f'   Signal keys in Redis: {len(signal_keys)}')
        for key in signal_keys[:3]:  # Show first 3
            data = redis_client.get(key)
            if data:
                try:
                    signal_data = json.loads(data)
                    print(f'     • {key}: {signal_data.get("action", "unknown")}')
                except:
                    print(f'     • {key}: {data[:50]}...')

        # Check pub/sub channels
        print(f'   Active pub/sub channels: checking...')

    except Exception as e:
        print(f'   ❌ Redis check failed: {e}')

    # Check engine API health
    print('\n3. Checking Engine API health...')
    response = requests.get('http://localhost:8006/health')
    if response.status_code == 200:
        health = response.json()
        print('   ✅ Engine API healthy')
        if 'dependencies' in health:
            deps = health['dependencies']
            print(f'   Dependencies: orchestrator={deps.get("orchestrator", "unknown")}, mongodb={deps.get("mongodb", "unknown")}')
    else:
        print(f'   ❌ Engine API health check failed: {response.status_code}')

    # Test signal creation
    print('\n4. Testing signal creation...')
    try:
        # Trigger analysis to potentially create new signals
        response = requests.post('http://localhost:8006/api/v1/analyze', json={'instrument': 'BANKNIFTY'}, timeout=30)
        if response.status_code == 200:
            analysis = response.json()
            decision = analysis['decision']
            confidence = analysis['confidence']
            print(f'   Analysis result: {decision} ({confidence:.1%})')

            # Check if signals were created after analysis
            response2 = requests.get('http://localhost:8006/api/v1/signals/BANKNIFTY')
            if response2.status_code == 200:
                new_signals = response2.json()
                if len(new_signals) > len(signals):
                    print(f'   ✅ New signals created! Total: {len(new_signals)}')
                else:
                    print(f'   ℹ️  Signal count unchanged: {len(new_signals)}')
        else:
            print(f'   ❌ Analysis failed: {response.status_code}')
    except Exception as e:
        print(f'   ❌ Signal creation test failed: {e}')

if __name__ == "__main__":
    investigate_signals()