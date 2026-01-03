"""Kill all trading processes and restart cleanly."""

import sys
import os
import subprocess
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psutil

def kill_all_trading_processes():
    """Kill all trading service processes."""
    print("\n" + "=" * 70)
    print("STOPPING ALL TRADING PROCESSES")
    print("=" * 70)
    
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'check_real_processes.py' in cmdline or 'kill_all_and_restart.py' in cmdline:
                continue
            if any(x in cmdline for x in ['trading_service', 'services.trading_service']):
                processes.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if not processes:
        print("[OK] No trading processes found")
        return True
    
    print(f"[INFO] Found {len(processes)} process(es) to kill:")
    for pid in processes:
        print(f"  PID {pid}")
    
    print("\nKilling processes...")
    killed = []
    for pid in processes:
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            killed.append(pid)
            print(f"  [OK] Sent terminate to PID {pid}")
        except psutil.NoSuchProcess:
            print(f"  [INFO] PID {pid} already dead")
        except Exception as e:
            print(f"  [ERROR] Could not kill PID {pid}: {e}")
    
    # Wait a bit
    time.sleep(2)
    
    # Force kill if still running
    for pid in killed:
        try:
            proc = psutil.Process(pid)
            if proc.is_running():
                proc.kill()
                print(f"  [OK] Force killed PID {pid}")
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            print(f"  [ERROR] Could not force kill PID {pid}: {e}")
    
    # Verify
    time.sleep(1)
    remaining = []
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if any(x in cmdline for x in ['trading_service', 'services.trading_service']):
                remaining.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if remaining:
        print(f"\n[WARNING] {len(remaining)} process(es) still running: {remaining}")
        return False
    else:
        print("\n[OK] All processes stopped")
        return True

def main():
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    success = kill_all_trading_processes()
    
    if success:
        print("\n" + "=" * 70)
        print("READY TO RESTART")
        print("=" * 70)
        print("\nNow run:")
        print("  python scripts/start_all.py BTC")
        print("\nThen wait 30 seconds and verify:")
        print("  python scripts/check_websocket_status.py")
        print("=" * 70 + "\n")
    else:
        print("\n" + "=" * 70)
        print("SOME PROCESSES STILL RUNNING")
        print("=" * 70)
        print("\nTry manually:")
        print("  taskkill /F /FI \"IMAGENAME eq python.exe\"")
        print("=" * 70 + "\n")

if __name__ == "__main__":
    main()

