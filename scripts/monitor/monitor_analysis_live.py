"""Live monitoring of analysis cycles - shows updates in real-time."""

import sys
import os
import time
from pathlib import Path
from datetime import datetime, timedelta

# Fix Windows encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.ERROR)

def format_time_ago(seconds):
    """Format seconds as human-readable time ago."""
    if seconds < 60:
        return f"{int(seconds)}s ago"
    elif seconds < 3600:
        return f"{int(seconds/60)}m {int(seconds%60)}s ago"
    else:
        return f"{int(seconds/3600)}h {int((seconds%3600)/60)}m ago"

def get_latest_analysis():
    """Get the latest analysis from MongoDB."""
    try:
        from mongodb_schema import get_mongo_client, get_collection
        from config.settings import settings
        
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        analysis_collection = get_collection(db, "agent_decisions")
        
        latest = analysis_collection.find_one(sort=[("timestamp", -1)])
        return latest
    except Exception as e:
        return None

def display_analysis(latest, prev_timestamp=None):
    """Display analysis information."""
    if not latest:
        print("[X] No analysis found")
        return None
    
    timestamp = latest.get("timestamp")
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except:
            timestamp = datetime.now()
    elif not isinstance(timestamp, datetime):
        timestamp = datetime.now()
    
    # Remove timezone for comparison
    if timestamp.tzinfo:
        timestamp = timestamp.replace(tzinfo=None)
    
    now = datetime.now()
    time_diff = (now - timestamp).total_seconds()
    
    # Check if this is a new analysis
    is_new = prev_timestamp is None or timestamp != prev_timestamp
    
    if is_new:
        print("\n" + "=" * 70)
        print(f"NEW ANALYSIS DETECTED - {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
    else:
        # Just update the status line
        sys.stdout.write(f"\r[WAITING] Last analysis: {format_time_ago(time_diff)} | Next expected: In {max(0, 60 - (time_diff % 60)):.0f}s")
        sys.stdout.flush()
        return timestamp
    
    # Show analysis details
    signal = latest.get("final_signal", "UNKNOWN")
    agent_decisions = latest.get("agent_decisions", {})
    
    agents_with_data = [name for name, data in agent_decisions.items() 
                       if data and isinstance(data, dict) and any(data.values())]
    
    print(f"Signal: {signal}")
    print(f"Agents: {len(agents_with_data)}/{len(agent_decisions)} produced data")
    print(f"Time ago: {format_time_ago(time_diff)}")
    
    # Show key agent outputs
    if "portfolio_manager" in agent_decisions:
        pm_data = agent_decisions["portfolio_manager"]
        if isinstance(pm_data, dict):
            bullish = pm_data.get("bullish_score", "N/A")
            bearish = pm_data.get("bearish_score", "N/A")
            print(f"Bullish Score: {bullish} | Bearish Score: {bearish}")
    
    if "technical" in agent_decisions:
        tech_data = agent_decisions["technical"]
        if isinstance(tech_data, dict):
            trend = tech_data.get("trend_direction", "N/A")
            rsi = tech_data.get("rsi", "N/A")
            print(f"Technical: Trend={trend}, RSI={rsi}")
    
    print("=" * 70)
    
    return timestamp

def main():
    """Main monitoring loop."""
    print("\n" + "=" * 70)
    print("LIVE ANALYSIS MONITOR")
    print("=" * 70)
    print("Monitoring analysis cycles every 5 seconds...")
    print("Press Ctrl+C to stop")
    print("=" * 70)
    
    prev_timestamp = None
    last_check_time = time.time()
    
    try:
        while True:
            # Check for new analysis
            latest = get_latest_analysis()
            
            if latest:
                new_timestamp = display_analysis(latest, prev_timestamp)
                
                if new_timestamp != prev_timestamp:
                    prev_timestamp = new_timestamp
                    last_check_time = time.time()
            else:
                print("\n[X] No analysis found in MongoDB")
                print("Make sure the trading system is running:")
                print("  python scripts/start_all.py")
                break
            
            # Wait 5 seconds before next check
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n[STOPPED] Monitoring stopped by user")
    except Exception as e:
        print(f"\n\n[ERROR] Monitoring failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

