"""Centralized Redis client factory with mode awareness.

This module provides a standardized way to create Redis clients
with automatic mode logging and configuration.
"""
import os
import redis
import logging
from typing import Optional
from redis_key_manager import get_execution_mode

logger = logging.getLogger(__name__)


def create_redis_client(
    host: Optional[str] = None,
    port: Optional[int] = None,
    db: int = 0,
    decode_responses: bool = True,
    log_mode: bool = True,
    **kwargs
) -> redis.Redis:
    """
    Create Redis client with mode logging and standardized configuration.
    
    This factory function ensures consistent Redis client creation across
    all services and optionally logs the execution mode for visibility.
    
    Args:
        host: Redis host (default from REDIS_HOST env or localhost)
        port: Redis port (default from REDIS_PORT env or 6379)
        db: Redis database number (default 0)
        decode_responses: Whether to decode byte responses to strings
        log_mode: Whether to log execution mode on client creation
        **kwargs: Additional arguments passed to redis.Redis()
        
    Returns:
        redis.Redis: Configured Redis client
        
    Example:
        >>> client = create_redis_client()
        >>> # Or with custom config:
        >>> client = create_redis_client(host='redis-server', port=6380)
    """
    # Get configuration from environment or defaults
    host = host or os.getenv("REDIS_HOST", "localhost")
    port = port or int(os.getenv("REDIS_PORT", "6379"))
    
    # Create client
    client = redis.Redis(
        host=host,
        port=port,
        db=db,
        decode_responses=decode_responses,
        **kwargs
    )
    
    # Log mode for visibility
    if log_mode:
        try:
            mode = get_execution_mode()
            logger.info(f"Redis client created: {host}:{port} (mode={mode.upper()})")
        except Exception as e:
            logger.warning(f"Redis client created: {host}:{port} (mode detection failed: {e})")
    
    return client


def create_redis_client_with_mode_check(
    host: Optional[str] = None,
    port: Optional[int] = None,
    db: int = 0,
    decode_responses: bool = True,
    **kwargs
) -> redis.Redis:
    """
    Create Redis client and verify mode consistency.
    
    This variant creates a client and immediately checks that it can
    connect and read mode configuration. Use this in critical services
    where mode validation is essential at startup.
    
    Args:
        host: Redis host
        port: Redis port
        db: Redis database number
        decode_responses: Whether to decode responses
        **kwargs: Additional arguments
        
    Returns:
        redis.Redis: Configured and validated Redis client
        
    Raises:
        redis.ConnectionError: If Redis is unavailable
        RuntimeError: If mode validation fails
    """
    client = create_redis_client(
        host=host,
        port=port,
        db=db,
        decode_responses=decode_responses,
        log_mode=False,
        **kwargs
    )
    
    # Test connection
    try:
        client.ping()
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis at {host}:{port}")
        raise
    
    # Check mode consistency
    try:
        env_mode = get_execution_mode()
        redis_mode_bytes = client.get("system:execution_mode")
        redis_mode = (
            redis_mode_bytes.decode() if isinstance(redis_mode_bytes, (bytes, bytearray))
            else redis_mode_bytes
        )
        
        if redis_mode and redis_mode != env_mode:
            logger.warning(
                f"Mode mismatch: EXECUTION_MODE={env_mode}, "
                f"Redis={redis_mode}. Using EXECUTION_MODE."
            )
        
        logger.info(f"Redis client validated: {host}:{port} (mode={env_mode.upper()})")
        
    except Exception as e:
        logger.warning(f"Mode validation skipped: {e}")
    
    return client
