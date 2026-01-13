"""
Error handling and recovery mechanisms for trading system.
Includes retry logic, circuit breakers, and graceful degradation.
"""

import time
import logging
import asyncio
from typing import Callable, Any, Optional, Dict, Type
from functools import wraps
from datetime import datetime, timedelta
from enum import Enum
import random
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))
from config import get_config

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"         # Failing, requests rejected
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60,
                 expected_exception: Type[Exception] = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None

    def _can_attempt_reset(self) -> bool:
        """Check if we can attempt to reset the circuit breaker."""
        if self.state != CircuitBreakerState.OPEN:
            return False

        if self.last_failure_time is None:
            return True

        return (datetime.now() - self.last_failure_time) > timedelta(seconds=self.recovery_timeout)

    def _record_success(self):
        """Record a successful operation."""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        logger.info("Circuit breaker reset to CLOSED state")

    def _record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
        else:
            logger.debug(f"Circuit breaker failure count: {self.failure_count}")

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == CircuitBreakerState.OPEN:
            if self._can_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker testing recovery (HALF_OPEN)")
            else:
                raise CircuitBreakerOpenException("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            if self.state == CircuitBreakerState.HALF_OPEN:
                self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class RetryPolicy:
    """Retry policy with exponential backoff and jitter."""

    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0,
                 max_delay: float = 60.0, backoff_factor: float = 2.0,
                 jitter: bool = True):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number."""
        delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        delay = min(delay, self.max_delay)

        if self.jitter:
            # Add random jitter (±25%)
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)


def retry_with_backoff(retry_policy: Optional[RetryPolicy] = None,
                      exceptions: tuple = (Exception,)) -> Callable:
    """Decorator for retrying functions with exponential backoff."""
    if retry_policy is None:
        retry_policy = RetryPolicy()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, retry_policy.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < retry_policy.max_attempts:
                        delay = retry_policy.get_delay(attempt)
                        logger.warning(f"Attempt {attempt} failed for {func.__name__}: {e}. "
                                     f"Retrying in {delay:.2f}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"All {retry_policy.max_attempts} attempts failed for {func.__name__}: {e}")

            raise last_exception

        return wrapper
    return decorator


async def retry_with_backoff_async(retry_policy: Optional[RetryPolicy] = None,
                                  exceptions: tuple = (Exception,)) -> Callable:
    """Async version of retry_with_backoff decorator."""
    if retry_policy is None:
        retry_policy = RetryPolicy()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, retry_policy.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < retry_policy.max_attempts:
                        delay = retry_policy.get_delay(attempt)
                        logger.warning(f"Attempt {attempt} failed for {func.__name__}: {e}. "
                                     f"Retrying in {delay:.2f}s...")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"All {retry_policy.max_attempts} attempts failed for {func.__name__}: {e}")

            raise last_exception

        return wrapper
    return decorator


class ErrorHandler:
    """Central error handling and recovery coordinator."""

    def __init__(self):
        self.config = get_config()
        self.circuit_breakers = {}
        self.retry_policies = {}

        # Default retry policy
        self.default_retry_policy = RetryPolicy(
            max_attempts=self.config.max_retries,
            base_delay=self.config.retry_delay
        )

    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """Get or create a circuit breaker for the given name."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker()
        return self.circuit_breakers[name]

    def get_retry_policy(self, name: str) -> RetryPolicy:
        """Get or create a retry policy for the given name."""
        if name not in self.retry_policies:
            self.retry_policies[name] = self.default_retry_policy
        return self.retry_policies[name]

    def set_retry_policy(self, name: str, policy: RetryPolicy):
        """Set a custom retry policy for the given name."""
        self.retry_policies[name] = policy

    def execute_with_protection(self, name: str, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with circuit breaker and retry protection."""
        circuit_breaker = self.get_circuit_breaker(name)
        retry_policy = self.get_retry_policy(name)

        @retry_with_backoff(retry_policy)
        def protected_call():
            return circuit_breaker.call(func, *args, **kwargs)

        return protected_call()

    async def execute_with_protection_async(self, name: str, func: Callable, *args, **kwargs) -> Any:
        """Async version of execute_with_protection."""
        circuit_breaker = self.get_circuit_breaker(name)
        retry_policy = self.get_retry_policy(name)

        @retry_with_backoff_async(retry_policy)
        async def protected_call():
            return circuit_breaker.call(func, *args, **kwargs)

        return await protected_call()

    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """Handle and log errors with context."""
        error_context = context or {}

        logger.error(f"Error handled: {error}", extra={
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': error_context,
            'timestamp': datetime.now().isoformat()
        })

        # Here you could add error reporting, alerting, etc.
        # For now, just log the error

    def graceful_shutdown(self, signum=None, frame=None):
        """Perform graceful shutdown on system signals."""
        logger.info("Initiating graceful shutdown...")

        # Close circuit breakers
        for name, cb in self.circuit_breakers.items():
            if cb.state != CircuitBreakerState.CLOSED:
                logger.info(f"Closing circuit breaker {name}")

        logger.info("Graceful shutdown complete")


# Global error handler instance
error_handler = ErrorHandler()


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance."""
    return error_handler