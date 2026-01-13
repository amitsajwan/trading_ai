"""
Health checking and status monitoring for trading system services.
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import aiohttp
import redis
import pymongo
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))
from config import get_config

logger = logging.getLogger(__name__)


class HealthChecker:
    """Checks health of all trading system services and dependencies."""

    def __init__(self):
        self.config = get_config()
        self.last_check = {}
        self.check_interval = 30  # seconds
        self.timeout = 10  # seconds

        # Service endpoints to check
        self.services = {
            'market_data': f"http://localhost:{self.config.market_data_port}/health",
            'news': f"http://localhost:{self.config.news_port}/health",
            'engine': f"http://localhost:{self.config.engine_port}/health",
            'user': f"http://localhost:{getattr(self.config, 'user_port', 8007)}/health",  # Default to 8007 if not set
            'dashboard': f"http://localhost:{self.config.dashboard_port}/health"
        }

    async def check_service_health(self, service_name: str, url: str) -> Dict[str, Any]:
        """Check health of a single service."""
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(url) as response:
                    response_time = time.time() - start_time

                    if response.status == 200:
                        try:
                            data = await response.json()
                            return {
                                'service': service_name,
                                'status': 'healthy',
                                'response_time': response_time,
                                'timestamp': datetime.now().isoformat(),
                                'details': data
                            }
                        except:
                            return {
                                'service': service_name,
                                'status': 'healthy',
                                'response_time': response_time,
                                'timestamp': datetime.now().isoformat()
                            }
                    else:
                        return {
                            'service': service_name,
                            'status': 'unhealthy',
                            'response_time': response_time,
                            'timestamp': datetime.now().isoformat(),
                            'error': f'HTTP {response.status}'
                        }

        except asyncio.TimeoutError:
            return {
                'service': service_name,
                'status': 'unhealthy',
                'response_time': self.timeout,
                'timestamp': datetime.now().isoformat(),
                'error': 'timeout'
            }
        except Exception as e:
            response_time = time.time() - start_time
            return {
                'service': service_name,
                'status': 'unhealthy',
                'response_time': response_time,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    def check_infrastructure(self) -> Dict[str, Any]:
        """Check infrastructure components (Redis, MongoDB)."""
        results = {
            'timestamp': datetime.now().isoformat(),
            'components': {}
        }

        # Check Redis
        try:
            redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=0,
                decode_responses=True,
                socket_timeout=5
            )
            redis_client.ping()
            results['components']['redis'] = {
                'status': 'healthy',
                'details': f'Connected to {self.config.redis_host}:{self.config.redis_port}'
            }
        except Exception as e:
            results['components']['redis'] = {
                'status': 'unhealthy',
                'error': str(e)
            }

        # Check MongoDB
        try:
            mongo_client = pymongo.MongoClient(self.config.mongodb_uri, serverSelectionTimeoutMS=5000)
            mongo_client.admin.command('ping')
            results['components']['mongodb'] = {
                'status': 'healthy',
                'details': f'Connected to {self.config.mongodb_uri}'
            }
            mongo_client.close()
        except Exception as e:
            results['components']['mongodb'] = {
                'status': 'unhealthy',
                'error': str(e)
            }

        return results

    async def check_all_services(self) -> Dict[str, Any]:
        """Check health of all services and infrastructure."""
        logger.info("Performing comprehensive health check...")

        # Check infrastructure
        infra_results = self.check_infrastructure()

        # Check services concurrently
        service_tasks = []
        for service_name, url in self.services.items():
            task = self.check_service_health(service_name, url)
            service_tasks.append(task)

        service_results = await asyncio.gather(*service_tasks, return_exceptions=True)

        # Process results
        services_status = {}
        for i, result in enumerate(service_results):
            service_name = list(self.services.keys())[i]
            if isinstance(result, Exception):
                services_status[service_name] = {
                    'service': service_name,
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'error': str(result)
                }
            else:
                services_status[service_name] = result

        # Overall status
        infra_healthy = all(
            comp['status'] == 'healthy'
            for comp in infra_results['components'].values()
        )

        services_healthy = all(
            service['status'] == 'healthy'
            for service in services_status.values()
        )

        overall_status = 'healthy' if (infra_healthy and services_healthy) else 'degraded'

        health_report = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': overall_status,
            'infrastructure': infra_results,
            'services': services_status,
            'summary': {
                'infrastructure_healthy': infra_healthy,
                'services_healthy': services_healthy,
                'total_services': len(self.services),
                'healthy_services': sum(1 for s in services_status.values() if s['status'] == 'healthy')
            }
        }

        self.last_check = health_report

        # Log summary
        logger.info(f"Health check complete: {overall_status}")
        logger.info(f"Infrastructure: {'✓' if infra_healthy else '✗'}")
        logger.info(f"Services: {health_report['summary']['healthy_services']}/{health_report['summary']['total_services']} healthy")

        return health_report

    def get_last_health_check(self) -> Optional[Dict[str, Any]]:
        """Get the last health check results."""
        return self.last_check if self.last_check else None

    def is_system_healthy(self) -> bool:
        """Check if the overall system is healthy."""
        if not self.last_check:
            return False

        return self.last_check.get('overall_status') == 'healthy'

    async def continuous_health_monitoring(self):
        """Run continuous health monitoring."""
        logger.info("Starting continuous health monitoring...")

        while True:
            try:
                await self.check_all_services()

                # Alert if system is unhealthy
                if not self.is_system_healthy():
                    logger.warning("System health check failed - some components may be degraded")

            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")

            await asyncio.sleep(self.check_interval)


# Global health checker instance
health_checker = HealthChecker()


def get_health_checker() -> HealthChecker:
    """Get the global health checker instance."""
    return health_checker