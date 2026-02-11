"""Redis key management utilities.

Provides consistent Redis key naming across the system.

Key rule (mode isolation): ALL Redis keys must be prefixed with execution mode:

  live:<key>
  historical:<key>
  paper:<key>

This prevents cross-contamination between LIVE and HISTORICAL runs.
"""
import os
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Optional


_KNOWN_MODE_PREFIXES = ("live:", "historical:", "paper:")


def _normalize_mode(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    val = str(raw).strip().lower()
    # Common aliases
    if val in {"prod", "production"}:
        return "live"
    if val in {"hist", "replay", "backtest"}:
        return "historical"
    if val in {"paper", "paper_trading", "sim", "simulation"}:
        return "paper"
    if val in {"live", "historical", "paper"}:
        return val
    return None


def _market_is_open_ist(now_ist: Optional[datetime] = None) -> bool:
    """Best-effort NSE cash market hours check in IST.

    Notes:
    - Ignores holidays.
    - Uses 09:15 to 15:30 IST.
    """
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = now_ist or datetime.now(ist)

    # Mon-Fri
    if now_ist.weekday() >= 5:
        return False

    start = dtime(hour=9, minute=15)
    end = dtime(hour=15, minute=30)
    return start <= now_ist.timetz().replace(tzinfo=None) <= end


def get_execution_mode() -> str:
    """Get current execution mode from environment.

    Env var precedence (first match wins):
        1) EXECUTION_MODE
        2) TRADING_MODE
        3) ZERODHA_MODE
        4) MODE

    If none are set, we auto-select:
        - live when market hours are open (IST)
        - historical otherwise
    
    FAIL-FAST: Always returns a valid mode (live/historical/paper), never None.
    """

    for var in ("EXECUTION_MODE", "TRADING_MODE", "ZERODHA_MODE", "MODE"):
        mode = _normalize_mode(os.getenv(var))
        if mode:
            return mode

    # Auto mode - ALWAYS returns a valid mode
    auto_mode = "live" if _market_is_open_ist() else "historical"
    return auto_mode


def get_redis_key(key_type: str, instrument: Optional[str] = None, **kwargs) -> str:
    """Generate standardized Redis keys with MANDATORY mode prefix.
    
    Args:
        key_type: Type of key ('tick', 'ohlc', 'ltp', etc.)
        instrument: Trading instrument symbol
        **kwargs: Additional parameters for key construction
        
    Returns:
        Formatted Redis key with mode prefix (live:|historical:|paper:)
        
    FAIL-FAST: Always returns a mode-prefixed key. Never returns unprefixed keys.
        
    Examples:
        >>> get_redis_key('tick', 'BANKNIFTY26FEBFUT')
        'historical:tick:BANKNIFTY26FEBFUT'  # when market closed
        >>> get_redis_key('ohlc', 'NIFTY', timeframe='5m')
        'live:ohlc:NIFTY:5m'  # when market open
    """
    mode = get_execution_mode()
    
    # FAIL-FAST: Mode must be valid
    if mode not in ("live", "historical", "paper"):
        raise ValueError(f"Invalid execution mode: {mode}. Must be 'live', 'historical', or 'paper'.")
    
    # Build key parts
    parts = [key_type]
    
    if instrument:
        parts.append(instrument)
    
    # Add additional parameters
    for key, value in sorted(kwargs.items()):
        if value is not None:
            parts.append(str(value))
    
    # Join with colon
    redis_key = ":".join(parts)

    # If already mode-prefixed, return as-is
    if redis_key.startswith(_KNOWN_MODE_PREFIXES):
        return redis_key

    # Mandatory mode prefix - ALWAYS applied
    return f"{mode}:{redis_key}"


def get_redis_pattern(pattern: str, mode: Optional[str] = None) -> str:
    """Return a Redis scan pattern with mandatory mode prefix.

    Examples:
      get_redis_pattern('ohlc_sorted:*', mode='live') -> 'live:ohlc_sorted:*'
      get_redis_pattern('live:ohlc_sorted:*') -> 'live:ohlc_sorted:*'
    """
    if not pattern:
        pattern = "*"
    if pattern.startswith(_KNOWN_MODE_PREFIXES):
        return pattern
    effective_mode = _normalize_mode(mode) or get_execution_mode()
    if effective_mode not in ("live", "historical", "paper"):
        effective_mode = "live"
    return f"{effective_mode}:{pattern}"


def clear_mode_data(redis_client, mode: str) -> int:
    """Delete all keys for a given mode prefix.

    Returns number of deleted keys.
    """
    effective_mode = _normalize_mode(mode) or "live"
    deleted = 0
    cursor = 0
    # Use SCAN to avoid blocking Redis.
    while True:
        cursor, keys = redis_client.scan(cursor=cursor, match=f"{effective_mode}:*", count=1000)
        if keys:
            deleted += int(redis_client.delete(*keys))
        if cursor == 0:
            break
    return deleted


def get_market_tick_key(instrument: str) -> str:
    """Get Redis key for market ticks.
    
    Args:
        instrument: Trading instrument symbol
        
    Returns:
        Redis key for tick data
    """
    return get_redis_key('tick', instrument)


def get_ohlc_key(instrument: str, timeframe: str) -> str:
    """Get Redis key for OHLC data.
    
    Args:
        instrument: Trading instrument symbol
        timeframe: Timeframe (1m, 5m, 15m, 1h, etc.)
        
    Returns:
        Redis key for OHLC data
    """
    return get_redis_key('ohlc', instrument, timeframe=timeframe)


def get_ltp_key(instrument: str) -> str:
    """Get Redis key for Last Traded Price.
    
    Args:
        instrument: Trading instrument symbol
        
    Returns:
        Redis key for LTP
    """
    return get_redis_key('ltp', instrument)


if __name__ == "__main__":
    # Test key generation
    print("Redis Key Examples:")
    print(f"  Tick: {get_market_tick_key('BANKNIFTY26FEBFUT')}")
    print(f"  OHLC: {get_ohlc_key('BANKNIFTY26FEBFUT', '5m')}")
    print(f"  LTP: {get_ltp_key('BANKNIFTY26FEBFUT')}")
    
    os.environ['MODE'] = 'historical'
    print(f"\nHistorical mode:")
    print(f"  Tick: {get_market_tick_key('BANKNIFTY26FEBFUT')}")
