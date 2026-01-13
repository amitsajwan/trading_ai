#!/usr/bin/env python3
"""Test orchestrator cycle."""

import requests

def test_orchestrator():
    """Test the orchestrator cycle endpoint."""
    print("🧪 Testing Orchestrator Cycle")
    print("=" * 30)

    try:
        response = requests.post('http://localhost:8006/api/v1/orchestrator/run_cycle', timeout=30)

        if response.status_code == 200:
            result = response.json()
            print("✅ Orchestrator cycle completed!")
            decision = result.get('decision', 'unknown')
            confidence = result.get('confidence', 0)
            agent_signals = result.get('agent_signals', 0)

            print(f"Decision: {decision}")
            print(f"Confidence: {confidence:.1%}")
            print(f"Agent signals: {agent_signals}")

            if decision != 'unknown':
                print("\n🎉 SUCCESS: Orchestrator is working!")
                print("Agent data should now be published to WebSocket")
                print("Dashboard should show agent information")
                return True
            else:
                print("\n⚠️ Decision is unknown - agents may need debugging")
                return False
        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_orchestrator()