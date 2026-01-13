#!/usr/bin/env python3
"""
Test enhanced backend functionality.
"""

import requests
import json

def test_enhanced_backend():
    """Test enhanced backend functionality."""
    print('🧪 Testing Enhanced Dashboard Backend Integration')
    print('=' * 55)

    # Trigger analysis to generate rich agent data
    print('1. Running comprehensive analysis...')
    response = requests.post('http://localhost:8006/api/v1/analyze', json={'instrument': 'BANKNIFTY'}, timeout=30)
    if response.status_code == 200:
        data = response.json()
        print('   ✅ Analysis completed')

        # Check if orchestrator decisions are being created
        print('\n2. Checking orchestrator decisions...')
        response2 = requests.get('http://localhost:8006/api/v1/decisions')
        if response2.status_code == 200:
            decisions = response2.json()
            print(f'   Found {len(decisions)} orchestrator decisions')
            if decisions:
                latest = decisions[0]
                confidence = latest.get('confidence', 0)
                decision = latest.get('final_decision', 'unknown')
                print(f'   Latest: {decision} ({confidence:.1%})')
        else:
            print('   ❌ Could not fetch decisions')

        # Check agent statuses
        print('\n3. Checking agent statuses...')
        response3 = requests.get('http://localhost:8006/api/v1/agents/status')
        if response3.status_code == 200:
            agents = response3.json()
            print(f'   Found {len(agents)} agent statuses')
            if agents:
                sample = agents[0]
                print(f'   Sample agent: {sample.get("name", "unknown")} ({sample.get("status", "unknown")})')
        else:
            print('   ❌ Could not fetch agent statuses')

    else:
        print(f'   ❌ Analysis failed: {response.status_code}')

    print('\n✅ Backend enhancement test completed')

if __name__ == "__main__":
    test_enhanced_backend()