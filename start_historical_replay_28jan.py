#!/usr/bin/env python3
"""
Quick start for Historical Replay - 28 Jan 2026
Full market data with all services
"""

import subprocess
import sys
import time
from pathlib import Path

def main():
    print("\n" + "=" * 80)
    print("🚀 STARTING HISTORICAL REPLAY - 28 JAN 2026")
    print("=" * 80)
    
    print("\n📋 Configuration:")
    print("   Date: 28 January 2026")
    print("   Instrument: BANKNIFTY26FEBFUT")
    print("   Timeframe: Minute (375 candles)")
    print("   Speed: Real-time (1.0x)")
    print("   Data Source: Zerodha API (continuous=False)")
    print("   Mode: Historical Replay with Virtual Time")
    
    print("\n✅ Prerequisites Check:")
    creds_path = Path("credentials.json")
    if creds_path.exists():
        print("   ✅ Credentials found")
    else:
        print("   ❌ Credentials missing - aborting")
        return False
    
    print("\n🔧 Services that will start:")
    print("   1. Kite Authentication (Zerodha API)")
    print("   2. Historical Data Replayer")
    print("   3. OHLC Aggregator (1-minute candles)")
    print("   4. Multi-Timeframe Aggregator (5m, 15m, 1h, 4h, 1d)")
    print("   5. Technical Indicators Engine (40+ indicators)")
    print("   6. Market Data API (port 8004)")
    print("   7. Dashboard (port 8008)")
    print("   8. Redis Cache")
    
    print("\n📊 Data Pipeline:")
    print("   Zerodha API → Historical Replayer → OHLC Aggregator")
    print("   → Multi-Timeframe Aggregator → Indicators → Dashboard")
    
    print("\n🕐 Timeline Simulation:")
    print("   - Virtual time set to 2026-01-28 09:15:00 IST")
    print("   - Candles replayed at 1.0x speed (real-time)")
    print("   - Takes ~6 hours (9:15 AM to 3:30 PM IST)")
    print("   - Can be accelerated with --historical-speed parameter")
    
    print("\n📈 What You Can Do During Replay:")
    print("   ✓ Watch market data update in real-time dashboard")
    print("   ✓ See technical indicators calculated live")
    print("   ✓ Test trading strategies with actual market conditions")
    print("   ✓ Analyze multi-timeframe patterns")
    print("   ✓ Backtest algorithms")
    print("   ✓ Paper trade without real capital risk")
    
    print("\n🌐 Dashboard Access:")
    print("   After services start (wait ~30 seconds):")
    print("   → Open: http://localhost:8008")
    print("   → Shows: BANKNIFTY price, 40+ indicators, charts")
    
    print("\n📝 Data Statistics for 28 Jan 2026:")
    print("   - Opening: 59,880.00")
    print("   - High: 59,977.00")
    print("   - Low: 59,532.20")
    print("   - Closing: 59,840.00")
    print("   - Total Volume: 947,520 contracts")
    print("   - Avg Volume/min: 2,527 contracts")
    
    print("\n" + "=" * 80)
    input("Press ENTER to start historical replay...")
    print("=" * 80 + "\n")
    
    # Build command
    cmd = [
        sys.executable,
        "start_local.py",
        "--provider", "historical",
        "--historical-source", "zerodha",
        "--historical-from", "2026-01-28",
        "--historical-speed", "1.0",
        "--historical-ticks"
    ]
    
    print(f"[RUN] {' '.join(cmd[2:])}\n")
    
    # Run
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
