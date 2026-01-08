"""Check agent status after fixes."""

import requests
import json

try:
    r = requests.get('http://localhost:8888/api/latest-analysis', timeout=5)
    analysis = r.json()
    
    print("=" * 60)
    print("LATEST AGENT ANALYSIS (After Fixes)")
    print("=" * 60)
    print(f"Agents: {len(analysis.get('agents', {}))}")
    print(f"Signal: {analysis.get('final_signal', 'N/A')}")
    timestamp = analysis.get('timestamp', 'N/A')
    if timestamp != 'N/A':
        timestamp = timestamp[:19]
    print(f"Timestamp: {timestamp}")
    
    agents = analysis.get('agents', {})
    print("\nAgent Status:")
    
    for name in ['technical', 'fundamental', 'sentiment', 'macro', 'bull', 'bear', 
                 'aggressive_risk', 'conservative_risk', 'neutral_risk']:
        if name in agents:
            agent_data = agents[name]
            if isinstance(agent_data, dict):
                has_error = 'error' in str(agent_data).lower()
                status = "ERROR" if has_error else "OK"
            else:
                status = "OK"
            print(f"  {name:20s}: {status}")
        else:
            print(f"  {name:20s}: NOT FOUND")
    
    print("=" * 60)
    
except Exception as e:
    print(f"Error: {e}")


