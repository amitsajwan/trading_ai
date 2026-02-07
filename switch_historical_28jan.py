#!/usr/bin/env python3
"""
Switch to historical mode for 28 Jan 2026 and verify full market data.
"""

import sys
import subprocess
import os
from datetime import datetime
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent / 'market_data' / 'src'))

def main():
    print("=" * 80)
    print("SWITCHING TO HISTORICAL MODE - 28 JAN 2026")
    print("=" * 80)
    
    # Check if we have Zerodha credentials
    creds_path = Path(__file__).parent / "credentials.json"
    if not creds_path.exists():
        print("[ERROR] credentials.json not found!")
        print("[INFO] Please ensure you have Zerodha credentials configured.")
        return False
    
    print("\n[INFO] Starting system in HISTORICAL mode with Zerodha API...")
    print("[INFO] Date: 28 Jan 2026")
    print("[INFO] Mode: Full market data replay from Zerodha API")
    print("[INFO] Speed: Real-time (1.0x)")
    
    # Start the system with historical mode
    cmd = [
        sys.executable,
        "start_local.py",
        "--provider", "historical",
        "--historical-source", "zerodha",
        "--historical-from", "2026-01-28",
        "--historical-speed", "1.0",
        "--historical-ticks"
    ]
    
    print(f"\n[RUN] Command: {' '.join(cmd)}")
    print("\n[WAIT] Starting all services in historical replay mode...")
    print("=" * 80)
    
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to start: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
