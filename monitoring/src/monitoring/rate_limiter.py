"""
Rate limiting for API calls and resource usage.
Implements token bucket algorithm for fair resource allocation.
"""

import time
import logging
import threading
from typing import Dict, Any, Optional
from collections import defaultdict
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))
from config import get_config

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket rate limiter implementation."""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum number of tokens in the bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate

        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        with self._lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                return False

    def get_tokens_available(self) -> float:
        """Get the current number of available tokens."""
        with self._lock:
            self._refill()
            return self.tokens

    def get_wait_time(self, tokens: int = 1) -> float:
        """Get the time to wait until tokens are available."""
        with self._lock:
            self._refill()

            if self.tokens >= tokens:
                return 0.0

            tokens_needed = tokens - self.tokens
            return tokens_needed / self.refill_rate


class RateLimiter:
    """Rate limiter with multiple buckets for different resources."""

    def __init__(self):
        self.config = get_config()
        self.buckets: Dict[str, TokenBucket] = {}

        # Initialize default buckets
        self._init_default_buckets()

    def _init_default_buckets(self):
        """Initialize default rate limiting buckets."""
        # API rate limiting
        self.buckets['api_requests'] = TokenBucket(
            capacity=self.config.api_rate_limit,
            refill_rate=self.config.api_rate_limit / 60.0  # tokens per second
        )

        # LLM API rate limiting
        self.buckets['llm_requests'] = TokenBucket(
            capacity=self.config.llm_rate_limit,
            refill_rate=self.config.llm_rate_limit / 60.0
        )

        # Database operations
        self.buckets['db_operations'] = TokenBucket(
            capacity=1000,  # 1000 operations
            refill_rate=1000 / 60.0  # per second
        )

        # External API calls
        self.buckets['external_api'] = TokenBucket(
            capacity=50,  # 50 calls
            refill_rate=50 / 60.0  # per second
        )

        logger.info("Rate limiter initialized with default buckets")

    def create_bucket(self, name: str, capacity: int, refill_rate: float):
        """Create a custom rate limiting bucket."""
        self.buckets[name] = TokenBucket(capacity, refill_rate)
        logger.info(f"Created rate limiting bucket: {name} (capacity={capacity}, rate={refill_rate}/s)")

    def allow(self, bucket_name: str, tokens: int = 1) -> bool:
        """
        Check if the operation is allowed under rate limiting.

        Args:
            bucket_name: Name of the rate limiting bucket
            tokens: Number of tokens to consume

        Returns:
            True if allowed, False if rate limited
        """
        bucket = self.buckets.get(bucket_name)
        if not bucket:
            logger.warning(f"Rate limiting bucket '{bucket_name}' not found, allowing request")
            return True

        allowed = bucket.consume(tokens)

        if not allowed:
            logger.warning(f"Rate limit exceeded for bucket '{bucket_name}'")
            # Could add metrics collection here

        return allowed

    def wait_for_tokens(self, bucket_name: str, tokens: int = 1, timeout: float = 10.0) -> bool:
        """
        Wait for tokens to become available.

        Args:
            bucket_name: Name of the rate limiting bucket
            tokens: Number of tokens needed
            timeout: Maximum time to wait in seconds

        Returns:
            True if tokens became available, False if timeout
        """
        bucket = self.buckets.get(bucket_name)
        if not bucket:
            return True

        start_time = time.time()
        while time.time() - start_time < timeout:
            if bucket.consume(tokens):
                return True

            # Wait a bit before checking again
            time.sleep(0.1)

        logger.warning(f"Timeout waiting for rate limit tokens in bucket '{bucket_name}'")
        return False

    def get_bucket_status(self, bucket_name: str) -> Optional[Dict[str, Any]]:
        """Get status of a rate limiting bucket."""
        bucket = self.buckets.get(bucket_name)
        if not bucket:
            return None

        return {
            'name': bucket_name,
            'capacity': bucket.capacity,
            'refill_rate': bucket.refill_rate,
            'tokens_available': bucket.get_tokens_available(),
            'utilization_percent': ((bucket.capacity - bucket.get_tokens_available()) / bucket.capacity) * 100
        }

    def get_all_bucket_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all rate limiting buckets."""
        return {
            name: self.get_bucket_status(name)
            for name in self.buckets.keys()
        }

    def reset_bucket(self, bucket_name: str):
        """Reset a rate limiting bucket to full capacity."""
        bucket = self.buckets.get(bucket_name)
        if bucket:
            bucket.tokens = bucket.capacity
            bucket.last_refill = time.time()
            logger.info(f"Reset rate limiting bucket: {bucket_name}")


# Global rate limiter instance
rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return rate_limiter


# Decorators for easy rate limiting

def rate_limit(bucket_name: str, tokens: int = 1):
    """Decorator to apply rate limiting to a function."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not rate_limiter.allow(bucket_name, tokens):
                raise RateLimitExceeded(f"Rate limit exceeded for {bucket_name}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    pass