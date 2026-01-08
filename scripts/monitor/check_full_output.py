"""ARCHIVED: The original check script was archived on 2026-01-03; the compressed backup was permanently deleted on 2026-01-03 per repository cleanup."""

print("This check script's original content was archived and the compressed backup was permanently deleted on 2026-01-03. Contact maintainers to request restoration.")

from core_kernel.mongodb_schema import get_mongo_client, get_collection
from config.settings import settings
import json

client = get_mongo_client()
db = client[settings.mongodb_db_name]
analysis_collection = get_collection(db, "agent_decisions")

latest = analysis_collection.find_one(sort=[("timestamp", -1)])

if latest:
    agents = latest.get("agent_decisions", {})
    
    print("=" * 60)
    print("FULL AGENT OUTPUTS (No Truncation)")
    print("=" * 60)
    print(f"Timestamp: {latest.get('timestamp', 'N/A')}")
    print(f"Signal: {latest.get('final_signal', 'N/A')}")
    print("=" * 60)
    
    for agent_name, agent_data in agents.items():
        print(f"\n{agent_name.upper()}:")
        print(json.dumps(agent_data, indent=2))
        print("-" * 60)
else:
    print("No analysis found")


