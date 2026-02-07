"""
Data Validation Layer - Ensures data integrity across system components.

This module provides comprehensive validation for market data, technical indicators,
and system state to prevent data corruption and ensure consistency.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import asdict
import redis

logger = logging.getLogger(__name__)


class DataValidator:
    """Comprehensive data validation and integrity checker."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._available = False
        try:
            self.redis.ping()
            self._available = True
        except Exception as exc:
            logger.warning(f"Redis unavailable for validation: {exc}")

    def validate_ohlc_data(self, instrument: str, timeframe: str,
                          max_age_hours: int = 24) -> Dict[str, Any]:
        """Validate OHLC data integrity for an instrument/timeframe.

        Args:
            instrument: Trading instrument symbol
            timeframe: Timeframe (1min, 5min, etc.)
            max_age_hours: Maximum age of data to consider (for staleness check)

        Returns:
            Validation report dictionary
        """
        report = {
            'instrument': instrument,
            'timeframe': timeframe,
            'valid': True,
            'issues': [],
            'metrics': {}
        }

        if not self._available:
            report['valid'] = False
            report['issues'].append('Redis unavailable')
            return report

        try:
            # Check data existence
            sorted_key = f"ohlc_sorted:{instrument}:{timeframe}"
            individual_pattern = f"ohlc:{instrument}:{timeframe}:*"

            sorted_count = self.redis.zcount(sorted_key, '-inf', '+inf')
            individual_keys = self.redis.keys(individual_pattern)
            individual_count = len(individual_keys)

            report['metrics']['sorted_set_count'] = sorted_count
            report['metrics']['individual_keys_count'] = individual_count

            if sorted_count == 0 and individual_count == 0:
                report['valid'] = False
                report['issues'].append('No OHLC data found')
                return report

            # Validate data consistency between formats
            # If only the sorted set is present and individual keys are gone, consider it valid (migration finished)
            if individual_count == 0 and sorted_count > 0:
                logger.info('No individual keys found; canonical sorted set present (migration complete)')
            elif abs(sorted_count - individual_count) > 2:  # Allow small difference when both formats present
                report['issues'].append(
                    f'Data format inconsistency: sorted_set={sorted_count}, individual_keys={individual_count}'
                )

            # Sample and validate data quality
            if sorted_count > 0:
                quality_issues = self._validate_ohlc_quality(sorted_key, max_age_hours)
                report['issues'].extend(quality_issues)

            elif individual_count > 0:
                # Validate a sample of individual keys
                sample_keys = individual_keys[:min(5, len(individual_keys))]
                quality_issues = self._validate_individual_keys_quality(sample_keys, max_age_hours)
                report['issues'].extend(quality_issues)

            # Check for data gaps
            gap_issues = self._check_data_gaps(instrument, timeframe)
            report['issues'].extend(gap_issues)

            # Overall validity
            report['valid'] = len(report['issues']) == 0

        except Exception as e:
            logger.error(f"Error validating OHLC data: {e}")
            report['valid'] = False
            report['issues'].append(f'Validation error: {str(e)}')

        return report

    def _validate_ohlc_quality(self, sorted_key: str, max_age_hours: int) -> List[str]:
        """Validate quality of OHLC data in sorted set."""
        issues = []

        try:
            # Get a sample of recent data
            recent_data = self.redis.zrange(sorted_key, -10, -1)
            if not recent_data:
                return ['No recent data in sorted set']

            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

            for json_data in recent_data[-3:]:  # Check last 3 bars
                try:
                    bar = json.loads(json_data)

                    # Validate required fields
                    required_fields = ['timestamp', 'open', 'high', 'low', 'close']
                    for field in required_fields:
                        if field not in bar:
                            issues.append(f'Missing required field: {field}')
                            continue

                    # Validate data types and ranges
                    if not isinstance(bar.get('open'), (int, float)) or bar['open'] <= 0:
                        issues.append(f'Invalid open price: {bar.get("open")}')

                    if not isinstance(bar.get('close'), (int, float)) or bar['close'] <= 0:
                        issues.append(f'Invalid close price: {bar.get("close")}')

                    # Validate OHLC relationship
                    high = bar.get('high', 0)
                    low = bar.get('low', 0)
                    if high < low:
                        issues.append(f'High < Low: high={high}, low={low}')

                    # Check staleness
                    timestamp_str = bar.get('timestamp')
                    if timestamp_str:
                        try:
                            bar_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            if bar_time < cutoff_time:
                                issues.append(f'Stale data: {bar_time}')
                        except ValueError:
                            issues.append(f'Invalid timestamp format: {timestamp_str}')

                except (json.JSONDecodeError, KeyError) as e:
                    issues.append(f'Data parsing error: {e}')

        except Exception as e:
            issues.append(f'Quality validation error: {e}')

        return issues

    def _validate_individual_keys_quality(self, keys: List[str], max_age_hours: int) -> List[str]:
        """Validate quality of OHLC data in individual keys."""
        issues = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

        for key in keys:
            try:
                json_data = self.redis.get(key)
                if not json_data:
                    issues.append(f'Empty data for key: {key}')
                    continue

                bar = json.loads(json_data)

                # Basic validation (same as sorted set)
                if not isinstance(bar.get('close'), (int, float)) or bar.get('close', 0) <= 0:
                    issues.append(f'Invalid close price in {key}')

                timestamp_str = bar.get('timestamp')
                if timestamp_str:
                    try:
                        bar_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        if bar_time < cutoff_time:
                            issues.append(f'Stale data in {key}: {bar_time}')
                    except ValueError:
                        issues.append(f'Invalid timestamp in {key}: {timestamp_str}')

            except Exception as e:
                issues.append(f'Error validating {key}: {e}')

        return issues

    def _check_data_gaps(self, instrument: str, timeframe: str) -> List[str]:
        """Check for significant gaps in OHLC data."""
        issues = []

        try:
            # This is a simplified gap check - in production you'd want more sophisticated logic
            sorted_key = f"ohlc_sorted:{instrument}:{timeframe}"
            count = self.redis.zcount(sorted_key, '-inf', '+inf')

            if count > 10:  # Only check if we have enough data
                # Check if data spans expected time range
                earliest = self.redis.zrange(sorted_key, 0, 0, withscores=True)
                latest = self.redis.zrange(sorted_key, -1, -1, withscores=True)

                if earliest and latest:
                    earliest_time = datetime.fromtimestamp(earliest[0][1])
                    latest_time = datetime.fromtimestamp(latest[0][1])

                    expected_span_hours = 8  # Expected trading hours per day
                    actual_span_hours = (latest_time - earliest_time).total_seconds() / 3600

                    if actual_span_hours < expected_span_hours * 0.1:  # Less than 10% of expected
                        issues.append('.1f')

        except Exception as e:
            logger.warning(f"Error checking data gaps: {e}")

        return issues

    def validate_technical_indicators(self, instrument: str) -> Dict[str, Any]:
        """Validate technical indicators data integrity."""
        report = {
            'instrument': instrument,
            'valid': True,
            'issues': [],
            'indicators_present': [],
            'indicators_missing': []
        }

        expected_indicators = [
            'rsi_14', 'macd_value', 'macd_signal', 'bollinger_upper',
            'bollinger_lower', 'adx_14', 'sma_10', 'ema_20'
        ]

        for indicator in expected_indicators:
            key = f'indicators:{instrument}:{indicator}'
            value = self.redis.get(key)

            if value is not None:
                try:
                    # Try to parse as number
                    float(value)
                    report['indicators_present'].append(indicator)
                except ValueError:
                    report['issues'].append(f'Invalid value for {indicator}: {value}')
            else:
                report['indicators_missing'].append(indicator)

        # Check for stale indicators
        if report['indicators_present']:
            # Check timestamp if available
            timestamp_key = f'indicators:{instrument}:timestamp'
            timestamp_str = self.redis.get(timestamp_key)

            if timestamp_str:
                try:
                    indicator_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    age_hours = (datetime.now(timezone.utc) - indicator_time).total_seconds() / 3600

                    if age_hours > 1:  # More than 1 hour old
                        report['issues'].append('.1f')
                except ValueError:
                    report['issues'].append(f'Invalid timestamp format: {timestamp_str}')

        report['valid'] = len(report['issues']) == 0 and len(report['indicators_present']) > 0
        return report

    def validate_system_health(self) -> Dict[str, Any]:
        """Validate overall system health and data consistency."""
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'overall_health': 'healthy',
            'components': {},
            'issues': []
        }

        # Check Redis connectivity
        try:
            self.redis.ping()
            report['components']['redis'] = 'healthy'
        except Exception as e:
            report['components']['redis'] = 'unhealthy'
            report['issues'].append(f'Redis connection failed: {e}')
            report['overall_health'] = 'critical'

        # Check for orphaned data
        try:
            # Count keys by pattern
            ohlc_keys = len(self.redis.keys('ohlc:*'))
            indicator_keys = len(self.redis.keys('indicators:*'))
            tick_keys = len(self.redis.keys('tick:*'))

            report['components']['data_counts'] = {
                'ohlc_bars': ohlc_keys,
                'indicators': indicator_keys,
                'ticks': tick_keys
            }

            # Warn if no data
            if ohlc_keys == 0:
                report['issues'].append('No OHLC data found in system')
            if indicator_keys == 0:
                report['issues'].append('No technical indicators found')

        except Exception as e:
            report['issues'].append(f'Data count check failed: {e}')

        # Update overall health
        if report['issues']:
            if any('Redis connection failed' in issue for issue in report['issues']):
                report['overall_health'] = 'critical'
            else:
                report['overall_health'] = 'degraded'

        return report

    def repair_data_integrity(self, instrument: str, timeframe: str) -> Dict[str, Any]:
        """Attempt to repair data integrity issues."""
        repair_report = {
            'instrument': instrument,
            'timeframe': timeframe,
            'repairs_attempted': [],
            'repairs_successful': [],
            'repairs_failed': []
        }

        # Validate current state
        validation = self.validate_ohlc_data(instrument, timeframe)

        if validation['valid']:
            repair_report['status'] = 'no_repairs_needed'
            return repair_report

        # Attempt repairs
        try:
            from .data_storage_manager import DataStorageManager
            storage_manager = DataStorageManager(self.redis)

            # Try to migrate data to standardized format
            migrated, errors = storage_manager.migrate_ohlc_data(instrument, timeframe)
            repair_report['repairs_attempted'].append('data_migration')

            if errors == 0:
                repair_report['repairs_successful'].append(f'migrated_{migrated}_records')
            else:
                repair_report['repairs_failed'].append(f'migration_errors_{errors}')

            # Validate again after repair
            post_validation = self.validate_ohlc_data(instrument, timeframe)
            repair_report['post_repair_valid'] = post_validation['valid']

        except Exception as e:
            repair_report['repairs_failed'].append(f'repair_exception_{str(e)}')

        repair_report['status'] = 'repair_completed'
        return repair_report


def create_data_validation_middleware(validator: DataValidator) -> Callable:
    """Create middleware for automatic data validation."""
    def validation_middleware(func):
        def wrapper(*args, **kwargs):
            # Pre-validation
            if len(args) > 0 and hasattr(args[0], 'instrument'):
                instrument = args[0].instrument
                # Could add pre-call validation here

            # Execute function
            result = func(*args, **kwargs)

            # Post-validation
            try:
                if 'instrument' in kwargs:
                    instrument = kwargs['instrument']
                    # Validate data integrity after operation
                    validation = validator.validate_ohlc_data(instrument, '1min')
                    if not validation['valid']:
                        logger.warning(f"Data validation failed after {func.__name__}: {validation['issues']}")
            except Exception as e:
                logger.error(f"Validation middleware error: {e}")

            return result
        return wrapper
    return validation_middleware


# Global validator instance
_data_validator = None

def get_data_validator(redis_client: redis.Redis = None) -> DataValidator:
    """Get global data validator instance."""
    global _data_validator
    if _data_validator is None:
        if redis_client is None:
            # Try to create from environment
            import os
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = int(os.getenv('REDIS_PORT', '6379'))
            redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        _data_validator = DataValidator(redis_client)
    return _data_validator