"""Test dashboard startup independently."""

import subprocess
import sys
import time
import socket
from pathlib import Path

def test_dashboard():
    """Test if dashboard can start and is accessible."""
    print("=" * 70)
    print("Testing Dashboard Startup")
    print("=" * 70)
    
    python_path = sys.executable
    
    print("\n1. Starting dashboard with uvicorn...")
    proc = subprocess.Popen(
        [python_path, "-m", "uvicorn", "monitoring.dashboard:app", "--host", "127.0.0.1", "--port", "8888"],
        cwd=str(Path(__file__).parent.parent)
    )
    
    print(f"   Process PID: {proc.pid}")
    print("   Waiting 5 seconds for startup...")
    time.sleep(5)
    
    print("\n2. Checking if process is running...")
    if proc.poll() is None:
        print("   SUCCESS: Process is running")
    else:
        print(f"   ERROR: Process exited with code {proc.returncode}")
        proc.terminate()
        return False
    
    print("\n3. Checking if port 8888 is listening...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', 8888))
        sock.close()
        
        if result == 0:
            print("   SUCCESS: Port 8888 is accessible")
            print("\n" + "=" * 70)
            print("Dashboard is running!")
            print("Access at: http://localhost:8888")
            print("=" * 70)
            print("\nPress Enter to stop dashboard...")
            input()
            proc.terminate()
            return True
        else:
            print(f"   ERROR: Port 8888 not accessible (result: {result})")
            proc.terminate()
            return False
    except Exception as e:
        print(f"   ERROR: {e}")
        proc.terminate()
        return False

if __name__ == "__main__":
    test_dashboard()

