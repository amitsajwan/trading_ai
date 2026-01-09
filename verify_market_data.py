#!/usr/bin/env python3
"""Market Data Verification CLI."""

import asyncio
import sys

# ui_shell package is now part of `dashboard/ui` and re-exported at top-level for compatibility
# No longer need to modify sys.path here
from ui_shell.market_data_verifier import MarketDataVerifier


async def main():
    """Run market data verification."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python verify_market_data.py verify    # Verify all APIs")
        print("  python verify_market_data.py raw [instrument]  # Show raw API data")
        return

    command = sys.argv[1]

    verifier = MarketDataVerifier()

    try:
        if command == "verify":
            results = await verifier.verify_all_apis()
            print(f"\nVerification complete: {results['summary']}")

        elif command == "raw":
            instrument = sys.argv[2] if len(sys.argv) > 2 else "BANKNIFTY"
            await verifier.show_raw_data(instrument)

        else:
            print(f"Unknown command: {command}")

    finally:
        await verifier.close()


if __name__ == "__main__":
    asyncio.run(main())