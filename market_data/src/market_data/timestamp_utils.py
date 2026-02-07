"""Canonical Timestamp Model for Market Data.

This module provides a standardized way to handle timestamps across the system,
ensuring consistent timezone handling and proper separation of:
- Log time (when log was printed)
- Market time (when trade occurred)
- Indicator time (when indicator was calculated)
- Original timestamp (raw feed time)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def get_market_time(timestamp: Optional[datetime] = None, redis_client=None) -> datetime:
    """Get market time (IST) for a given timestamp.

    In backtest mode, uses virtual time from Redis if available.

    Args:
        timestamp: Optional datetime. If None, uses current time (or virtual time).
                  If naive, assumes IST. If timezone-aware, converts to IST.
        redis_client: Redis client to check for virtual time

    Returns:
        datetime in IST timezone
    """
    if timestamp is None:
        # Check for virtual time first
        if redis_client:
            try:
                virtual_enabled = redis_client.get("system:virtual_time:enabled")
                if virtual_enabled and virtual_enabled.decode() == "1":
                    virtual_time_str = redis_client.get("system:virtual_time:current")
                    if virtual_time_str:
                        virtual_time = datetime.fromisoformat(virtual_time_str.decode())
                        if virtual_time.tzinfo is None:
                            return virtual_time.replace(tzinfo=IST)
                        else:
                            return virtual_time.astimezone(IST)
            except Exception:
                pass
        return datetime.now(IST)

    if timestamp.tzinfo is None:
        # Naive datetime - assume IST
        return timestamp.replace(tzinfo=IST)

    # Convert to IST
    return timestamp.astimezone(IST)


def get_utc_time(timestamp: Optional[datetime] = None) -> datetime:
    """Get UTC time for a given timestamp.
    
    Args:
        timestamp: Optional datetime. If None, uses current time.
    
    Returns:
        datetime in UTC timezone
    """
    if timestamp is None:
        return datetime.now(timezone.utc)
    
    if timestamp.tzinfo is None:
        # Naive datetime - assume IST and convert to UTC
        ist_time = timestamp.replace(tzinfo=IST)
        return ist_time.astimezone(timezone.utc)
    
    return timestamp.astimezone(timezone.utc)


def normalize_timestamp(timestamp: datetime, target_tz: timezone = IST) -> datetime:
    """Normalize a timestamp to a specific timezone.
    
    Args:
        timestamp: Datetime to normalize
        target_tz: Target timezone (default: IST)
    
    Returns:
        datetime in target timezone
    """
    if timestamp.tzinfo is None:
        # Naive datetime - assume IST
        return timestamp.replace(tzinfo=IST).astimezone(target_tz)
    
    return timestamp.astimezone(target_tz)


def create_canonical_timestamp_payload(
    market_timestamp: datetime,
    indicator_timestamp: Optional[datetime] = None,
    original_timestamp: Optional[datetime] = None
) -> Dict[str, Any]:
    """Create a canonical timestamp payload for Redis/WebSocket messages.
    
    Args:
        market_timestamp: When the market event occurred (trade time)
        indicator_timestamp: When indicator was calculated (default: now)
        original_timestamp: Original timestamp from feed (optional)
    
    Returns:
        Dictionary with normalized timestamps in ISO format
    """
    # Normalize all timestamps to IST
    market_time = normalize_timestamp(market_timestamp, IST)
    indicator_time = normalize_timestamp(
        indicator_timestamp or datetime.now(IST), IST
    )
    
    payload = {
        "market_timestamp": market_time.isoformat(),  # IST
        "indicator_timestamp": indicator_time.isoformat(),  # IST
        "market_timestamp_utc": market_time.astimezone(timezone.utc).isoformat(),  # UTC
        "indicator_timestamp_utc": indicator_time.astimezone(timezone.utc).isoformat(),  # UTC
    }
    
    if original_timestamp:
        original_time = normalize_timestamp(original_timestamp, IST)
        payload["original_timestamp"] = original_time.isoformat()
        payload["original_timestamp_utc"] = original_time.astimezone(timezone.utc).isoformat()
    
    return payload


def create_mode_aware_payload(
    mode: str,
    run_id: Optional[str] = None,
    instrument: str = "BANKNIFTY",
    timeframe: str = "1min"
) -> Dict[str, str]:
    """Creates mandatory mode-aware payload fields for ALL messages."""
    payload = {
        "mode": mode,  # "LIVE" or "HISTORICAL"
        "run_id": run_id or "",  # Required for BACKTEST, optional otherwise
        "instrument": instrument,
        "timeframe": timeframe,
    }
    return payload


def detect_instrument_type(instrument: str) -> str:
    """Detect instrument type from symbol.
    
    Args:
        instrument: Instrument symbol (e.g., "BANKNIFTY", "NIFTY BANK", "BANKNIFTY26JANFUT")
    
    Returns:
        "INDEX" for index instruments, "FUT" for futures, "OPT" for options, "UNKNOWN" otherwise
    """
    instrument_upper = instrument.upper()
    
    # Check for futures (contains FUT or date pattern like 26JAN)
    if "FUT" in instrument_upper or any(month in instrument_upper for month in ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]):
        # Check if it's a futures contract (has expiry date)
        if any(char.isdigit() for char in instrument_upper) and ("FUT" in instrument_upper or len(instrument_upper) > 10):
            return "FUT"
    
    # Check for options (contains CE or PE)
    if "CE" in instrument_upper or "PE" in instrument_upper:
        return "OPT"
    
    # Check for index (NIFTY BANK, NIFTY 50, etc.)
    if "NIFTY BANK" in instrument_upper or "NIFTY 50" in instrument_upper or instrument_upper == "BANKNIFTY":
        # If it's just "BANKNIFTY" without expiry, it's likely INDEX
        # But if it has expiry info, it's FUT
        if "FUT" not in instrument_upper and not any(char.isdigit() for char in instrument_upper[8:]):
            return "INDEX"
    
    # Default: try to infer from common patterns
    if instrument_upper in ["BANKNIFTY", "NIFTY BANK", "NIFTY", "NIFTY 50"]:
        return "INDEX"
    
    return "UNKNOWN"


def get_instrument_channel(instrument: str, channel_type: str = "tick") -> str:
    """Get Redis channel name with instrument type suffix.
    
    Args:
        instrument: Instrument symbol
        channel_type: "tick" or "indicators"
    
    Returns:
        Channel name like "market:tick:BANKNIFTY:INDEX" or "indicators:BANKNIFTY:FUT"
    """
    instrument_type = detect_instrument_type(instrument)
    
    # Normalize instrument name (remove spaces, standardize)
    normalized = instrument.upper().replace(" ", "")
    if normalized == "NIFTYBANK":
        normalized = "BANKNIFTY"
    
    if channel_type == "tick":
        return f"market:tick:{normalized}:{instrument_type}"
    elif channel_type == "indicators":
        return f"indicators:{normalized}:{instrument_type}"
    else:
        return f"{channel_type}:{normalized}:{instrument_type}"
