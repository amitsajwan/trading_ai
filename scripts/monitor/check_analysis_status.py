"""ARCHIVED: The original check script was archived and the archive folder was later removed (2026-01-03).
The compressed backup for this file was permanently deleted on 2026-01-03 per repository cleanup."""

print("This check script's original content was archived and the compressed backup was permanently deleted on 2026-01-03. Contact maintainers to request restoration.")

def check_recent_analysis():
    """Check MongoDB for recent analysis cycles."""
    print("\n" + "=" * 70)
    print("ANALYSIS STATUS CHECK")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        from core_kernel.mongodb_schema import get_mongo_client, get_collection
        from config.settings import settings
        
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        analysis_collection = get_collection(db, "agent_decisions")
        
        # Get last 5 analyses
        recent_analyses = list(analysis_collection.find(
            sort=[("timestamp", -1)]
        ).limit(5))
        
        if not recent_analyses:
            print("[X] No analysis cycles found in MongoDB")
            print("\nPossible reasons:")
            print("  1. Trading system is not running")
            print("  2. Analysis hasn't completed yet")
            print("  3. MongoDB connection issue")
            print("\nTo start the system:")
            print("  python scripts/start_all.py")
            return False
        
        latest = recent_analyses[0]
        latest_time = latest.get("timestamp")
        
        if isinstance(latest_time, str):
            try:
                latest_time = datetime.fromisoformat(latest_time.replace('Z', '+00:00'))
            except:
                latest_time = datetime.now()
        elif isinstance(latest_time, datetime):
            pass
        else:
            latest_time = datetime.now()
        
        time_diff = datetime.now() - latest_time.replace(tzinfo=None) if latest_time.tzinfo else datetime.now() - latest_time
        
        print(f"[OK] Found {len(recent_analyses)} recent analysis cycle(s)\n")
        print("=" * 70)
        print("LATEST ANALYSIS")
        print("=" * 70)
        print(f"Timestamp: {latest_time}")
        print(f"Time ago: {time_diff.total_seconds():.0f} seconds ({time_diff.total_seconds()/60:.1f} minutes)")
        
        if time_diff.total_seconds() < 120:
            print("[OK] Analysis is recent (< 2 minutes ago)")
        elif time_diff.total_seconds() < 300:
            print("[WARNING] Analysis is > 2 minutes old")
        else:
            print("[X] Analysis is > 5 minutes old - system may not be running!")
        
        # Check agent results
        agent_decisions = latest.get("agent_decisions", {})
        print(f"\nAgents that produced data: {len(agent_decisions)}")
        
        for agent_name, agent_data in agent_decisions.items():
            if isinstance(agent_data, dict):
                non_empty = [k for k, v in agent_data.items() if v is not None and v != ""]
                if non_empty:
                    print(f"  [OK] {agent_name}: {len(non_empty)} fields")
                else:
                    print(f"  [X] {agent_name}: Empty")
            elif agent_data:
                print(f"  [OK] {agent_name}: Has data")
            else:
                print(f"  [X] {agent_name}: Empty")
        
        # Check final signal
        signal = latest.get("final_signal", "UNKNOWN")
        print(f"\nFinal Signal: {signal}")
        
        # Show previous analyses
        if len(recent_analyses) > 1:
            print("\n" + "=" * 70)
            print("RECENT ANALYSIS HISTORY")
            print("=" * 70)
            for i, analysis in enumerate(recent_analyses[1:6], 1):
                prev_time = analysis.get("timestamp")
                if isinstance(prev_time, str):
                    try:
                        prev_time = datetime.fromisoformat(prev_time.replace('Z', '+00:00'))
                    except:
                        prev_time = datetime.now()
                elif not isinstance(prev_time, datetime):
                    prev_time = datetime.now()
                
                time_diff_prev = datetime.now() - prev_time.replace(tzinfo=None) if prev_time.tzinfo else datetime.now() - prev_time
                prev_signal = analysis.get("final_signal", "UNKNOWN")
                print(f"{i}. {prev_time.strftime('%H:%M:%S')} ({time_diff_prev.total_seconds()/60:.1f}m ago) - Signal: {prev_signal}")
        
        # Check if system should be running
        print("\n" + "=" * 70)
        print("SYSTEM STATUS")
        print("=" * 70)
        
        if time_diff.total_seconds() < 120:
            print("[OK] System appears to be running")
            print(f"     Last analysis: {time_diff.total_seconds():.0f} seconds ago")
            print(f"     Expected next: In {60 - (time_diff.total_seconds() % 60):.0f} seconds")
        elif time_diff.total_seconds() < 300:
            print("[WARNING] System may be slow or stuck")
            print(f"     Last analysis: {time_diff.total_seconds()/60:.1f} minutes ago")
            print("     Check logs for errors")
        else:
            print("[X] System does not appear to be running")
            print(f"     Last analysis: {time_diff.total_seconds()/60:.1f} minutes ago")
            print("\nTo start the system:")
            print("  python scripts/start_all.py")
            return False
        
        return True
        
    except Exception as e:
        print(f"[X] Error checking analysis: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_trading_service_running():
    """Check if trading service process is running."""
    print("\n" + "=" * 70)
    print("PROCESS CHECK")
    print("=" * 70)
    
    try:
        import psutil
        
        python_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'python' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'trading_service' in cmdline or 'start_all' in cmdline or 'services/trading_service.py' in cmdline:
                        python_processes.append({
                            'pid': proc.info['pid'],
                            'cmdline': cmdline[:100]
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if python_processes:
            print(f"[OK] Found {len(python_processes)} trading service process(es):")
            for proc in python_processes:
                print(f"  PID {proc['pid']}: {proc['cmdline']}")
            return True
        else:
            print("[X] No trading service process found")
            print("\nThe trading system is not running.")
            print("To start it:")
            print("  python scripts/start_all.py")
            return False
            
    except ImportError:
        print("[SKIP] psutil not installed (pip install psutil)")
        return None
    except Exception as e:
        print(f"[SKIP] Could not check processes: {e}")
        return None

def main():
    """Main check function."""
    # Check MongoDB for recent analyses
    analysis_ok = check_recent_analysis()
    
    # Check if process is running
    process_ok = check_trading_service_running()
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if analysis_ok:
        print("[OK] Analysis cycles are happening")
    else:
        print("[X] No recent analysis cycles found")
    
    if process_ok is True:
        print("[OK] Trading service process is running")
    elif process_ok is False:
        print("[X] Trading service process not found")
    
    if not analysis_ok and process_ok is False:
        print("\n[ACTION REQUIRED]")
        print("The trading system is not running. Start it with:")
        print("  python scripts/start_all.py")
    elif not analysis_ok:
        print("\n[ACTION REQUIRED]")
        print("Process is running but no recent analyses found.")
        print("Check logs for errors or timeouts.")
    else:
        print("\n[OK] System is running and producing analyses!")
    
    print("=" * 70 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCheck interrupted")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nCheck failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


