"""Show what agents are actually producing."""
import sys
import json
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.parent))

from core_kernel.mongodb_schema import get_mongo_client, get_collection
from core_kernel.config.settings import settings

client = get_mongo_client()
db = client[settings.mongodb_db_name]
coll = get_collection(db, "agent_decisions")

latest = coll.find_one(sort=[("timestamp", -1)])

if not latest:
    print("No agent analysis found in MongoDB")
    sys.exit(1)

print("=" * 70)
print("LATEST AGENT ANALYSIS")
print("=" * 70)
print(f"Timestamp: {latest.get('timestamp', 'N/A')}")
print(f"Signal: {latest.get('final_signal', 'N/A')}")
print(f"Current Price: {latest.get('current_price', 'N/A')}")
print()

agent_decisions = latest.get("agent_decisions", {})

for agent_name in ['technical', 'fundamental', 'sentiment', 'macro']:
    print(f"{agent_name.upper()} AGENT:")
    agent_data = agent_decisions.get(agent_name, {})
    if isinstance(agent_data, dict):
        # Check if all values are None/empty
        non_empty = {k: v for k, v in agent_data.items() if v is not None and v != "" and v != False}
        if non_empty:
            print(f"  Has {len(non_empty)} non-empty fields:")
            for k, v in list(non_empty.items())[:5]:  # Show first 5
                print(f"    {k}: {v}")
        else:
            print(f"  [EMPTY] All fields are None/empty/False")
            print(f"  Fields: {list(agent_data.keys())}")
    elif isinstance(agent_data, str):
        if agent_data.strip():
            print(f"  {agent_data[:200]}")
        else:
            print(f"  [EMPTY] Empty string")
    else:
        print(f"  {agent_data}")
    print()

print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total agents: {len(agent_decisions)}")
empty_count = 0
for agent_name, agent_data in agent_decisions.items():
    if isinstance(agent_data, dict):
        if all(v is None or v == "" or v == False for v in agent_data.values()):
            empty_count += 1
    elif isinstance(agent_data, str) and not agent_data.strip():
        empty_count += 1

print(f"Empty agents: {empty_count}/{len(agent_decisions)}")
if empty_count > 0:
    print("\n[WARNING] Some agents are producing empty analysis!")
    print("This usually means:")
    print("  1. LLM is not responding properly")
    print("  2. LLM responses are not being parsed correctly")
    print("  3. Prompts need adjustment")
    print("  4. Market data format doesn't match what agents expect")


