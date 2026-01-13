#!/usr/bin/env python3
"""
Test WebSocket connection to the gateway.
"""

import asyncio
import websockets
import json

async def test_websocket():
    """Test WebSocket connection."""
    print('🔌 Testing WebSocket Connection')
    print('=' * 35)

    uri = "ws://localhost:8889/ws"

    try:
        async with websockets.connect(uri) as websocket:
            print('✅ WebSocket connection established successfully!')

            # Send a test message
            test_message = {"type": "test", "message": "Hello from test client"}
            await websocket.send(json.dumps(test_message))
            print(f'📤 Sent: {test_message}')

            # Try to receive a response (timeout after 2 seconds)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print(f'📥 Received: {response}')
            except asyncio.TimeoutError:
                print('⏰ No response received (normal for test)')

            print('✅ WebSocket test completed successfully!')
            return True

    except Exception as e:
        print(f'❌ WebSocket connection failed: {e}')
        return False

if __name__ == "__main__":
    result = asyncio.run(test_websocket())
    if result:
        print('\n🎉 Dashboard should now be able to connect to WebSocket!')
    else:
        print('\n❌ WebSocket still not working')