"""Market hours utility for Indian equity markets."""

from datetime import datetime, time
from typing import Tuple


def is_market_open(now: datetime = None) -> bool:
    """
    Check if Indian equity market is currently open.
    
    Market hours: Monday-Friday, 9:15 AM to 3:30 PM IST
    
    Args:
        now: Optional datetime to check. Defaults to current time.
    
    Returns:
        True if market is open, False otherwise.
    """
    if now is None:
        now = datetime.now()
    
    # Market is only open Monday-Friday
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    # Market hours: 9:15 AM to 3:30 PM IST
    market_open = time(9, 15, 0)
    market_close = time(15, 30, 0)
    
    current_time = now.time()
    return market_open <= current_time < market_close  # Market closes AT 3:30, so < not <=


def get_market_status(now: datetime = None) -> Tuple[bool, str]:
    """
    Get market status with description.
    
    Args:
        now: Optional datetime to check. Defaults to current time.
    
    Returns:
        Tuple of (is_open: bool, description: str)
    """
    if now is None:
        now = datetime.now()
    
    is_open = is_market_open(now)
    
    if is_open:
        return True, "Market is OPEN (9:15 AM - 3:30 PM IST)"
    else:
        if now.weekday() >= 5:
            return False, "Market is CLOSED (Weekend)"
        elif now.time() < time(9, 15, 0):
            return False, "Market is CLOSED (Pre-market hours)"
        else:
            return False, "Market is CLOSED (Post-market hours)"


def get_suggested_mode(now: datetime = None) -> str:
    """
    Get suggested trading mode based on market hours.
    
    Args:
        now: Optional datetime to check. Defaults to current time.
    
    Returns:
        Suggested mode: 'paper_live' if market open, 'paper_mock' if closed
    """
    if is_market_open(now):
        return "paper_live"
    else:
        return "paper_mock"


