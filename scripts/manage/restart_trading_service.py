"""Stop all TradingService processes and restart cleanly."""

import sys
import subprocess
import time
from pathlib import Path

def stop_trading_service():
    """Stop all TradingService processes."""
    print("Stopping all TradingService processes...")
    try:
        # Find all Python processes running trading_service
        result = subprocess.run(
            ["powershell", "-Command",
             "$procs = Get-Process python -ErrorAction SilentlyContinue | "
             "Where-Object {(Get-WmiObject Win32_Process -Filter \"ProcessId = $($_.Id)\").CommandLine -like '*trading_service*'}; "
             "$procs | ForEach-Object { Stop-Process -Id $_.Id -Force }; "
             "$procs.Count"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            count = result.stdout.strip()
            if count.isdigit() and int(count) > 0:
                print(f"   Stopped {count} TradingService process(es)")
                time.sleep(2)  # Give processes time to stop
                return True
            else:
                print("   No TradingService processes found to stop")
                return False
        else:
            print(f"   Error stopping processes: {result.stderr}")
            return False
    except Exception as e:
        print(f"   Error: {e}")
        return False

def start_trading_service():
    """Start TradingService."""
    print("\nStarting TradingService...")
    try:
        python_path = Path(".venv/Scripts/python.exe")
        if not python_path.exists():
            python_path = Path(sys.executable)
        
        process = subprocess.Popen(
            [str(python_path), "-m", "services.trading_service"],
            cwd=Path(__file__).parent.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"   Started TradingService (PID: {process.pid})")
        print("   Waiting 5 seconds for initialization...")
        time.sleep(5)
        return process
    except Exception as e:
        print(f"   Error starting TradingService: {e}")
        return None

def main():
    print("=" * 70)
    print("TradingService Restart")
    print("=" * 70)
    print()
    
    # Stop existing processes
    stopped = stop_trading_service()
    
    # Start new process
    process = start_trading_service()
    
    if process:
        print()
        print("=" * 70)
        print("SUCCESS: TradingService restarted")
        print("=" * 70)
        print(f"Process ID: {process.pid}")
        print("Check logs for agent activity")
        print("Run 'python scripts/check_agent_status.py' in 60 seconds to verify")
        print("=" * 70)
    else:
        print()
        print("=" * 70)
        print("ERROR: Failed to restart TradingService")
        print("=" * 70)
        print("Try manually: python -m services.trading_service")
        print("=" * 70)

if __name__ == "__main__":
    main()

