"""Centralized Time Service for Virtual/Historical Time Support.

This module provides system-wide time synchronization allowing the entire
trading system to operate in virtual time during historical replay.
"""

from datetime import datetime, timezone
from typing import Optional
import os


class TimeService:
    """Centralized time service supporting both real and virtual time."""
    
    def __init__(self, redis_client=None):
        """Initialize time service.
        
        Args:
            redis_client: Redis client for time synchronization across containers
        """
        self.redis_client = redis_client
        self._virtual_time: Optional[datetime] = None
        self._use_virtual_time = False
    
    def set_virtual_time(self, timestamp: datetime | str) -> None:
        """Set the current virtual time for the system.
        
        Args:
            timestamp: Virtual time to set (datetime or ISO string)
        """
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        self._virtual_time = timestamp
        self._use_virtual_time = True
        
        # Sync to Redis for cross-container coordination
        if self.redis_client:
            try:
                self.redis_client.set(
                    "system:virtual_time:enabled",
                    "1"
                )
                self.redis_client.set(
                    "system:virtual_time:current",
                    timestamp.isoformat()
                )
            except Exception:
                pass
    
    def clear_virtual_time(self) -> None:
        """Switch back to real time."""
        self._use_virtual_time = False
        self._virtual_time = None
        
        if self.redis_client:
            try:
                self.redis_client.delete("system:virtual_time:enabled")
                self.redis_client.delete("system:virtual_time:current")
            except Exception:
                pass
    
    def now(self) -> datetime:
        """Get current system time (virtual or real).
        
        Returns:
            Current datetime (virtual if set, otherwise real)
        """
        # Check Redis first for cross-container sync
        if self.redis_client:
            try:
                enabled = self.redis_client.get("system:virtual_time:enabled")
                if enabled and enabled.decode() == "1":
                    vtime = self.redis_client.get("system:virtual_time:current")
                    if vtime:
                        return datetime.fromisoformat(vtime.decode())
            except Exception:
                pass
        
        # Fall back to local virtual time
        if self._use_virtual_time and self._virtual_time:
            return self._virtual_time
        
        # Default to real time
        return datetime.now(timezone.utc).replace(tzinfo=None)
    
    def is_virtual(self) -> bool:
        """Check if currently using virtual time.
        
        Returns:
            True if in virtual time mode
        """
        if self.redis_client:
            try:
                enabled = self.redis_client.get("system:virtual_time:enabled")
                return enabled and enabled.decode() == "1"
            except Exception:
                pass
        
        return self._use_virtual_time
    
    def advance(self, seconds: float) -> datetime:
        """Advance virtual time by specified seconds.
        
        Args:
            seconds: Seconds to advance
            
        Returns:
            New current time after advancing
        """
        from datetime import timedelta
        
        current = self.now()
        new_time = current + timedelta(seconds=seconds)
        self.set_virtual_time(new_time)
        return new_time


# Global time service instance
_time_service: Optional[TimeService] = None


def get_time_service() -> TimeService:
    """Get global time service instance.
    
    Returns:
        TimeService instance
    """
    global _time_service
    
    if _time_service is None:
        # Try to initialize with Redis
        redis_client = None
        try:
            import redis
            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", "6379"))
            redis_client = redis.Redis(host=host, port=port, db=0)
            redis_client.ping()  # Test connection
        except Exception:
            redis_client = None
        
        _time_service = TimeService(redis_client=redis_client)
    
    return _time_service


def now() -> datetime:
    """Get current system time (virtual or real).
    
    This is the main function all components should use instead of datetime.now().
    
    Returns:
        Current datetime (virtual during replay, real otherwise)
    """
    return get_time_service().now()


def set_virtual_time(timestamp: datetime | str) -> None:
    """Set virtual time for historical replay.
    
    Args:
        timestamp: Time to set as current system time
    """
    get_time_service().set_virtual_time(timestamp)


def clear_virtual_time() -> None:
    """Clear virtual time and return to real time."""
    get_time_service().clear_virtual_time()


def is_virtual_time() -> bool:
    """Check if system is in virtual time mode.
    
    Returns:
        True if using virtual time
    """
    return get_time_service().is_virtual()


__all__ = [
    "TimeService",
    "get_time_service",
    "now",
    "set_virtual_time",
    "clear_virtual_time",
    "is_virtual_time",
]

