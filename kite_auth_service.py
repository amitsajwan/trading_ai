#!/usr/bin/env python3
"""DEPRECATED shim: use the in-package `market_data.tools.kite_auth_service`.

This module provides a backward-compatible symbol import so existing code
that does `from kite_auth_service import KiteAuthService` continues to work
without starting the service on import.
"""

from market_data.tools.kite_auth_service import KiteAuthService, main

if __name__ == "__main__":
    print("DEPRECATED: use 'python -m market_data.tools.kite_auth_service'")
    main()
