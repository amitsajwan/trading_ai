#!/usr/bin/env python3
"""
System Health Monitor - Continuous monitoring and alerting for the trading system.

This script provides real-time monitoring of all system components, data integrity,
and performance metrics with configurable alerting.
"""

import time
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
import requests
import redis
import os
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('system_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SystemMonitor:
    """Comprehensive system health monitoring and alerting."""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.redis_client = redis.Redis(
            host=self.config.get('redis_host', 'localhost'),
            port=self.config.get('redis_port', 6379),
            decode_responses=True
        )

        # Monitoring state
        self.last_alert_time = {}
        self.alert_cooldown = self.config.get('alert_cooldown_minutes', 5) * 60  # seconds

        # Service endpoints
        self.services = {
            'market_data_api': f"http://localhost:{self.config.get('market_data_port', 8004)}",
            'news_api': f"http://localhost:{self.config.get('news_api_port', 8005)}",
            'dashboard': f"http://localhost:{self.config.get('dashboard_port', 8888)}",
            'websocket_gateway': f"http://localhost:{self.config.get('websocket_port', 8889)}"
        }

    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load monitoring configuration."""
        default_config = {
            'check_interval_seconds': 30,
            'alert_cooldown_minutes': 5,
            'market_data_port': 8004,
            'news_api_port': 8005,
            'dashboard_port': 8888,
            'websocket_port': 8889,
            'redis_host': 'localhost',
            'redis_port': 6379,
            'enable_alerts': True,
            'alert_webhook_url': None,
            'critical_services': ['market_data_api', 'redis'],
            'data_validation_enabled': True,
            'performance_monitoring': True
        }

        if config_path and Path(config_path).exists():
            try:
                with open(config_path, 'r') as f:
                    loaded_config = json.load(f)
                    default_config.update(loaded_config)
            except Exception as e:
                logger.error(f"Failed to load config from {config_path}: {e}")

        return default_config

    def run_continuous_monitoring(self):
        """Run continuous monitoring loop."""
        logger.info("Starting continuous system monitoring...")

        while True:
            try:
                self._perform_health_check()
                time.sleep(self.config['check_interval_seconds'])
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                time.sleep(10)  # Brief pause before retrying

    def _perform_health_check(self):
        """Perform comprehensive health check of all system components."""
        timestamp = datetime.now(timezone.utc)
        health_report = {
            'timestamp': timestamp.isoformat(),
            'overall_status': 'healthy',
            'services': {},
            'data_integrity': {},
            'performance': {},
            'issues': []
        }

        # Check Redis connectivity
        redis_healthy = self._check_redis_health()
        health_report['services']['redis'] = 'healthy' if redis_healthy else 'unhealthy'

        # Check service health
        for service_name, base_url in self.services.items():
            service_status = self._check_service_health(service_name, base_url)
            health_report['services'][service_name] = service_status

        # Data integrity checks (only if Redis is healthy)
        if redis_healthy and self.config['data_validation_enabled']:
            data_integrity = self._check_data_integrity()
            health_report['data_integrity'] = data_integrity

        # Performance monitoring
        if self.config['performance_monitoring']:
            performance = self._check_performance_metrics()
            health_report['performance'] = performance

        # Determine overall status
        critical_services = self.config['critical_services']
        critical_failures = []

        for service in critical_services:
            if service == 'redis':
                if not redis_healthy:
                    critical_failures.append(f'Redis connection failed')
            elif service in health_report['services']:
                if health_report['services'][service] != 'healthy':
                    critical_failures.append(f'{service} unhealthy')

        # Check data integrity issues
        if 'data_integrity' in health_report:
            for check_name, check_result in health_report['data_integrity'].items():
                if isinstance(check_result, dict) and not check_result.get('valid', True):
                    critical_failures.extend(check_result.get('issues', []))

        if critical_failures:
            health_report['overall_status'] = 'critical' if len(critical_failures) > 2 else 'degraded'
            health_report['issues'] = critical_failures

        # Log and alert
        self._log_health_report(health_report)

        if health_report['overall_status'] != 'healthy' and self.config['enable_alerts']:
            self._send_alert(health_report)

        return health_report

    def _check_redis_health(self) -> bool:
        """Check Redis connectivity and basic operations."""
        try:
            self.redis_client.ping()
            # Test basic operations
            self.redis_client.setex('health_check', 60, 'ok')
            value = self.redis_client.get('health_check')
            return value == 'ok'
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    def _check_service_health(self, service_name: str, base_url: str) -> str:
        """Check individual service health."""
        try:
            # Basic health check
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code == 200:
                # For market data API, also check detailed health
                if service_name == 'market_data_api' and self.config['data_validation_enabled']:
                    detailed_response = requests.get(f"{base_url}/health/detailed", timeout=10)
                    if detailed_response.status_code == 200:
                        detailed_data = detailed_response.json()
                        if detailed_data.get('summary', {}).get('overall_status') == 'unhealthy':
                            return 'degraded'
                return 'healthy'
            else:
                return f'error_{response.status_code}'
        except requests.exceptions.Timeout:
            return 'timeout'
        except requests.exceptions.ConnectionError:
            return 'unreachable'
        except Exception as e:
            logger.error(f"Service health check failed for {service_name}: {e}")
            return 'error'

    def _check_data_integrity(self) -> Dict[str, Any]:
        """Check data integrity across the system."""
        integrity_report = {}

        try:
            from market_data.src.market_data.data_validator import get_data_validator
            validator = get_data_validator(self.redis_client)

            # Check data for configured instrument
            instrument = os.getenv('INSTRUMENT_SYMBOL', 'BANKNIFTY26JANFUT')

            # OHLC data integrity
            ohlc_validation = validator.validate_ohlc_data(instrument, '1min')
            integrity_report['ohlc_data'] = ohlc_validation

            # Technical indicators integrity
            indicators_validation = validator.validate_technical_indicators(instrument)
            integrity_report['technical_indicators'] = indicators_validation

            # System-wide health
            system_health = validator.validate_system_health()
            integrity_report['system_health'] = system_health

        except Exception as e:
            logger.error(f"Data integrity check failed: {e}")
            integrity_report['error'] = str(e)

        return integrity_report

    def _check_performance_metrics(self) -> Dict[str, Any]:
        """Check system performance metrics."""
        metrics = {}

        try:
            # Redis memory usage
            redis_info = self.redis_client.info('memory')
            metrics['redis_memory_used'] = redis_info.get('used_memory_human', 'unknown')

            # Data counts
            ohlc_count = len(self.redis_client.keys('ohlc:*'))
            indicators_count = len(self.redis_client.keys('indicators:*'))
            metrics['data_counts'] = {
                'ohlc_bars': ohlc_count,
                'indicators': indicators_count
            }

            # Recent activity (keys modified in last 5 minutes)
            recent_ohlc = self._count_recent_keys('ohlc:*', 300)
            recent_indicators = self._count_recent_keys('indicators:*', 300)
            metrics['recent_activity'] = {
                'ohlc_updates_last_5min': recent_ohlc,
                'indicator_updates_last_5min': recent_indicators
            }

        except Exception as e:
            logger.error(f"Performance metrics check failed: {e}")
            metrics['error'] = str(e)

        return metrics

    def _count_recent_keys(self, pattern: str, seconds: int) -> int:
        """Count keys modified within the last N seconds."""
        try:
            keys = self.redis_client.keys(pattern)
            recent_count = 0

            for key in keys[:100]:  # Sample first 100 keys
                # This is approximate - in production you'd want more sophisticated tracking
                ttl = self.redis_client.ttl(key)
                if ttl > 0 and ttl < (86400 - seconds):  # Assuming 24h TTL
                    recent_count += 1

            return recent_count
        except Exception:
            return 0

    def _log_health_report(self, report: Dict[str, Any]):
        """Log health report with appropriate level."""
        status = report['overall_status']
        issues = report.get('issues', [])

        if status == 'healthy':
            logger.info(f"System health: {status}")
        elif status == 'degraded':
            logger.warning(f"System health: {status} - Issues: {issues}")
        else:  # critical
            logger.error(f"System health: {status} - Critical issues: {issues}")

        # Log detailed service status
        for service, service_status in report['services'].items():
            if service_status != 'healthy':
                logger.warning(f"Service {service}: {service_status}")

    def _send_alert(self, report: Dict[str, Any]):
        """Send alert notifications."""
        current_time = time.time()

        # Check cooldown
        last_alert = self.last_alert_time.get('system_health', 0)
        if current_time - last_alert < self.alert_cooldown:
            return  # Too soon for another alert

        # Prepare alert message
        alert_message = {
            'timestamp': report['timestamp'],
            'status': report['overall_status'],
            'issues': report.get('issues', []),
            'services': report['services']
        }

        # Send to configured webhook
        webhook_url = self.config.get('alert_webhook_url')
        if webhook_url:
            try:
                response = requests.post(webhook_url, json=alert_message, timeout=10)
                if response.status_code == 200:
                    logger.info("Alert sent successfully")
                else:
                    logger.error(f"Failed to send alert: HTTP {response.status_code}")
            except Exception as e:
                logger.error(f"Alert sending failed: {e}")

        # Log alert
        logger.warning(f"ALERT: System status {report['overall_status']} - {alert_message}")

        # Update cooldown
        self.last_alert_time['system_health'] = current_time

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive system report."""
        return self._perform_health_check()


def main():
    """Main monitoring function."""
    import argparse

    parser = argparse.ArgumentParser(description='System Health Monitor')
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--once', action='store_true', help='Run single check and exit')
    parser.add_argument('--report', action='store_true', help='Generate and print report')

    args = parser.parse_args()

    monitor = SystemMonitor(args.config)

    if args.report:
        report = monitor.generate_report()
        print(json.dumps(report, indent=2))
    elif args.once:
        report = monitor.generate_report()
        print(f"Overall Status: {report['overall_status']}")
        if report.get('issues'):
            print("Issues:")
            for issue in report['issues']:
                print(f"  - {issue}")
    else:
        monitor.run_continuous_monitoring()


if __name__ == "__main__":
    main()