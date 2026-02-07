#!/usr/bin/env python3
"""
Debug agent data publication issues.
"""

import requests
import json
import asyncio
import websockets
import time

def debug_agent_data():
    """Debug why agent data isn't showing in dashboard."""
    print('🔍 Debugging Agent Data Publication')
    print('=' * 40)

    # Check if agents are running and what they return
    print('1. Testing agent analysis directly...')
    try:
        response = requests.post('http://localhost:8006/api/v1/analyze', json={'instrument': 'BANKNIFTY'}, timeout=30)
        if response.status_code == 200:
            data = response.json()
            details = data['details']
            agg = details['aggregated_analysis']

            print('   ✅ Analysis successful')
            print(f'   Overall decision: {data["decision"]} ({data["confidence"]:.1%})')

            # Check if technical signals exist
            tech_signals = agg.get('technical_signals', [])
            print(f'   Technical signals: {len(tech_signals)}')

            if tech_signals:
                # Check what data each agent has
                for signal in tech_signals[:2]:  # Show first 2
                    agent_name = signal['agent'].replace('Agent', '')
                    indicators = signal.get('indicators', {})
                    print(f'     {agent_name}: {len(indicators)} indicators, confidence: {signal["confidence"]:.1%}')

        else:
            print(f'   ❌ Analysis failed: {response.status_code}')
            print(f'   Response: {response.text}')
    except Exception as e:
        print(f'   ❌ Analysis request failed: {e}')

    print('\n2. Checking WebSocket connection...')

    async def test_ws_subscription():
        uri = 'ws://localhost:8889/ws'
        try:
            async with websockets.connect(uri) as websocket:
                # Subscribe to agent channels
                subscribe_msg = {
                    'type': 'subscribe',
                    'channels': ['engine:agent', 'engine:agent:*', 'engine:decision']
                }
                await websocket.send(json.dumps(subscribe_msg))

                print('   ✅ Subscribed to agent channels')

                # Wait a moment for any messages
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    data = json.loads(msg)
                    if 'type' in data:
                        print(f'   📥 Received: {data["type"]} message')
                        if data.get('type') == 'agent_analysis':
                            print(f'      Agent: {data.get("agent_name")}, Decision: {data.get("decision")}')
                        elif data.get('type') == 'orchestrator_decision':
                            print(f'      Orchestrator: {data.get("final_decision")}, Agents: {len(data.get("agent_responses", []))}')
                    else:
                        print(f'   📥 Received: {msg[:100]}...')
                except asyncio.TimeoutError:
                    print('   ⏱️  No messages received (normal if no new analysis)')

        except Exception as e:
            print(f'   ❌ WebSocket test failed: {e}')

    # Run WebSocket test
    try:
        asyncio.run(test_ws_subscription())
    except Exception as e:
        print(f'   ❌ Asyncio run failed: {e}')

    print('\n3. Checking Redis for stored data...')
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

        # Check for agent keys
        agent_keys = r.keys('engine:agent*')
        print(f'   Redis agent keys: {len(agent_keys)}')

        # Check for decision keys
        decision_keys = r.keys('engine:decision*')
        print(f'   Redis decision keys: {len(decision_keys)}')

        # Sample recent agent data
        if agent_keys:
            for key in agent_keys[:2]:  # Show first 2
                data = r.get(key)
                if data:
                    try:
                        parsed = json.loads(data)
                        agent_name = parsed.get('agent_name', 'unknown')
                        decision = parsed.get('decision', 'unknown')
                        confidence = parsed.get('confidence', 0)
                        print(f'     {key}: {agent_name} -> {decision} ({confidence:.1%})')
                    except:
                        print(f'     {key}: {data[:50]}...')

    except Exception as e:
        print(f'   ❌ Redis check failed: {e}')

if __name__ == "__main__":
    debug_agent_data()