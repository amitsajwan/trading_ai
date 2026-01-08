import os
from typing import Optional

from .zerodha import ZerodhaProvider


def get_provider(name: Optional[str] = None):
    """Return a provider instance based on environment or explicit name.

    Selection order:
    - explicit name if provided
    - TRADING_PROVIDER env var
    - auto-fallback: try ZerodhaProvider from credentials, otherwise None (use historical)
    """
    provider_name = name or os.getenv("TRADING_PROVIDER")

    if provider_name:
        provider_name = provider_name.lower()
        if provider_name in ("zerodha", "kite"):
            zp = ZerodhaProvider.from_credentials_file()
            return zp
        # For other providers, return None to signal missing implementation
        return None

    # Auto: try Zerodha creds first
    zp = ZerodhaProvider.from_credentials_file()
    if zp:
        return zp

    # Default to None - will use historical replay at higher level
    return None
