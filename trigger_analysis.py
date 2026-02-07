#!/usr/bin/env python3
import requests
import time
import os

# Get configured instrument
INSTRUMENT = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY26JANFUT")

try:
    print("Triggering orchestrator analysis...")
    response = requests.post("http://localhost:8000/api/engine/analyze", json={"instrument": INSTRUMENT}, timeout=60)
    print(f"Response status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("Analysis completed!")
        print("Full response keys:", list(data.keys()))
        print("Full response:", data)
        print(f"Decision: {data.get('decision', 'N/A')}")
        print(f"Confidence: {data.get('confidence', 'N/A')}")
        if 'details' in data and 'aggregated_analysis' in data['details']:
            agg = data['details']['aggregated_analysis']
            print(f"Consensus direction: {agg.get('consensus_direction', 'N/A')}")
            print(f"Agent breakdown: {agg.get('agent_breakdown', {})}")
            print(f"Weighted votes: {agg.get('weighted_votes', {})}")
        print(f"Details keys: {list(data.get('details', {}).keys()) if 'details' in data else 'No details'}")
        print(f"Detail field: {data.get('detail', 'N/A')}")
        if 'agent_responses' in data:
            print(f"Agent responses: {len(data['agent_responses'])}")
            for agent in data['agent_responses'][:5]:  # Show first 5
                print(f"  {agent['agent']}: {agent['decision']} ({agent['confidence']})")
    else:
        print(f"Error: {response.text}")

except Exception as e:
    print(f"Error triggering analysis: {e}")