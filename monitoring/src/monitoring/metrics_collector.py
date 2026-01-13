"""
Metrics collection and aggregation for trading system monitoring.
"""

import time
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))
from config import get_config

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and aggregates metrics from various system components."""

    def __init__(self):
        self.config = get_config()
        self.metrics_store = defaultdict(list)
        self.aggregates = {}
        self._lock = threading.Lock()

        # Start metrics aggregation thread
        if self.config.enable_performance_monitoring:
            self._start_aggregation_thread()

    def _start_aggregation_thread(self):
        """Start background thread for metrics aggregation."""
        def aggregate_metrics():
            while True:
                try:
                    self._perform_aggregation()
                except Exception as e:
                    logger.error(f"Error in metrics aggregation: {e}")

                time.sleep(self.config.performance_log_interval)

        thread = threading.Thread(target=aggregate_metrics, daemon=True)
        thread.start()
        logger.info("Metrics aggregation thread started")

    def _perform_aggregation(self):
        """Perform periodic metrics aggregation."""
        with self._lock:
            # Aggregate metrics for the last interval
            cutoff_time = datetime.now() - timedelta(seconds=self.config.performance_log_interval)

            for metric_name, readings in self.metrics_store.items():
                # Filter recent readings
                recent_readings = [
                    r for r in readings
                    if datetime.fromisoformat(r['timestamp']) > cutoff_time
                ]

                if recent_readings:
                    self._aggregate_metric(metric_name, recent_readings)

            # Log aggregated metrics
            self._log_aggregated_metrics()

    def _aggregate_metric(self, name: str, readings: List[Dict[str, Any]]):
        """Aggregate readings for a specific metric."""
        try:
            values = [r.get('value', 0) for r in readings if 'value' in r]

            if values:
                self.aggregates[name] = {
                    'timestamp': datetime.now().isoformat(),
                    'count': len(values),
                    'sum': sum(values),
                    'avg': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'period_seconds': self.config.performance_log_interval
                }

                # Calculate rate metrics if applicable
                if 'rate' in name.lower():
                    self.aggregates[name]['rate_per_second'] = len(values) / self.config.performance_log_interval
                elif 'error' in name.lower() or 'failure' in name.lower():
                    self.aggregates[name]['error_rate'] = len(values) / self.config.performance_log_interval

        except Exception as e:
            logger.error(f"Error aggregating metric {name}: {e}")

    def _log_aggregated_metrics(self):
        """Log aggregated metrics."""
        if not self.aggregates:
            return

        logger.info("METRICS AGGREGATION REPORT")
        logger.info("-" * 40)

        for name, data in self.aggregates.items():
            logger.info(f"{name}: count={data['count']}, avg={data['avg']:.2f}, "
                       f"min={data['min']:.2f}, max={data['max']:.2f}")

        logger.info("-" * 40)

    def collect_metric(self, name: str, value: float, tags: Optional[Dict[str, Any]] = None,
                      metadata: Optional[Dict[str, Any]] = None):
        """Collect a metric reading."""
        reading = {
            'timestamp': datetime.now().isoformat(),
            'value': value,
            'tags': tags or {},
            'metadata': metadata or {}
        }

        with self._lock:
            self.metrics_store[name].append(reading)

            # Keep only recent readings (last 24 hours worth)
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.metrics_store[name] = [
                r for r in self.metrics_store[name]
                if datetime.fromisoformat(r['timestamp']) > cutoff_time
            ]

        logger.debug(f"Collected metric: {name} = {value}")

    def collect_counter(self, name: str, increment: int = 1, tags: Optional[Dict[str, Any]] = None):
        """Increment a counter metric."""
        # For counters, we store the increment value
        self.collect_metric(f"{name}_counter", increment, tags)

    def collect_timer(self, name: str, duration_seconds: float, tags: Optional[Dict[str, Any]] = None):
        """Record a timing metric."""
        self.collect_metric(f"{name}_duration", duration_seconds, tags)

    def collect_gauge(self, name: str, value: float, tags: Optional[Dict[str, Any]] = None):
        """Record a gauge metric (point-in-time value)."""
        self.collect_metric(f"{name}_gauge", value, tags)

    def get_metric_stats(self, name: str, hours: int = 1) -> Optional[Dict[str, Any]]:
        """Get statistics for a metric over the specified time period."""
        with self._lock:
            readings = self.metrics_store.get(name, [])
            if not readings:
                return None

            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_readings = [
                r for r in readings
                if datetime.fromisoformat(r['timestamp']) > cutoff_time
            ]

            if not recent_readings:
                return None

            values = [r['value'] for r in recent_readings]

            return {
                'name': name,
                'count': len(values),
                'sum': sum(values),
                'avg': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'period_hours': hours,
                'latest_value': values[-1],
                'latest_timestamp': recent_readings[-1]['timestamp']
            }

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metrics and aggregates."""
        with self._lock:
            return {
                'metrics_store': dict(self.metrics_store),
                'aggregates': dict(self.aggregates),
                'collection_timestamp': datetime.now().isoformat()
            }

    def export_metrics(self, format: str = 'json') -> str:
        """Export metrics in the specified format."""
        data = self.get_all_metrics()

        if format.lower() == 'json':
            return json.dumps(data, indent=2, default=str)
        else:
            # Simple text format
            lines = ["METRICS EXPORT", "=" * 50]

            for name, readings in data['metrics_store'].items():
                lines.append(f"\n{name}:")
                for reading in readings[-10:]:  # Last 10 readings
                    lines.append(f"  {reading['timestamp']}: {reading['value']}")

            if data['aggregates']:
                lines.append("\nAGGREGATES:")
                for name, agg in data['aggregates'].items():
                    lines.append(f"  {name}: {agg}")

            return "\n".join(lines)


# Global metrics collector instance
metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return metrics_collector