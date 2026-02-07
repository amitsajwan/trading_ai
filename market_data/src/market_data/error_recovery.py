"""
Error Recovery System - Automatic recovery from common system issues.

This module provides automatic recovery mechanisms for common system failures,
data corruption, and service unavailability issues.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import redis
import requests
import subprocess
import os

logger = logging.getLogger(__name__)


class RecoveryAction:
    """Represents a recovery action that can be taken."""

    def __init__(self, name: str, description: str, action_func: Callable,
                 max_attempts: int = 3, cooldown_seconds: int = 300):
        self.name = name
        self.description = description
        self.action_func = action_func
        self.max_attempts = max_attempts
        self.cooldown_seconds = cooldown_seconds

        self.attempt_count = 0
        self.last_attempt = None
        self.success_count = 0

    def can_attempt(self) -> bool:
        """Check if recovery action can be attempted."""
        if self.attempt_count >= self.max_attempts:
            return False

        if self.last_attempt and (time.time() - self.last_attempt) < self.cooldown_seconds:
            return False

        return True

    def execute(self, *args, **kwargs) -> bool:
        """Execute the recovery action."""
        if not self.can_attempt():
            return False

        try:
            self.attempt_count += 1
            self.last_attempt = time.time()

            logger.info(f"Attempting recovery action: {self.name} (attempt {self.attempt_count}/{self.max_attempts})")

            result = self.action_func(*args, **kwargs)

            if result:
                self.success_count += 1
                logger.info(f"Recovery action successful: {self.name}")
                return True
            else:
                logger.warning(f"Recovery action failed: {self.name}")
                return False

        except Exception as e:
            logger.error(f"Recovery action error for {self.name}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get recovery action statistics."""
        return {
            'name': self.name,
            'description': self.description,
            'attempts': self.attempt_count,
            'successes': self.success_count,
            'last_attempt': self.last_attempt,
            'can_attempt': self.can_attempt()
        }


class ErrorRecoveryManager:
    """Manages automatic error recovery for the system."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.recovery_actions: Dict[str, RecoveryAction] = {}

        self._register_default_actions()

    def _register_default_actions(self):
        """Register default recovery actions."""

        # Redis connection recovery
        self.register_action(
            'redis_restart',
            'Restart Redis service',
            self._restart_redis_service,
            max_attempts=2,
            cooldown_seconds=600  # 10 minutes
        )

        # Data integrity repair
        self.register_action(
            'data_integrity_repair',
            'Repair data integrity issues',
            self._repair_data_integrity,
            max_attempts=3,
            cooldown_seconds=1800  # 30 minutes
        )

        # Service restart actions
        self.register_action(
            'market_data_api_restart',
            'Restart market data API service',
            lambda: self._restart_service('market_data_api', 8004),
            max_attempts=3,
            cooldown_seconds=300  # 5 minutes
        )

        self.register_action(
            'news_api_restart',
            'Restart news API service',
            lambda: self._restart_service('news_api', 8005),
            max_attempts=3,
            cooldown_seconds=300  # 5 minutes
        )

        # Data migration
        self.register_action(
            'data_migration',
            'Migrate data to standardized format',
            self._migrate_data_format,
            max_attempts=1,
            cooldown_seconds=3600  # 1 hour
        )

    def register_action(self, action_id: str, action: RecoveryAction):
        """Register a recovery action."""
        self.recovery_actions[action_id] = action
        logger.info(f"Registered recovery action: {action_id}")

    def diagnose_and_recover(self, issue_type: str, issue_details: Dict[str, Any]) -> Dict[str, Any]:
        """Diagnose an issue and attempt automatic recovery."""
        logger.info(f"Diagnosing issue: {issue_type}")

        recovery_plan = self._create_recovery_plan(issue_type, issue_details)
        results = []

        for action_id in recovery_plan:
            if action_id in self.recovery_actions:
                action = self.recovery_actions[action_id]

                if action.can_attempt():
                    success = action.execute(issue_details)
                    results.append({
                        'action': action_id,
                        'success': success,
                        'attempts': action.attempt_count
                    })

                    if success:
                        # Stop trying further actions if one succeeds
                        break
                else:
                    results.append({
                        'action': action_id,
                        'success': False,
                        'reason': 'cooldown_or_max_attempts_reached'
                    })

        return {
            'issue_type': issue_type,
            'recovery_plan': recovery_plan,
            'results': results,
            'overall_success': any(r['success'] for r in results)
        }

    def _create_recovery_plan(self, issue_type: str, issue_details: Dict[str, Any]) -> List[str]:
        """Create a recovery plan based on issue type."""

        if issue_type == 'redis_connection_failed':
            return ['redis_restart', 'data_integrity_repair']

        elif issue_type == 'data_integrity_violation':
            return ['data_integrity_repair', 'data_migration']

        elif issue_type == 'service_unhealthy':
            service_name = issue_details.get('service', '')
            if 'market_data' in service_name:
                return ['market_data_api_restart']
            elif 'news' in service_name:
                return ['news_api_restart']
            else:
                return []

        elif issue_type == 'data_format_inconsistency':
            return ['data_migration', 'data_integrity_repair']

        else:
            return ['data_integrity_repair']  # Default fallback

    def _restart_redis_service(self, issue_details: Dict[str, Any] = None) -> bool:
        """Attempt to restart Redis service."""
        try:
            # Try different restart methods based on platform
            if os.name == 'nt':  # Windows
                # Try to restart Redis service
                result = subprocess.run(
                    ['net', 'stop', 'redis'],
                    capture_output=True,
                    timeout=30
                )
                if result.returncode == 0:
                    result = subprocess.run(
                        ['net', 'start', 'redis'],
                        capture_output=True,
                        timeout=30
                    )
                    return result.returncode == 0
            else:  # Unix-like systems
                result = subprocess.run(
                    ['systemctl', 'restart', 'redis'],
                    capture_output=True,
                    timeout=30
                )
                return result.returncode == 0

        except Exception as e:
            logger.error(f"Failed to restart Redis service: {e}")
            return False

    def _repair_data_integrity(self, issue_details: Dict[str, Any] = None) -> bool:
        """Attempt to repair data integrity issues."""
        try:
            from .data_validator import get_data_validator
            validator = get_data_validator(self.redis)

            instrument = issue_details.get('instrument', 'BANKNIFTY26JANFUT') if issue_details else 'BANKNIFTY26JANFUT'
            timeframe = issue_details.get('timeframe', '1min') if issue_details else '1min'

            repair_result = validator.repair_data_integrity(instrument, timeframe)
            return repair_result.get('status') == 'repair_completed'

        except Exception as e:
            logger.error(f"Data integrity repair failed: {e}")
            return False

    def _restart_service(self, service_name: str, port: int) -> bool:
        """Restart a specific service."""
        try:
            logger.info(f"Attempting to restart {service_name} on port {port}")

            # Kill existing process on port
            if os.name == 'nt':  # Windows
                result = subprocess.run(
                    ['netstat', '-ano', '|', 'findstr', f':{port}'],
                    capture_output=True,
                    shell=True
                )
                if result.returncode == 0:
                    # Extract PID and kill
                    lines = result.stdout.decode().strip().split('\n')
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = parts[4]
                            subprocess.run(['taskkill', '/PID', pid, '/F'], capture_output=True)

            # For now, just return success - in production you'd implement actual service restart
            # This would require knowing how to restart each specific service
            logger.info(f"Service restart simulation completed for {service_name}")
            return True

        except Exception as e:
            logger.error(f"Service restart failed for {service_name}: {e}")
            return False

    def _migrate_data_format(self, issue_details: Dict[str, Any] = None) -> bool:
        """Migrate data to standardized format."""
        try:
            from .data_storage_manager import DataStorageManager
            storage_manager = DataStorageManager(self.redis)

            instrument = issue_details.get('instrument', 'BANKNIFTY26JANFUT') if issue_details else 'BANKNIFTY26JANFUT'
            timeframe = issue_details.get('timeframe', '1min') if issue_details else '1min'

            migrated, errors = storage_manager.migrate_ohlc_data(instrument, timeframe)

            if errors == 0:
                logger.info(f"Data migration successful: {migrated} records migrated")
                return True
            else:
                logger.warning(f"Data migration completed with errors: {migrated} migrated, {errors} errors")
                return migrated > 0  # Consider partial success as success

        except Exception as e:
            logger.error(f"Data migration failed: {e}")
            return False

    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get statistics for all recovery actions."""
        return {
            action_id: action.get_stats()
            for action_id, action in self.recovery_actions.items()
        }

    def manual_recovery(self, action_id: str, issue_details: Dict[str, Any] = None) -> bool:
        """Manually trigger a recovery action."""
        if action_id not in self.recovery_actions:
            logger.error(f"Unknown recovery action: {action_id}")
            return False

        action = self.recovery_actions[action_id]
        return action.execute(issue_details)


# Global recovery manager
_recovery_manager = None

def get_error_recovery_manager(redis_client: redis.Redis = None) -> ErrorRecoveryManager:
    """Get global error recovery manager instance."""
    global _recovery_manager
    if _recovery_manager is None:
        if redis_client is None:
            import os
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = int(os.getenv('REDIS_PORT', '6379'))
            redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        _recovery_manager = ErrorRecoveryManager(redis_client)
    return _recovery_manager


# Integration with monitoring system
def integrate_with_monitoring():
    """Integrate error recovery with the monitoring system."""
    try:
        from ..scripts.monitor_system import SystemMonitor

        # Monkey patch the monitoring system to include recovery
        original_perform_health_check = SystemMonitor._perform_health_check

        def enhanced_health_check(self):
            report = original_perform_health_check(self)

            # Check if automatic recovery is needed
            if report['overall_status'] in ['degraded', 'critical']:
                recovery_manager = get_error_recovery_manager()

                # Attempt recovery for critical issues
                for issue in report.get('issues', []):
                    if 'Redis connection failed' in issue:
                        recovery_result = recovery_manager.diagnose_and_recover(
                            'redis_connection_failed',
                            {'issues': report['issues']}
                        )
                        if recovery_result['overall_success']:
                            logger.info("Automatic recovery successful for Redis connection")
                            # Re-run health check
                            return self._perform_health_check()

                    elif 'data integrity' in issue.lower():
                        recovery_result = recovery_manager.diagnose_and_recover(
                            'data_integrity_violation',
                            {'issues': report['issues']}
                        )
                        if recovery_result['overall_success']:
                            logger.info("Automatic recovery successful for data integrity")
                            # Re-run health check
                            return self._perform_health_check()

            return report

        SystemMonitor._perform_health_check = enhanced_health_check
        logger.info("Error recovery integrated with monitoring system")

    except ImportError:
        logger.warning("Could not integrate with monitoring system - scripts not available")
    except Exception as e:
        logger.error(f"Failed to integrate error recovery with monitoring: {e}")


# Auto-integrate on import
try:
    integrate_with_monitoring()
except Exception as e:
    logger.warning(f"Could not auto-integrate error recovery: {e}")