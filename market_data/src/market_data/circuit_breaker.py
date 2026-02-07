"""
Circuit Breaker Pattern Implementation - Graceful error handling and resilience.

This module provides circuit breaker functionality to prevent cascading failures
and enable graceful degradation when services become unavailable.
"""

import time
import logging
from enum import Enum
from typing import Callable, Any, Dict, Optional
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker for resilient service calls."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60,
                 expected_exception: Exception = Exception, name: str = "default"):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.success_count = 0

        # Call statistics
        self.call_count = 0
        self.success_count_total = 0
        self.failure_count_total = 0

    def __call__(self, func: Callable) -> Callable:
        """Decorator to apply circuit breaker to a function."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        self.call_count += 1

        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info(f"Circuit breaker {self.name}: HALF_OPEN - Testing recovery")
            else:
                raise CircuitBreakerOpenException(f"Circuit breaker {self.name} is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.last_failure_time is None:
            return True

        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.recovery_timeout

    def _on_success(self):
        """Handle successful call."""
        self.success_count_total += 1

        if self.state == CircuitBreakerState.HALF_OPEN:
            # Recovery successful
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            logger.info(f"Circuit breaker {self.name}: CLOSED - Recovery successful")

        elif self.state == CircuitBreakerState.CLOSED:
            # Normal success
            self.success_count += 1

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count_total += 1
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitBreakerState.HALF_OPEN:
            # Recovery failed, go back to open
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"Circuit breaker {self.name}: OPEN - Recovery failed")

        elif self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                # Too many failures, open circuit
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker {self.name}: OPEN - Failure threshold exceeded ({self.failure_count}/{self.failure_threshold})")

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'call_count': self.call_count,
            'success_rate': self.success_count_total / max(1, self.call_count),
            'last_failure_time': self.last_failure_time,
            'time_since_last_failure': time.time() - (self.last_failure_time or 0)
        }


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class FallbackRegistry:
    """Registry for fallback functions."""

    def __init__(self):
        self.fallbacks: Dict[str, Callable] = {}

    def register(self, service_name: str, fallback_func: Callable):
        """Register a fallback function for a service."""
        self.fallbacks[service_name] = fallback_func
        logger.info(f"Registered fallback for service: {service_name}")

    def get_fallback(self, service_name: str) -> Optional[Callable]:
        """Get fallback function for a service."""
        return self.fallbacks.get(service_name)


class GracefulDegradationManager:
    """Manages graceful degradation when services fail."""

    def __init__(self):
        self.service_states: Dict[str, str] = {}
        self.fallback_registry = FallbackRegistry()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

    def register_service(self, service_name: str, circuit_breaker: CircuitBreaker = None,
                        fallback_func: Callable = None):
        """Register a service with optional circuit breaker and fallback."""
        self.service_states[service_name] = 'healthy'

        if circuit_breaker:
            self.circuit_breakers[service_name] = circuit_breaker

        if fallback_func:
            self.fallback_registry.register(service_name, fallback_func)

    def execute_with_fallback(self, service_name: str, primary_func: Callable,
                            *args, **kwargs) -> Any:
        """Execute function with fallback support."""
        try:
            # Try primary function
            if service_name in self.circuit_breakers:
                circuit_breaker = self.circuit_breakers[service_name]
                result = circuit_breaker.call(primary_func, *args, **kwargs)
            else:
                result = primary_func(*args, **kwargs)

            # Mark service as healthy
            self.service_states[service_name] = 'healthy'
            return result

        except Exception as e:
            logger.warning(f"Primary function failed for {service_name}: {e}")

            # Mark service as degraded
            self.service_states[service_name] = 'degraded'

            # Try fallback
            fallback_func = self.fallback_registry.get_fallback(service_name)
            if fallback_func:
                try:
                    logger.info(f"Executing fallback for {service_name}")
                    return fallback_func(*args, **kwargs)
                except Exception as fallback_error:
                    logger.error(f"Fallback also failed for {service_name}: {fallback_error}")

            # No fallback available or fallback failed
            raise e

    def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """Get status of a service including circuit breaker stats."""
        status = {
            'service': service_name,
            'state': self.service_states.get(service_name, 'unknown'),
            'circuit_breaker': None,
            'fallback_available': service_name in self.fallback_registry.fallbacks
        }

        if service_name in self.circuit_breakers:
            status['circuit_breaker'] = self.circuit_breakers[service_name].get_stats()

        return status

    def get_all_service_status(self) -> Dict[str, Any]:
        """Get status of all registered services."""
        return {
            service_name: self.get_service_status(service_name)
            for service_name in self.service_states.keys()
        }


# Global instances
_circuit_breaker_manager = None
_graceful_degradation_manager = None

def get_circuit_breaker_manager() -> GracefulDegradationManager:
    """Get global circuit breaker and graceful degradation manager."""
    global _graceful_degradation_manager
    if _graceful_degradation_manager is None:
        _graceful_degradation_manager = GracefulDegradationManager()

        # Register default services
        _graceful_degradation_manager.register_service(
            'redis',
            circuit_breaker=CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=30,
                name='redis_circuit_breaker'
            )
        )

        _graceful_degradation_manager.register_service(
            'market_data_api',
            circuit_breaker=CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60,
                name='market_data_api_circuit_breaker'
            )
        )

        _graceful_degradation_manager.register_service(
            'external_api',
            circuit_breaker=CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=300,  # 5 minutes for external APIs
                name='external_api_circuit_breaker'
            )
        )

    return _graceful_degradation_manager


# Fallback functions
def redis_fallback_get(key: str, default=None):
    """Fallback for Redis get operations."""
    logger.warning(f"Redis unavailable, returning default for key: {key}")
    return default

def redis_fallback_set(key: str, value: Any, ex: int = None):
    """Fallback for Redis set operations."""
    logger.warning(f"Redis unavailable, ignoring set operation for key: {key}")
    return True

def api_fallback_response(**kwargs):
    """Fallback response for API calls."""
    logger.warning("API unavailable, returning fallback response")
    return {
        'status': 'service_unavailable',
        'message': 'Service temporarily unavailable, using cached data',
        'timestamp': datetime.now().isoformat(),
        'data': {}
    }

# Register fallbacks
manager = get_circuit_breaker_manager()
manager.fallback_registry.register('redis_get', redis_fallback_get)
manager.fallback_registry.register('redis_set', redis_fallback_set)
manager.fallback_registry.register('market_data_api', api_fallback_response)


# Decorators for easy use
def with_circuit_breaker(service_name: str, failure_threshold: int = 5,
                        recovery_timeout: int = 60):
    """Decorator to add circuit breaker to a function."""
    def decorator(func):
        circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            name=f"{service_name}_circuit_breaker"
        )

        @wraps(func)
        def wrapper(*args, **kwargs):
            return circuit_breaker.call(func, *args, **kwargs)

        return wrapper
    return decorator

def with_fallback(primary_func: Callable, fallback_func: Callable):
    """Decorator to add fallback functionality."""
    @wraps(primary_func)
    def wrapper(*args, **kwargs):
        try:
            return primary_func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Primary function failed, trying fallback: {e}")
            try:
                return fallback_func(*args, **kwargs)
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                raise e
    return wrapper