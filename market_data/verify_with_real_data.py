#!/usr/bin/env python3
"""Quick verification script with real Zerodha historical data.

Usage:
    python market_data/verify_with_real_data.py

This script verifies all our implementations work with real market data.
Run when market is closed to test with historical data.
"""

import sys
import os
from pathlib import Path

# Add project paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "market_data" / "src"))
sys.path.insert(0, str(project_root / "market_data" / "tests"))

if __name__ == "__main__":
    # Import and run the verification script
    from integration.verify_real_data import main
    import asyncio
    
    print("\n" + "="*70)
    print("VERIFICATION WITH REAL ZERODHA HISTORICAL DATA")
    print("="*70)
    print("\nThis script will:")
    print("  1. Connect to Zerodha API")
    print("  2. Fetch real historical OHLC data")
    print("  3. Test Multi-Timeframe Reader")
    print("  4. Test Technical Indicators")
    print("  5. Test Greeks Calculator")
    print("  6. Test Enhanced Options Chain")
    print("  7. Test Multi-Timeframe Indicators")
    print("\n" + "-"*70)
    print("\nPrerequisites:")
    print("  - Redis running (localhost:6379)")
    print("  - Zerodha credentials set (KITE_API_KEY, KITE_ACCESS_TOKEN)")
    print("  - Market closed (using historical data)")
    print("\n" + "-"*70 + "\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Verification interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
