"""Check TradingService status and diagnose issues."""

import sys
import subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings
from datetime import datetime
import time

def check_processes():
    """Check if TradingService processes are running."""
    try:
        result = subprocess.run(
            ["powershell", "-Command", 
             "Get-Process python -ErrorAction SilentlyContinue | "
             "Where-Object {$_.CommandLine -like '*trading_service*'} | "
             "Select-Object Id, StartTime, @{Name='CommandLine';Expression={(Get-WmiObject Win32_Process -Filter \"ProcessId = $($_.Id)\").CommandLine}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            print("TradingService processes found:")
            print(result.stdout)
            return True
        else:
            print("No TradingService processes found")
            return False
    except Exception as e:
        print(f"Error checking processes: {e}")
        return False

def check_analysis_age():
    """Check how old the latest analysis is."""
    try:
        client = get_mongo_client()
        db = client[settings.mongodb_db_name]
        collection = get_collection(db, "agent_decisions")
        
        latest = collection.find_one({}, sort=[("timestamp", -1)])
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
                return age_seconds, timestamp_str
            except Exception as e:
                return None, timestamp_str
        return None, None
    except Exception as e:
        print(f"Error checking analysis: {e}")
        return None, None

def main():
    print("=" * 70)
    print("TradingService Diagnostic")
    print("=" * 70)
    print()
    
    # Check processes
    print("1. Checking TradingService processes...")
    has_processes = check_processes()
    print()
    
    # Check analysis age
    print("2. Checking latest analysis...")
    age_seconds, timestamp_str = check_analysis_age()
    if age_seconds is not None:
        age_minutes = int(age_seconds / 60)
        age_secs = int(age_seconds % 60)
        print(f"   Latest analysis: {timestamp_str}")
        print(f"   Age: {age_minutes} minutes {age_secs} seconds ago")
        
        if age_seconds > 120:
            print("\n   WARNING: Analysis is more than 2 minutes old!")
            print("   TradingService may be stuck or crashed.")
        elif age_seconds > 90:
            print("\n   WARNING: Analysis is more than 90 seconds old.")
            print("   Agents should run every 60 seconds.")
    else:
        print("   ❌ No analysis found!")
    print()
    
    # Diagnosis
    print("3. Diagnosis:")
    if has_processes and age_seconds and age_seconds > 120:
        print("   WARNING: TradingService processes are running but not producing new analysis.")
        print("   Possible causes:")
        print("   - Multiple instances causing conflicts")
        print("   - LLM calls hanging/timing out")
        print("   - Exception in trading loop not being caught")
        print()
        print("   Recommendation:")
        print("   1. Stop all TradingService processes")
        print("   2. Check logs for errors")
        print("   3. Restart with: python -m services.trading_service")
    elif not has_processes:
        print("   ERROR: TradingService is not running!")
        print("   Start it with: python -m services.trading_service")
    elif age_seconds and age_seconds < 90:
        print("   ✅ TradingService appears to be working correctly")
    print()
    print("=" * 70)

if __name__ == "__main__":
    main()

