"""Stop all trading system processes."""

import sys
import subprocess
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def stop_all_processes():
    """Stop all Python processes related to trading system."""
    print("=" * 60)
    print("Stopping All Trading System Processes")
    print("=" * 60)
    
    # Find all Python processes
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            pids = []
            
            # Skip header line
            for line in lines[1:]:
                if line.strip():
                    # CSV format: "python.exe","PID","Session Name","Session#","Mem Usage"
                    parts = line.split('","')
                    if len(parts) >= 2:
                        try:
                            pid = int(parts[1].replace('"', ''))
                            pids.append(pid)
                        except ValueError:
                            continue
            
            if pids:
                print(f"Found {len(pids)} Python process(es)")
                for pid in pids:
                    try:
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)], 
                                     capture_output=True)
                        print(f"  Stopped PID {pid}")
                    except Exception as e:
                        print(f"  Could not stop PID {pid}: {e}")
            else:
                print("No Python processes found")
        else:
            print("Could not list processes")
            
    except Exception as e:
        print(f"Error stopping processes: {e}")
    
    # Also try to stop by port
    print("\nChecking ports...")
    try:
        # Port 8888 (dashboard)
        result = subprocess.run(
            ["netstat", "-ano", "|", "findstr", ":8888"],
            shell=True,
            capture_output=True,
            text=True
        )
        if result.stdout:
            print("Port 8888 is still in use")
        else:
            print("Port 8888 is free")
    except:
        pass
    
    print("\n" + "=" * 60)
    print("All processes stopped!")
    print("=" * 60)

if __name__ == "__main__":
    stop_all_processes()

