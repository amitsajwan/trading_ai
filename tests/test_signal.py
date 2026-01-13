#!/usr/bin/env python3
"""
Test script to publish mock signals to Redis for WebSocket testing
"""

import redis
import json
from datetime import datetime

def main():
    # Connect to Redis
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

    # Test Redis connection
    try:
        redis_client.ping()
        print("[OK] Redis connection successful")
    except Exception as e:
        print(f"[ERROR] Redis connection failed: {e}")
        return

    # Create mock signal data (matching the backend format)
    mock_signal = {
        'signal_id': 'test-signal-001',
        'condition_id': 'test-condition-001',
        'instrument': 'BANKNIFTY',
        'action': 'IRON_CONDOR',
        'confidence': 0.85,
        'timestamp': datetime.now().isoformat(),
        'created_at': datetime.now().isoformat(),
        'status': 'pending',
        'reasoning': 'Mock signal for testing WebSocket flow',
        'operator': '>',
        'threshold': 59500.0,
        'strategy_type': 'options',
        'position_size': 1000,
        'stop_loss': 59000.0,
        'take_profit': 60500.0,
        'additional_conditions': {},
        'expires_at': None,
        'triggered_at': None,
        'is_active': True,
        'created_from': 'test_script',
        'metadata': {
            'signal_source': 'websocket_test',
            'options_strategy_summary': {
                'available': True,
                'strategy_type': 'iron_condor',
                'legs_count': 4,
                'max_loss': 5000,
                'max_profit': 3000,
                'expiry': '2026-01-15',
                'confidence': 0.85,
                'underlying': 'BANKNIFTY',
                'timestamp': datetime.now().isoformat(),
                'legs': [
                    {'strike_price': 59500, 'option_type': 'CE', 'position': 'BUY', 'quantity': 100, 'premium': 150},
                    {'strike_price': 60000, 'option_type': 'CE', 'position': 'SELL', 'quantity': 100, 'premium': 50},
                    {'strike_price': 59000, 'option_type': 'PE', 'position': 'BUY', 'quantity': 100, 'premium': 140},
                    {'strike_price': 58500, 'option_type': 'PE', 'position': 'SELL', 'quantity': 100, 'premium': 45}
                ],
                'risk_analysis': {
                    'max_profit': 3000,
                    'max_loss': 5000,
                    'breakeven_points': [59140, 59860],
                    'risk_reward_ratio': 0.6,
                    'margin_required': 25000
                },
                'agent': 'TestAgent',
                'reasoning': 'Test options strategy for WebSocket testing'
            }
        }
    }

    print('[TEST] Publishing mock signal to Redis...')
    print(f'Signal data: {json.dumps(mock_signal, indent=2)}')

    # Publish to Redis channels (same as backend does)
    try:
        result1 = redis_client.publish('engine:signal', json.dumps(mock_signal))
        result2 = redis_client.publish('engine:signal:BANKNIFTY', json.dumps(mock_signal))

        print(f'[OK] Published to engine:signal: {result1} subscribers')
        print(f'[OK] Published to engine:signal:BANKNIFTY: {result2} subscribers')
        print('[SUCCESS] Mock signal sent! Check browser console for WebSocket reception.')
    except Exception as e:
        print(f'[ERROR] Failed to publish signal: {e}')

if __name__ == '__main__':
    main()