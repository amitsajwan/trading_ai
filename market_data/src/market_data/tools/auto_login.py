"""Deprecated helper - replaced by in-package helpers.

This file was left as a convenience shim. Please use the in-package
`market_data.tools.kite_auth` CLI or the in-package service
`market_data.tools.kite_auth_service` instead.
"""

import sys

print("DEPRECATED: use 'python -m market_data.tools.kite_auth' or 'python -m market_data.tools.kite_auth_service'")
sys.exit(0)
