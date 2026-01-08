"""Check what processes are ACTUALLY running."""

import psutil
import sys

def find_trading_processes():
    """Find all processes related to trading service."""
    processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            
            # Skip this script
            if 'check_real_processes.py' in cmdline:
                continue
            
            # Look for trading service
            if any(x in cmdline for x in ['trading_service', 'services.trading_service']):
                processes.append({
                    'pid': proc.info['pid'],
                    'cmdline': cmdline[:100],  # Truncate
                    'create_time': proc.info['create_time']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return processes

def main():
    print("\n" + "=" * 70)
    print("ACTUAL PROCESSES RUNNING")
    print("=" * 70)
    
    processes = find_trading_processes()
    
    if not processes:
        print("[OK] No trading service processes found")
        print("System is NOT running")
    else:
        print(f"[INFO] Found {len(processes)} process(es):\n")
        for i, proc in enumerate(processes, 1):
            print(f"Process {i}:")
            print(f"  PID: {proc['pid']}")
            print(f"  CMD: {proc['cmdline']}")
            print(f"  Started: {proc['create_time']}")
            print()
        
        if len(processes) > 1:
            print("[WARNING] Multiple processes detected!")
            print("This can cause conflicts.")
            print("\nTo stop all:")
            pids = [str(p['pid']) for p in processes]
            print(f"  taskkill /F /PID {' /PID '.join(pids)}")
        else:
            print("[OK] Only 1 process - good!")
    
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()


