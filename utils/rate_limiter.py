"""Rate limiter utility - generic for any API, any region."""

import asyncio
import time
import logging
from typing import Callable, Any, Optional
from collections import deque

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Generic rate limiter for API calls.
    Works for any API, any rate limit.
    """
    
    def __init__(self, max_calls: int, period: int):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed
            period: Time period in seconds
        """
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()  # Store timestamps of calls
        self.lock = asyncio.Lock()
    
    async def call(
        self, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        """
        Call function with rate limiting.
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result
        """
        async with self.lock:
            # Wait if needed
            await self._wait_if_needed()
            
            # Make call
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Record call timestamp
            self.calls.append(time.time())
            
            return result
    
    async def _wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        now = time.time()
        
        # Remove old calls outside the period
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()
        
        # If at limit, wait until oldest call expires
        if len(self.calls) >= self.max_calls:
            oldest_call = self.calls[0]
            wait_time = self.period - (now - oldest_call) + 0.1  # Small buffer
            
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                
                # Clean up again after waiting
                now = time.time()
                while self.calls and self.calls[0] < now - self.period:
                    self.calls.popleft()
    
    def get_remaining_calls(self) -> int:
        """Get number of remaining calls in current period."""
        now = time.time()
        
        # Remove old calls
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()
        
        return max(0, self.max_calls - len(self.calls))
    
    def reset(self):
        """Reset rate limiter (clear call history)."""
        self.calls.clear()


class AdaptiveRateLimiter(RateLimiter):
    """
    Adaptive rate limiter that adjusts based on API responses.
    """
    
    def __init__(self, max_calls: int, period: int, initial_backoff: float = 1.0):
        super().__init__(max_calls, period)
        self.backoff_multiplier = initial_backoff
        self.max_backoff = 60.0  # Max 60 seconds
    
    async def call_with_retry(
        self,
        func: Callable,
        max_retries: int = 3,
        *args,
        **kwargs
    ) -> Any:
        """
        Call function with rate limiting and retry on rate limit errors.
        
        Args:
            func: Function to call
            max_retries: Maximum retry attempts
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result
        """
        for attempt in range(max_retries):
            try:
                return await self.call(func, *args, **kwargs)
            except Exception as e:
                error_str = str(e).upper()
                
                # Check if it's a rate limit error
                if any(phrase in error_str for phrase in [
                    "RATE LIMIT",
                    "TOO MANY REQUESTS",
                    "429",
                    "QUOTA EXCEEDED"
                ]):
                    if attempt < max_retries - 1:
                        wait_time = min(
                            self.backoff_multiplier * (2 ** attempt),
                            self.max_backoff
                        )
                        logger.warning(
                            f"Rate limit hit, backing off {wait_time:.2f}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                
                # Not a rate limit error, re-raise
                raise
        
        raise RuntimeError(f"Failed after {max_retries} retries")

