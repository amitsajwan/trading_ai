"""
Data Storage Manager - Standardized Redis data storage with migration support.

This module provides a unified interface for storing and retrieving market data
in Redis, supporting both legacy individual keys and standardized sorted sets.

Key Features:
- Dual storage format support (sorted sets + individual keys)
- Automatic data migration between formats
- Data integrity validation
- Performance optimization with caching
- Backward compatibility with existing code
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import redis
import os
import sys
import time

# Add root directory to path for redis_key_manager
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from redis_key_manager import get_redis_key, get_redis_pattern
    _HAS_KEY_MANAGER = True
except ImportError as e:
    logger.warning(f"Failed to import redis_key_manager: {e}")
    _HAS_KEY_MANAGER = False
    # Fallback if redis_key_manager not available
    def get_redis_key(key: str) -> str:
        logger.warning(f"Using fallback get_redis_key (no mode prefix): {key}")
        return key

    def get_redis_pattern(pattern: str, mode: Optional[str] = None) -> str:
        return pattern

logger = logging.getLogger(__name__)


class DataStorageManager:
    """Unified data storage manager for Redis operations."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._available = False
        try:
            self.redis.ping()
            self._available = True
        except Exception as exc:
            logger.warning(f"Redis unavailable: {exc}")

    def store_ohlc_bar(self, instrument: str, timeframe: str, bar_data: Dict[str, Any],
                       use_sorted_sets: bool = True) -> bool:
        """Store OHLC bar data using standardized format.

        Args:
            instrument: Trading instrument symbol
            timeframe: Timeframe (1min, 5min, etc.)
            bar_data: OHLC bar data dictionary
            use_sorted_sets: Whether to use sorted sets (True) or individual keys (False)

        Returns:
            True if stored successfully, False otherwise
        """
        if not self._available:
            return False

        try:
            # Normalize timeframe
            normalized_timeframe = self._normalize_timeframe(timeframe)

            # Ensure required fields are present
            required_fields = ['timestamp', 'open', 'high', 'low', 'close']
            for field in required_fields:
                if field not in bar_data:
                    logger.error(f"Missing required field '{field}' in bar data")
                    return False

            # Add provenance & metadata
            bar_data['instrument'] = instrument
            bar_data['timeframe'] = normalized_timeframe
            bar_data.setdefault('_stored_at', datetime.now(timezone.utc).isoformat())
            bar_data.setdefault('_stored_by', os.getenv('PROCESS_NAME', 'unknown_process'))
            bar_data['_format_version'] = bar_data.get('_format_version', '2.0')

            # Store in standardized format (sorted set) with verification & retries
            success = False
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                if use_sorted_sets:
                    success = self._store_in_sorted_set(instrument, normalized_timeframe, bar_data)
                else:
                    success = self._store_as_individual_key(instrument, normalized_timeframe, bar_data)

                if success:
                    # Verify presence in sorted set when using canonical storage
                    if use_sorted_sets:
                        if self._verify_sorted_set_entry(instrument, normalized_timeframe, bar_data):
                            success = True
                            break
                        else:
                            logger.warning(f"Verification failed on attempt {attempt} for {instrument}:{normalized_timeframe}")
                            success = False
                    else:
                        break

                # Retry delay
                time.sleep(0.5)

            # Legacy storage: optional, controlled via env var DISABLE_LEGACY_STORE
            if success and use_sorted_sets and os.getenv('DISABLE_LEGACY_STORE', '0') != '1':
                self._store_as_individual_key(instrument, normalized_timeframe, bar_data, legacy=True)

            if not success:
                logger.error(f"Failed to store OHLC bar for {instrument}:{normalized_timeframe} after {max_attempts} attempts")

            return success

        except Exception as e:
            logger.error(f"Failed to store OHLC bar: {e}")
            return False

    def _verify_sorted_set_entry(self, instrument: str, timeframe: str, bar_data: Dict[str, Any]) -> bool:
        """Verify that a recently stored bar exists in the sorted set by checking recent entries."""
        try:
            sorted_key = get_redis_key(f"ohlc_sorted:{instrument}:{timeframe}")
            results = self.redis.zrange(sorted_key, -10, -1)
            if not results:
                return False

            for json_data in results:
                try:
                    entry = json.loads(json_data)
                    # Match on timestamp and format version as a best-effort check
                    if entry.get('timestamp') == bar_data.get('timestamp') and entry.get('_format_version') == bar_data.get('_format_version'):
                        return True
                except Exception:
                    continue

            return False
        except Exception as e:
            logger.warning(f"Verification error for sorted set entry: {e}")
            return False

    def _store_in_sorted_set(self, instrument: str, timeframe: str, bar_data: Dict[str, Any]) -> bool:
        """Store OHLC bar in Redis sorted set for efficient range queries."""
        try:
            sorted_key = get_redis_key(f"ohlc_sorted:{instrument}:{timeframe}")

            # Use timestamp as score for sorting
            timestamp_str = bar_data['timestamp']
            if isinstance(timestamp_str, str):
                try:
                    # Parse timestamp to get unix timestamp for sorting
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    score = dt.timestamp()
                except ValueError:
                    # Fallback to current time if parsing fails
                    score = datetime.now().timestamp()
            else:
                score = timestamp_str

            # Store JSON data in sorted set
            json_data = json.dumps(bar_data, default=str)
            self.redis.zadd(sorted_key, {json_data: score})

            # Set expiration (24 hours for intraday data) if supported by the client
            try:
                if hasattr(self.redis, 'expire'):
                    self.redis.expire(sorted_key, 86400)
            except Exception as e:
                logger.debug(f"Redis expire not available or failed: {e}")

            logger.debug(f"Stored OHLC bar in sorted set: {sorted_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to store in sorted set: {e}")
            return False

    def _store_as_individual_key(self, instrument: str, timeframe: str,
                                bar_data: Dict[str, Any], legacy: bool = False) -> bool:
        """Store OHLC bar as individual Redis key (legacy format)."""
        try:
            # Create key using timestamp
            timestamp_str = bar_data['timestamp']
            if isinstance(timestamp_str, str):
                # Clean timestamp for key
                key_timestamp = timestamp_str.replace(':', '').replace('-', '').replace('+', '_').replace('Z', '')
            else:
                key_timestamp = str(int(timestamp_str))

            key_suffix = '_legacy' if legacy else ''
            redis_key = get_redis_key(f"ohlc:{instrument}:{timeframe}:{key_timestamp}{key_suffix}")

            # Store JSON data
            json_data = json.dumps(bar_data, default=str)
            self.redis.setex(redis_key, 86400, json_data)  # 24 hour expiration

            logger.debug(f"Stored OHLC bar as individual key: {redis_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to store as individual key: {e}")
            return False

    def get_ohlc_bars(self, instrument: str, timeframe: str, limit: int = 100,
                      prefer_sorted_sets: bool = True) -> List[Dict[str, Any]]:
        """Retrieve OHLC bars with fallback support.

        Args:
            instrument: Trading instrument symbol
            timeframe: Timeframe (1min, 5min, etc.)
            limit: Maximum number of bars to return
            prefer_sorted_sets: Whether to prefer sorted sets over individual keys

        Returns:
            List of OHLC bar dictionaries, sorted by timestamp (oldest first)
        """
        if not self._available:
            return []

        normalized_timeframe = self._normalize_timeframe(timeframe)

        # Only use sorted sets - fail-fast, no fallbacks
        bars = self._get_from_sorted_set(instrument, normalized_timeframe, limit)
        
        if not bars:
            logger.warning(f"No OHLC data found for {instrument}:{normalized_timeframe}")
            return []
        
        return bars

    def _get_from_sorted_set(self, instrument: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
        """Retrieve OHLC bars from Redis sorted set."""
        try:
            # Use get_redis_key to handle mode prefixes (live:, historical:, paper:)
            sorted_key = get_redis_key(f"ohlc_sorted:{instrument}:{timeframe}")

            # Get latest N entries (highest scores)
            results = self.redis.zrange(sorted_key, -limit, -1)
            if not results:
                return []

            bars = []
            for json_data in results:
                try:
                    bar = json.loads(json_data)
                    bars.append(bar)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse OHLC data from sorted set: {e}")
                    continue

            # Sort by timestamp (should already be sorted, but ensure)
            # Support both 'timestamp' and 'start_at' fields
            bars.sort(key=lambda x: x.get('timestamp') or x.get('start_at') or 0)
            return bars

        except Exception as e:
            logger.error(f"Failed to get from sorted set: {e}")
            return []

    # REMOVED: Legacy individual keys method - use sorted sets only

    def migrate_ohlc_data(self, instrument: str, timeframe: str) -> Tuple[int, int]:
        """Migrate OHLC data from individual keys to sorted sets.

        Returns:
            Tuple of (migrated_count, error_count)
        """
        logger.info(f"Starting OHLC data migration for {instrument}:{timeframe}")

        # Get all individual keys
        pattern = get_redis_key(f"ohlc:{instrument}:{timeframe}:*")
        keys = self.redis.keys(pattern)

        migrated = 0
        errors = 0

        for key in keys:
            try:
                # Skip legacy keys (already migrated)
                if key.endswith('_legacy'):
                    continue

                json_data = self.redis.get(key)
                if json_data:
                    bar_data = json.loads(json_data)

                    # Store in sorted set
                    if self._store_in_sorted_set(instrument, timeframe, bar_data):
                        # Mark original key as migrated
                        bar_data['_migrated'] = True
                        self.redis.setex(key, 86400, json.dumps(bar_data, default=str))
                        migrated += 1
                    else:
                        errors += 1

            except Exception as e:
                logger.error(f"Failed to migrate key {key}: {e}")
                errors += 1

        logger.info(f"Migration complete: {migrated} migrated, {errors} errors")
        return migrated, errors

    def validate_data_integrity(self, instrument: str, timeframe: str) -> Dict[str, Any]:
        """Validate data integrity between storage formats."""
        result = {
            'instrument': instrument,
            'timeframe': timeframe,
            'sorted_set_count': 0,
            'individual_keys_count': 0,
            'data_consistent': True,
            'issues': []
        }

        try:
            # Check sorted set
            sorted_key = get_redis_key(f"ohlc_sorted:{instrument}:{timeframe}")
            sorted_count = self.redis.zcount(sorted_key, '-inf', '+inf')
            result['sorted_set_count'] = sorted_count

            # Check individual keys
            pattern = get_redis_key(f"ohlc:{instrument}:{timeframe}:*")
            individual_keys = self.redis.keys(pattern)
            result['individual_keys_count'] = len(individual_keys)

            # Basic consistency check
            if abs(sorted_count - len(individual_keys)) > 5:  # Allow small difference
                result['data_consistent'] = False
                result['issues'].append(f"Count mismatch: sorted_set={sorted_count}, individual_keys={len(individual_keys)}")

        except Exception as e:
            result['data_consistent'] = False
            result['issues'].append(f"Validation error: {e}")

        return result

    def _normalize_timeframe(self, timeframe: str) -> str:
        """Normalize timeframe strings."""
        timeframe = timeframe.lower()
        if timeframe == "minute":
            return "1min"
        elif timeframe.endswith("minute"):
            minutes = timeframe.replace("minute", "").strip()
            return f"{minutes}m"
        return timeframe

    def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """Clean up old data beyond retention period."""
        cutoff_timestamp = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)

        cleaned = 0
        try:
            # Clean up old sorted sets
            sorted_keys = self.redis.keys(get_redis_pattern("ohlc_sorted:*"))
            for key in sorted_keys:
                # Remove entries older than cutoff
                removed = self.redis.zremrangebyscore(key, '-inf', cutoff_timestamp)
                cleaned += removed

            # Clean up old individual keys (this would be more complex)
            # For now, rely on key expiration

        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")

        return cleaned