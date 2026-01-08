"""Verify system is actually running correctly - ticks and analysis."""

import sys
import os
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.ERROR)

def check_ticks_receiving():
    """Check if ticks are being received RIGHT NOW."""
    print("\n" + "=" * 70)
    print("CHECK 1: Are Ticks Being Received?")
    print("=" * 70)
    
    try:
        import redis
        from config.settings import settings
        
        r = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=False,
            socket_connect_timeout=2
        )
        r.ping()
        
        instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
        latest_price_key = f"price:{instrument_key}:latest"
        latest_ts_key = f"price:{instrument_key}:latest_ts"
        
        # Check latest price
        price = r.get(latest_price_key)
        ts_str = r.get(latest_ts_key)
        
        if not price:
            print("[CRITICAL] [X] No latest price found!")
            print("WebSocket is NOT receiving/storing ticks")
            return False
        
        if not ts_str:
            print("[CRITICAL] [X] No latest timestamp found!")
            return False
        
        # Parse timestamp
        try:
            ts_str_decoded = ts_str.decode() if isinstance(ts_str, bytes) else ts_str
            latest_ts = datetime.fromisoformat(ts_str_decoded.replace('Z', '+00:00'))
            if latest_ts.tzinfo:
                latest_ts = latest_ts.replace(tzinfo=None)
            
            age = (datetime.now() - latest_ts).total_seconds()
            
            print(f"Latest price: ${float(price.decode() if isinstance(price, bytes) else price):,.2f}")
            print(f"Last tick: {age:.1f} seconds ago")
            
            if age < 10:
                print("[OK] [OK] Ticks are being received! (< 10s old)")
                return True
            elif age < 60:
                print("[WARNING] [!] Ticks are slow (> 10s old)")
                return False
            else:
                print(f"[CRITICAL] [X] Ticks are STALE ({age:.0f}s old)")
                print("WebSocket is NOT receiving real-time data")
                return False
        except Exception as e:
            print(f"[ERROR] Could not parse timestamp: {e}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Could not check ticks: {e}")
        return False

def check_analysis_running():
    """Check if analysis is running every minute."""
    print("\n" + "=" * 70)
    print("CHECK 2: Is Analysis Running Every Minute?")
    print("=" * 70)
    
    try:
        from core_kernel.mongodb_schema import get_mongo_client, get_collection
        from config.settings import settings
        
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        analysis_collection = get_collection(db, "agent_decisions")
        
        # Get last 3 analyses
        recent = list(analysis_collection.find(sort=[("timestamp", -1)]).limit(3))
        
        if len(recent) < 2:
            print("[WARNING] Not enough analyses to check timing")
            return False
        
        timestamps = []
        for a in recent:
            ts = a.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except:
                    continue
            elif isinstance(ts, datetime):
                pass
            else:
                continue
            if ts.tzinfo:
                ts = ts.replace(tzinfo=None)
            timestamps.append(ts)
        
        timestamps.sort()
        
        if len(timestamps) < 2:
            print("[ERROR] Could not parse timestamps")
            return False
        
        # Check latest
        latest = timestamps[-1]
        now = datetime.now()
        age = (now - latest).total_seconds()
        
        # Check gap between last 2
        gap = (timestamps[-1] - timestamps[-2]).total_seconds()
        
        print(f"Last analysis: {age/60:.1f} minutes ago")
        print(f"Gap between last 2: {gap:.1f} seconds")
        
        if age < 120 and gap < 90:
            print("[OK] [OK] Analysis is running regularly!")
            if gap > 70:
                print(f"  (Gap is {gap:.1f}s - slightly slow but acceptable)")
            return True
        else:
            print(f"[CRITICAL] [X] Analysis is NOT running every minute")
            print(f"  Last analysis: {age/60:.1f} minutes ago")
            print(f"  Gap: {gap:.1f} seconds (should be ~60s)")
            return False
            
    except Exception as e:
        print(f"[ERROR] Could not check analysis: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_processes():
    """Check for multiple processes."""
    print("\n" + "=" * 70)
    print("CHECK 3: Are Multiple Processes Running?")
    print("=" * 70)
    
    try:
        import psutil
        current_pid = os.getpid()
        
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] == current_pid:
                    continue
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'start_all.py' in cmdline:
                    continue
                if any(x in cmdline for x in ['trading_service', 'services.trading_service']):
                    processes.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if len(processes) == 0:
            print("[OK] [OK] No trading service processes found")
            print("  (System may not be running)")
            return True
        elif len(processes) == 1:
            print(f"[OK] [OK] Only 1 trading service process (PID {processes[0]})")
            return True
        else:
            print(f"[CRITICAL] [X] Found {len(processes)} trading service processes!")
            for pid in processes:
                print(f"  PID {pid}")
            print("\nMultiple processes cause conflicts!")
            return False
            
    except ImportError:
        print("[SKIP] psutil not installed")
        return None
    except Exception as e:
        print(f"[ERROR] Could not check processes: {e}")
        return None

def main():
    """Run all checks."""
    print("\n" + "=" * 70)
    print("SYSTEM VERIFICATION - Are Ticks & Analysis Working?")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    results = {}
    results['ticks'] = check_ticks_receiving()
    results['analysis'] = check_analysis_running()
    results['processes'] = check_processes()
    
    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    if results.get('ticks') and results.get('analysis'):
        print("[SUCCESS] [OK] System is working correctly!")
        print("  - Ticks are being received")
        print("  - Analysis is running every minute")
    else:
        print("[FAILURE] [X] System has issues:")
        if not results.get('ticks'):
            print("  - Ticks are NOT being received")
        if not results.get('analysis'):
            print("  - Analysis is NOT running every minute")
    
    if results.get('processes') is False:
        print("\n[ACTION REQUIRED]")
        print("Stop all processes and restart:")
        print("  taskkill /F /IM python.exe")
        print("  python scripts/start_all.py BTC")
    
    print("=" * 70 + "\n")
    
    return results.get('ticks') and results.get('analysis')

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nVerification interrupted")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nVerification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


