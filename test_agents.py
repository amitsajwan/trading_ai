#!/usr/bin/env python3
"""Test agent analysis and orchestrator cycles."""

import requests
import time

def test_analysis():
    """Test the analysis endpoint."""
    print("🧪 Testing Agent Analysis")
    print("-" * 30)

    try:
        response = requests.post('http://localhost:8006/api/v1/analyze',
                               json={'instrument': 'BANKNIFTY'},
                               timeout=15)

        if response.status_code == 200:
            data = response.json()
            details = data.get('details', {})
            agg = details.get('aggregated_analysis', {})
            signals = agg.get('technical_signals', [])

            print(f"✅ Analysis successful")
            print(f"   Overall decision: {data.get('decision', 'unknown')}")
            print(f"   Confidence: {data.get('confidence', 0):.1%}")
            print(f"   Agent signals: {len(signals)}")

            if signals:
                print("\n   Sample agents:")
                for i, signal in enumerate(signals[:3]):
                    agent_name = signal['agent'].replace('Agent', '')
                    decision = signal.get('decision', 'unknown')
                    confidence = signal.get('confidence', 0)
                    indicators = signal.get('indicators', {})
                    print(f"     {i+1}. {agent_name}: {decision} ({confidence:.1%}) - {len(indicators)} indicators")

            return True
        else:
            print(f"❌ Analysis failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_orchestrator_cycle():
    """Test the orchestrator cycle endpoint."""
    print("\n🏃 Testing Orchestrator Cycle")
    print("-" * 30)

    try:
        response = requests.post('http://localhost:8006/api/v1/orchestrator/run_cycle',
                               json={'instrument': 'BANKNIFTY'},
                               timeout=20)

        if response.status_code == 200:
            result = response.json()
            print("✅ Orchestrator cycle completed"            print(f"   Decision: {result.get('decision', 'unknown')}")
            print(f"   Confidence: {result.get('confidence', 0):.1%}")
            print(f"   Agent signals processed: {result.get('agent_signals', 0)}")

            if result.get('decision') != 'unknown':
                print("   🎉 This should trigger WebSocket publishing!")
                return True
            else:
                print("   ⚠️ Decision is unknown - agents might not be working")
                return False
        else:
            print(f"❌ Orchestrator failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("🔍 Agent Data Flow Analysis")
    print("=" * 40)

    # Test 1: Agent analysis
    analysis_ok = test_analysis()

    # Test 2: Orchestrator cycle (if analysis works)
    if analysis_ok:
        cycle_ok = test_orchestrator_cycle()

        if cycle_ok:
            print("\n📡 WebSocket Data Flow")
            print("-" * 30)
            print("✅ Analysis → Orchestrator → WebSocket publishing should work")
            print("📊 Dashboard should now show:")
            print("   • Agent Status: 7 agents with decisions & indicators")
            print("   • Orchestrator Decisions: Latest AI decision")
            print("   • Key Insights: Market intelligence")
            print("   • Agent Details: Click any agent for full breakdown")
        else:
            print("\n❌ Issues detected:")
            print("   • Orchestrator cycles not working")
            print("   • Check engine API logs for errors")
    else:
        print("\n❌ Issues detected:")
        print("   • Agent analysis not working")
        print("   • Check if all services are running")

if __name__ == "__main__":
    main()