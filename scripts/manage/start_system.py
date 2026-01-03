"""Deprecated launcher.

Use canonical entrypoints:
  - scripts/start_btc_trading.py (BTC/crypto)
  - scripts/start_all.py (orchestrator + verification + dashboard)
"""

import sys


def main():
    print("This launcher is deprecated. Use scripts/start_btc_trading.py or scripts/start_all.py.")
    sys.exit(1)


if __name__ == "__main__":
    main()

