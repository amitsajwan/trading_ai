"""Mode isolation startup validator.

This module provides validation to ensure execution mode consistency
across environment variables and Redis, preventing data contamination
between LIVE and HISTORICAL modes.
"""
import os
import redis
import logging
from typing import Dict, List, Optional
from redis_key_manager import get_execution_mode

logger = logging.getLogger(__name__)


class ModeValidationError(Exception):
    """Raised when mode configuration is critically inconsistent."""
    pass


def validate_mode_consistency(redis_client: redis.Redis, service_name: str = "service") -> Dict:
    """
    Validate that execution mode is consistent across environment and Redis.
    
    This checks:
    1. EXECUTION_MODE environment variable matches Redis system:execution_mode
    2. Virtual time is not enabled when EXECUTION_MODE=live
    3. Mode-prefixed keys exist in Redis
    4. No orphaned keys from other mode (warning only)
    
    Args:
        redis_client: Redis client instance
        service_name: Name of the service for logging
        
    Returns:
        dict: Validation results with:
            - mode: Current execution mode
            - virtual_time_enabled: Whether virtual time is enabled
            - redis_mode: Mode stored in Redis
            - warnings: List of warning messages
            - status: "ok" or "error"
            
    Raises:
        ModeValidationError: If critical inconsistency detected (e.g., virtual time in live mode)
    """
    try:
        env_mode = get_execution_mode()
    except Exception as e:
        logger.error(f"Failed to get execution mode: {e}")
        env_mode = "live"
    
    warnings: List[str] = []
    
    try:
        # Get Redis mode configuration
        redis_mode_bytes = redis_client.get("system:execution_mode")
        redis_mode = redis_mode_bytes.decode() if redis_mode_bytes else None
        
        virtual_time_enabled_bytes = redis_client.get("system:virtual_time:enabled")
        virtual_time_enabled = virtual_time_enabled_bytes == b"1" if virtual_time_enabled_bytes else False
        
        virtual_time_current = None
        if virtual_time_enabled:
            vt_bytes = redis_client.get("system:virtual_time:current")
            virtual_time_current = vt_bytes.decode() if vt_bytes else None
    except Exception as e:
        logger.warning(f"Failed to read Redis mode configuration: {e}")
        redis_mode = None
        virtual_time_enabled = False
        virtual_time_current = None
    
    # CRITICAL CHECK 1: Virtual time enabled in live mode creates timestamp confusion
    if virtual_time_enabled and env_mode == "live":
        raise ModeValidationError(
            f"CRITICAL: Virtual time is enabled (system:virtual_time:enabled=1) "
            f"but EXECUTION_MODE=live. This creates timestamp confusion and data "
            f"integrity issues. Either:\n"
            f"  1. Set EXECUTION_MODE=historical, or\n"
            f"  2. Disable virtual time: redis-cli DEL system:virtual_time:enabled"
        )
    
    # Check 2: Environment vs Redis mode mismatch (warning only, ENV takes precedence)
    if redis_mode and redis_mode != env_mode:
        warnings.append(
            f"Mode mismatch: EXECUTION_MODE={env_mode}, "
            f"Redis system:execution_mode={redis_mode}. "
            f"Using EXECUTION_MODE value. Consider setting: "
            f"redis-cli SET system:execution_mode {env_mode}"
        )
    
    # Check 3: Verify mode-prefixed keys exist (data sanity check)
    try:
        # Sample a few keys to verify mode prefix usage
        sample_keys = list(redis_client.scan_iter(match=f"{env_mode}:*", count=5))
        
        if len(sample_keys) == 0:
            warnings.append(
                f"No {env_mode}-prefixed keys found in Redis. This may be normal for "
                f"a fresh start, but verify data is being written correctly."
            )
    except Exception as e:
        logger.warning(f"Failed to check for mode-prefixed keys: {e}")
    
    # Check 4: Orphaned keys from other mode (warning only)
    try:
        other_mode = "historical" if env_mode == "live" else "live"
        other_keys = list(redis_client.scan_iter(match=f"{other_mode}:*", count=100))
        
        if len(other_keys) > 0:
            warnings.append(
                f"Found {len(other_keys)} keys with '{other_mode}:' prefix. "
                f"These are from {other_mode.upper()} mode and won't interfere, "
                f"but consider cleaning: "
                f"from redis_key_manager import clear_mode_data; "
                f"clear_mode_data(redis_client, '{other_mode}')"
            )
    except Exception as e:
        logger.warning(f"Failed to check for orphaned keys: {e}")
    
    # Prepare result
    result = {
        "mode": env_mode,
        "virtual_time_enabled": virtual_time_enabled,
        "virtual_time_current": virtual_time_current,
        "redis_mode": redis_mode,
        "warnings": warnings,
        "status": "error" if len(warnings) > 0 else "ok"
    }
    
    # Log validation results
    logger.info(f"[{service_name}] Mode validation: {env_mode.upper()}")
    if virtual_time_enabled:
        logger.info(f"[{service_name}] Virtual time: ENABLED ({virtual_time_current})")
    
    if redis_mode and redis_mode != env_mode:
        logger.warning(f"[{service_name}] Redis mode: {redis_mode} (using ENV: {env_mode})")
    
    for warning in warnings:
        logger.warning(f"[{service_name}] {warning}")
    
    if result['status'] == 'ok':
        logger.info(f"[{service_name}] Mode validation: PASSED")
    else:
        logger.warning(f"[{service_name}] Mode validation: PASSED with warnings")
    
    return result


def log_mode_startup(service_name: str, mode: Optional[str] = None):
    """
    Log mode information at service startup.
    
    Args:
        service_name: Name of the service
        mode: Optional mode override (uses get_execution_mode if not provided)
    """
    if mode is None:
        try:
            mode = get_execution_mode()
        except Exception:
            mode = "unknown"
    
    logger.info(f"{'='*60}")
    logger.info(f"{service_name.upper()} STARTING")
    logger.info(f"Execution Mode: {mode.upper()}")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"{'='*60}")


# Convenience function for quick validation
def validate_or_fail(redis_client: redis.Redis, service_name: str = "service"):
    """
    Validate mode consistency and raise exception if critical errors found.
    
    This is a convenience wrapper around validate_mode_consistency that
    raises ModeValidationError for both critical errors and warnings.
    Use this in services where strict validation is required.
    
    Args:
        redis_client: Redis client instance
        service_name: Name of the service for logging
        
    Raises:
        ModeValidationError: If any validation errors or warnings detected
    """
    result = validate_mode_consistency(redis_client, service_name)
    
    if result['status'] == 'error':
        raise ModeValidationError(
            f"Mode validation failed with {len(result['warnings'])} warning(s):\n" +
            "\n".join(f"  - {w}" for w in result['warnings'])
        )
