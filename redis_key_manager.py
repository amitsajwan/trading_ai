#!/usr/bin/env python3
"""
Redis Key Manager - Provides mode-based key isolation for LIVE vs HISTORICAL data.

This module ensures that LIVE and HISTORICAL trading modes never mix data by prefixing
all Redis keys with the execution mode.

Usage:
    from redis_key_manager import get_redis_key, get_execution_mode
    
    # Automatically uses EXECUTION_MODE env var
    key = get_redis_key("ohlc_sorted:BANKNIFTY:1min")
    # Returns: "live:ohlc_sorted:BANKNIFTY:1min" or "historical:ohlc_sorted:BANKNIFTY:1min"
    
    # Override mode
    key = get_redis_key("ohlc_sorted:BANKNIFTY:1min", mode="historical")
"""

import os
from typing import Optional

# Valid execution modes
VALID_MODES = {"live", "historical"}
DEFAULT_MODE = "live"


def get_execution_mode() -> str:
    """
    Get current execution mode from environment variable.
    
    Returns:
        str: "live" or "historical" (lowercase)
    """
    mode = os.getenv("EXECUTION_MODE", DEFAULT_MODE).lower()
    
    if mode not in VALID_MODES:
        print(f"⚠️  Invalid EXECUTION_MODE='{mode}', defaulting to '{DEFAULT_MODE}'")
        mode = DEFAULT_MODE
    
    return mode


def get_redis_key(base_key: str, mode: Optional[str] = None) -> str:
    """
    Get mode-prefixed Redis key for data isolation.
    
    Args:
        base_key: The base Redis key without mode prefix
                  Example: "ohlc_sorted:BANKNIFTY:1min"
        mode: Optional mode override ("live" or "historical")
              If None, uses EXECUTION_MODE environment variable
    
    Returns:
        str: Mode-prefixed key
             Example: "live:ohlc_sorted:BANKNIFTY:1min"
    
    Examples:
        >>> os.environ["EXECUTION_MODE"] = "live"
        >>> get_redis_key("ohlc_sorted:BNF:1min")
        'live:ohlc_sorted:BNF:1min'
        
        >>> get_redis_key("enhanced_ticks:BNF", mode="historical")
        'historical:enhanced_ticks:BNF'
    """
    if mode is None:
        mode = get_execution_mode()
    else:
        mode = mode.lower()
        if mode not in VALID_MODES:
            raise ValueError(f"Invalid mode: {mode}. Must be one of {VALID_MODES}")
    
    # Don't double-prefix if already prefixed
    if base_key.startswith(f"{mode}:"):
        return base_key
    
    return f"{mode}:{base_key}"


def get_redis_pattern(base_pattern: str, mode: Optional[str] = None) -> str:
    """
    Get mode-prefixed Redis key pattern for searching.
    
    Args:
        base_pattern: Redis key pattern (can include *)
                      Example: "ohlc_sorted:*:1min"
        mode: Optional mode override
    
    Returns:
        str: Mode-prefixed pattern
             Example: "live:ohlc_sorted:*:1min"
    """
    return get_redis_key(base_pattern, mode=mode)


def strip_mode_prefix(key: str) -> tuple[str, str]:
    """
    Strip mode prefix from Redis key.
    
    Args:
        key: Redis key with or without mode prefix
    
    Returns:
        tuple: (mode, base_key)
               Example: ("live", "ohlc_sorted:BNF:1min")
               If no prefix: (current_mode, original_key)
    """
    for mode in VALID_MODES:
        prefix = f"{mode}:"
        if key.startswith(prefix):
            return mode, key[len(prefix):]
    
    # No prefix found, return current mode and original key
    return get_execution_mode(), key


def clear_mode_data(redis_client, mode: str) -> int:
    """
    Clear all Redis keys for a specific mode.
    
    Args:
        redis_client: Redis client instance
        mode: "live" or "historical"
    
    Returns:
        int: Number of keys deleted
    """
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode: {mode}. Must be one of {VALID_MODES}")
    
    pattern = f"{mode}:*"
    keys = redis_client.keys(pattern)
    
    if keys:
        count = redis_client.delete(*keys)
        print(f"✓ Cleared {count} Redis keys for {mode.upper()} mode")
        return count
    else:
        print(f"✓ No {mode.upper()} mode keys to clear")
        return 0


# MongoDB collection name helpers
def get_mongo_collection(base_name: str, mode: Optional[str] = None) -> str:
    """
    Get mode-prefixed MongoDB collection name.
    
    Args:
        base_name: Base collection name (e.g., "signals", "trades")
        mode: Optional mode override
    
    Returns:
        str: Mode-prefixed collection name
             Example: "live_signals" or "historical_signals"
    """
    if mode is None:
        mode = get_execution_mode()
    else:
        mode = mode.lower()
        if mode not in VALID_MODES:
            raise ValueError(f"Invalid mode: {mode}")
    
    # Don't double-prefix
    if base_name.startswith(f"{mode}_"):
        return base_name
    
    return f"{mode}_{base_name}"


if __name__ == "__main__":
    # Test examples
    import sys
    
    print("Redis Key Manager - Test Examples\n")
    
    # Test with LIVE mode
    os.environ["EXECUTION_MODE"] = "live"
    print(f"EXECUTION_MODE = {os.getenv('EXECUTION_MODE')}")
    print(f"get_redis_key('ohlc_sorted:BNF:1min') = {get_redis_key('ohlc_sorted:BNF:1min')}")
    print(f"get_redis_pattern('ohlc_sorted:*:1min') = {get_redis_pattern('ohlc_sorted:*:1min')}")
    print(f"get_mongo_collection('signals') = {get_mongo_collection('signals')}")
    
    print()
    
    # Test with HISTORICAL mode override
    print("Override with mode='historical':")
    print(f"get_redis_key('ohlc_sorted:BNF:1min', mode='historical') = {get_redis_key('ohlc_sorted:BNF:1min', mode='historical')}")
    print(f"get_mongo_collection('trades', mode='historical') = {get_mongo_collection('trades', mode='historical')}")
    
    print()
    
    # Test strip prefix
    key_with_prefix = "live:ohlc_sorted:BNF:1min"
    mode, base = strip_mode_prefix(key_with_prefix)
    print(f"strip_mode_prefix('{key_with_prefix}') = ('{mode}', '{base}')")
