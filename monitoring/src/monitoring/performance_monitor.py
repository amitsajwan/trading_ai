"""
Performance monitoring for trading system components.
Tracks latency, throughput, and resource usage.
"""

import time
import psutil
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from datetime import datetime
from collections import defaultdict
import threading
import statistics
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))
from config import get_config

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitors performance metrics for trading system components."""

    def __init__(self):
        self.config = get_config()
        self.metrics = defaultdict(list)
        self.start_time = time.time()
        self._lock = threading.Lock()

        # System resource tracking
        self.system_metrics = {
            'cpu_percent': [],
            'memory_percent': [],
            'disk_usage': [],
            'network_connections': []
        }

        # Start background monitoring
        if self.config.enable_performance_monitoring:
            self._start_background_monitoring()

    def _start_background_monitoring(self):
        """Start background thread for system monitoring."""
        def monitor_system():
            while True:
                try:
                    # CPU usage
                    cpu_percent = psutil.cpu_percent(interval=1)
                    with self._lock:
                        self.system_metrics['cpu_percent'].append((time.time(), cpu_percent))
                        # Keep only last 100 readings
                        if len(self.system_metrics['cpu_percent']) > 100:
                            self.system_metrics['cpu_percent'] = self.system_metrics['cpu_percent'][-100:]

                    # Memory usage
                    memory = psutil.virtual_memory()
                    with self._lock:
                        self.system_metrics['memory_percent'].append((time.time(), memory.percent))
                        if len(self.system_metrics['memory_percent']) > 100:
                            self.system_metrics['memory_percent'] = self.system_metrics['memory_percent'][-100:]

                    # Disk usage
                    disk = psutil.disk_usage('/')
                    with self._lock:
                        self.system_metrics['disk_usage'].append((time.time(), disk.percent))
                        if len(self.system_metrics['disk_usage']) > 100:
                            self.system_metrics['disk_usage'] = self.system_metrics['disk_usage'][-100:]

                    # Network connections
                    connections = len(psutil.net_connections())
                    with self._lock:
                        self.system_metrics['network_connections'].append((time.time(), connections))
                        if len(self.system_metrics['network_connections']) > 100:
                            self.system_metrics['network_connections'] = self.system_metrics['network_connections'][-100:]

                except Exception as e:
                    logger.error(f"Error in system monitoring: {e}")

                time.sleep(60)  # Update every minute

        thread = threading.Thread(target=monitor_system, daemon=True)
        thread.start()
        logger.info("Performance monitoring background thread started")

    def time_function(self, name: str) -> Callable:
        """Decorator to time function execution."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time

                    with self._lock:
                        self.metrics[name].append({
                            'timestamp': datetime.now().isoformat(),
                            'duration': execution_time,
                            'success': True
                        })

                        # Keep only last 1000 readings per metric
                        if len(self.metrics[name]) > 1000:
                            self.metrics[name] = self.metrics[name][-1000:]

                    logger.debug(f"Function {name} executed in {execution_time:.4f}s")
                    return result

                except Exception as e:
                    execution_time = time.time() - start_time

                    with self._lock:
                        self.metrics[name].append({
                            'timestamp': datetime.now().isoformat(),
                            'duration': execution_time,
                            'success': False,
                            'error': str(e)
                        })

                        if len(self.metrics[name]) > 1000:
                            self.metrics[name] = self.metrics[name][-1000:]

                    logger.error(f"Function {name} failed after {execution_time:.4f}s: {e}")
                    raise

            return wrapper
        return decorator

    def record_metric(self, name: str, value: float, tags: Optional[Dict[str, Any]] = None):
        """Record a custom metric."""
        metric_data = {
            'timestamp': datetime.now().isoformat(),
            'value': value,
            'tags': tags or {}
        }

        with self._lock:
            self.metrics[name].append(metric_data)
            if len(self.metrics[name]) > 1000:
                self.metrics[name] = self.metrics[name][-1000:]

        logger.debug(f"Recorded metric {name}: {value}")

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all collected metrics."""
        with self._lock:
            summary = {
                'uptime_seconds': time.time() - self.start_time,
                'function_metrics': {},
                'system_metrics': {},
                'custom_metrics': {}
            }

            # Function timing metrics
            for func_name, readings in self.metrics.items():
                if not readings:
                    continue

                # Check if it's function timing data (has 'duration' key)
                if isinstance(readings[0], dict) and 'duration' in readings[0]:
                    durations = [r['duration'] for r in readings if r.get('success', True)]
                    success_count = sum(1 for r in readings if r.get('success', True))
                    total_count = len(readings)

                    if durations:
                        summary['function_metrics'][func_name] = {
                            'calls': total_count,
                            'successful_calls': success_count,
                            'success_rate': success_count / total_count if total_count > 0 else 0,
                            'avg_duration': statistics.mean(durations),
                            'min_duration': min(durations),
                            'max_duration': max(durations),
                            'p95_duration': statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations)
                        }
                else:
                    # Custom metrics
                    values = [r['value'] for r in readings]
                    if values:
                        summary['custom_metrics'][func_name] = {
                            'count': len(values),
                            'avg_value': statistics.mean(values),
                            'min_value': min(values),
                            'max_value': max(values),
                            'current_value': values[-1]
                        }

            # System metrics
            for metric_name, readings in self.system_metrics.items():
                if readings:
                    values = [r[1] for r in readings]
                    summary['system_metrics'][metric_name] = {
                        'current': values[-1],
                        'avg': statistics.mean(values),
                        'min': min(values),
                        'max': max(values)
                    }

            return summary

    def log_performance_report(self):
        """Log a performance report."""
        summary = self.get_metrics_summary()

        logger.info("=" * 60)
        logger.info("PERFORMANCE REPORT")
        logger.info("=" * 60)

        logger.info(f"System uptime: {summary['uptime_seconds']:.2f} seconds")

        if summary['system_metrics']:
            logger.info("SYSTEM METRICS:")
            for name, data in summary['system_metrics'].items():
                logger.info(f"  {name}: {data['current']:.2f} (avg: {data['avg']:.2f})")

        if summary['function_metrics']:
            logger.info("FUNCTION PERFORMANCE:")
            for func_name, data in summary['function_metrics'].items():
                logger.info(f"  {func_name}:")
                logger.info(f"    Calls: {data['calls']} (success: {data['success_rate']:.1%})")
                logger.info(f"    Duration: {data['avg_duration']:.4f}s avg, {data['max_duration']:.4f}s max")

        if summary['custom_metrics']:
            logger.info("CUSTOM METRICS:")
            for name, data in summary['custom_metrics'].items():
                logger.info(f"  {name}: {data['current_value']:.2f} (avg: {data['avg_value']:.2f})")

        logger.info("=" * 60)


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    return performance_monitor