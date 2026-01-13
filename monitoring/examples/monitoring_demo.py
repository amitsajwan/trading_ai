#!/usr/bin/env python3
"""
Demonstration of monitoring and production hardening features.
"""

import asyncio
import time
import logging
from monitoring import (
    get_performance_monitor, get_metrics_collector,
    get_health_checker, get_error_handler, get_rate_limiter
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@get_performance_monitor().time_function("demo_function")
def demo_function(duration: float = 0.1):
    """Demo function with performance monitoring."""
    time.sleep(duration)
    return f"Completed in {duration}s"


async def demo_async_function():
    """Demo async function with error handling."""
    error_handler = get_error_handler()

    # Simulate a function that might fail
    def unreliable_function():
        if time.time() % 2 > 1:  # Random failure
            raise Exception("Simulated failure")
        return "Success"

    try:
        result = await error_handler.execute_with_protection_async(
            "demo_operation", unreliable_function
        )
        logger.info(f"Operation succeeded: {result}")
    except Exception as e:
        logger.error(f"Operation failed: {e}")


async def demo_rate_limiting():
    """Demo rate limiting."""
    rate_limiter = get_rate_limiter()

    logger.info("Testing rate limiting...")

    # Create a custom bucket
    rate_limiter.create_bucket("demo_bucket", capacity=5, refill_rate=1.0)

    for i in range(10):
        if rate_limiter.allow("demo_bucket"):
            logger.info(f"Request {i+1}: ALLOWED")
        else:
            logger.info(f"Request {i+1}: RATE LIMITED")
            wait_time = rate_limiter.buckets["demo_bucket"].get_wait_time()
            logger.info(f"Waiting {wait_time:.1f}s for tokens...")
            time.sleep(wait_time + 0.1)  # Wait a bit longer


async def demo_metrics_collection():
    """Demo metrics collection."""
    metrics = get_metrics_collector()

    logger.info("Collecting demo metrics...")

    # Collect various types of metrics
    for i in range(10):
        metrics.collect_gauge("demo_temperature", 20 + i)
        metrics.collect_counter("demo_requests")
        metrics.collect_timer("demo_processing", 0.1 + (i * 0.01))

        time.sleep(0.1)

    # Get metrics summary
    temp_stats = metrics.get_metric_stats("demo_temperature_gauge")
    if temp_stats:
        logger.info(f"Temperature stats: avg={temp_stats['avg']:.1f}, min={temp_stats['min']}, max={temp_stats['max']}")


async def demo_health_check():
    """Demo health checking."""
    health_checker = get_health_checker()

    logger.info("Running health check...")
    health_report = await health_checker.check_all_services()

    logger.info(f"Overall status: {health_report['overall_status']}")
    logger.info(f"Services healthy: {health_report['summary']['healthy_services']}/{health_report['summary']['total_services']}")


async def main():
    """Run all monitoring demos."""
    logger.info("Starting monitoring demonstration...")

    # Demo 1: Performance monitoring
    logger.info("\n=== PERFORMANCE MONITORING ===")
    for i in range(5):
        result = demo_function(0.05 + (i * 0.01))
        logger.info(f"Function call {i+1}: {result}")

    # Demo 2: Error handling and retries
    logger.info("\n=== ERROR HANDLING ===")
    await demo_async_function()

    # Demo 3: Rate limiting
    logger.info("\n=== RATE LIMITING ===")
    await demo_rate_limiting()

    # Demo 4: Metrics collection
    logger.info("\n=== METRICS COLLECTION ===")
    await demo_metrics_collection()

    # Demo 5: Health checking
    logger.info("\n=== HEALTH CHECKING ===")
    await demo_health_check()

    # Final performance report
    logger.info("\n=== PERFORMANCE REPORT ===")
    monitor = get_performance_monitor()
    monitor.log_performance_report()

    logger.info("Monitoring demonstration complete!")


if __name__ == "__main__":
    asyncio.run(main())