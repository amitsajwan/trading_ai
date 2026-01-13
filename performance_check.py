#!/usr/bin/env python3
"""
System performance and health monitoring check.
"""

from monitoring import get_performance_monitor, get_metrics_collector, get_health_checker
import asyncio

async def check_performance():
    """Check system performance and health."""
    print('📈 SYSTEM PERFORMANCE & HEALTH MONITORING')
    print('=' * 50)

    # Get monitors
    perf = get_performance_monitor()
    metrics = get_metrics_collector()
    health = get_health_checker()

    # Performance summary
    summary = perf.get_metrics_summary()
    print('✅ Performance Summary:')
    print(f'   System uptime: {summary["uptime_seconds"]:.0f} seconds')

    if summary['function_metrics']:
        print('   Function performance:')
        for name, data in summary['function_metrics'].items():
            print(f'     • {name}: {data["calls"]} calls, {data["avg_duration"]:.3f}s avg')

    if summary['system_metrics']:
        print('   System resources:')
        for name, data in summary['system_metrics'].items():
            print(f'     • {name}: {data["current"]:.1f} (avg: {data["avg"]:.1f})')

    # Health check
    print('\n❤️ System Health Check:')
    health_report = await health.check_all_services()
    print(f'   Overall status: {health_report["overall_status"]}')
    print(f'   Services healthy: {health_report["summary"]["healthy_services"]}/{health_report["summary"]["total_services"]}')

    # Show service details
    print('   Service details:')
    for service_name, service_data in health_report["services"].items():
        status = service_data["status"]
        emoji = "✅" if status == "healthy" else "❌"
        print(f'     • {service_name}: {emoji} {status}')

    # Metrics export
    print('\n📊 Metrics Collection:')
    all_metrics = metrics.get_all_metrics()
    print(f'   Metrics stored: {len(all_metrics["metrics_store"])} types')
    print(f'   Aggregates: {len(all_metrics["aggregates"])} summaries')

    print('\n✅ Performance monitoring completed')

if __name__ == "__main__":
    asyncio.run(check_performance())