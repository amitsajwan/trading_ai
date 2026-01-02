"""Quick script to check if agents are running and when last analysis occurred."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings
from datetime import datetime

def main():
    try:
        client = get_mongo_client()
        db = client[settings.mongodb_db_name]
        collection = get_collection(db, "agent_decisions")
        
        latest = collection.find_one({}, sort=[("timestamp", -1)])
        total = collection.count_documents({})
        
        print("=" * 60)
        print("Agent Analysis Status")
        print("=" * 60)
        print(f"Total analyses in database: {total}")
        
        if latest:
            timestamp_str = latest.get("timestamp", "Unknown")
            try:
                if isinstance(timestamp_str, str):
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    timestamp = timestamp_str
                
                now = datetime.now()
                if timestamp.tzinfo:
                    now = datetime.now(timestamp.tzinfo)
                
                age_seconds = (now - timestamp).total_seconds()
                age_minutes = int(age_seconds / 60)
                age_secs = int(age_seconds % 60)
                
                print(f"Latest analysis: {timestamp_str}")
                print(f"Age: {age_minutes} minutes {age_secs} seconds ago")
                
                if age_seconds > 120:
                    print("\n⚠️  WARNING: Last analysis is more than 2 minutes old!")
                    print("   TradingService may not be running.")
                    print("   Start it with: python -m services.trading_service")
                elif age_seconds > 90:
                    print("\n⚠️  WARNING: Last analysis is more than 90 seconds old.")
                    print("   Agents should run every 60 seconds.")
                    print("   Check if TradingService is running.")
                else:
                    print("\n✅ Agents appear to be running (analysis is recent)")
            except Exception as e:
                print(f"Latest analysis timestamp: {timestamp_str}")
                print(f"Error parsing timestamp: {e}")
        else:
            print("\n❌ No analysis found in database!")
            print("   TradingService is not running or agents haven't completed a cycle yet.")
            print("   Start it with: python -m services.trading_service")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"Error checking status: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

