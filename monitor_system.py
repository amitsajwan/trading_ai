#!/usr/bin/env python3
"""
Comprehensive System Monitoring Script for Zerodha Trading System.

Monitors all services, ports, APIs, and WebSocket connections for 2 hours.
Reports any issues and provides detailed status updates.
"""

import time
import requests
import subprocess
import socket
import json
import sys
from datetime import datetime, timedelta
import threading
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('system_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SystemMonitor:
    def __init__(self):
        self.services = {
            'market_data': {
                'port': 8004,
                'health_url': 'http://localhost:8004/health',
                'api_endpoints': [
                    'http://localhost:8004/api/v1/market/tick/BANKNIFTY',
                    'http://localhost:8004/api/v1/market/price/BANKNIFTY',
                    'http://localhost:8004/api/v1/technical/indicators/BANKNIFTY'
                ]
            },
            'news': {
                'port': 8005,
                'health_url': 'http://localhost:8005/health',
                'api_endpoints': [
                    'http://localhost:8005/api/v1/news/BANKNIFTY'
                ]
            },
            'engine': {
                'port': 8006,
                'health_url': 'http://localhost:8006/health',
                'api_endpoints': []  # Analyze endpoint requires POST with JSON body
            },
            'user': {
                'port': 8007,
                'health_url': 'http://localhost:8007/health'
            },
            'dashboard': {
                'port': 8888,
                'health_url': 'http://localhost:8888/'
            }
        }

        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(hours=2)
        self.monitoring_active = True
        self.check_interval = 30  # seconds
        self.status_history = []
        self.error_count = {}
        self.last_successful_check = {}

    def check_port_open(self, host, port):
        """Check if a port is open."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def check_http_endpoint(self, url, timeout=10):
        """Check HTTP endpoint health."""
        try:
            response = requests.get(url, timeout=timeout)
            return response.status_code, response.text[:200] if response.status_code != 200 else None
        except requests.exceptions.RequestException as e:
            return None, str(e)

    def check_websocket_gateway(self):
        """Check WebSocket gateway status."""
        try:
            # Try to connect to WebSocket health endpoint if available
            ws_health_url = "http://localhost:8889/health"
            status, error = self.check_http_endpoint(ws_health_url)
            if status == 200:
                return True, None
            else:
                return False, f"WS Gateway health check failed: {error}"
        except Exception as e:
            return False, str(e)

    def check_redis_connection(self):
        """Check Redis connectivity."""
        try:
            import redis
            client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            client.ping()
            # Check if we have market data
            keys = client.keys('tick:BANKNIFTY*')
            return True, f"Redis OK, {len(keys)} tick records"
        except Exception as e:
            return False, str(e)

    def perform_comprehensive_check(self):
        """Perform comprehensive system check."""
        timestamp = datetime.now()
        status_report = {
            'timestamp': timestamp.isoformat(),
            'services': {},
            'redis': {},
            'websocket': {},
            'overall_status': 'HEALTHY'
        }

        issues = []

        # Check Redis first (critical dependency)
        redis_ok, redis_msg = self.check_redis_connection()
        status_report['redis'] = {
            'status': 'OK' if redis_ok else 'ERROR',
            'message': redis_msg
        }
        if not redis_ok:
            issues.append(f"Redis: {redis_msg}")
            status_report['overall_status'] = 'ERROR'

        # Check each service
        for service_name, service_config in self.services.items():
            service_status = {
                'port_open': False,
                'health_ok': False,
                'api_endpoints': {},
                'issues': []
            }

            # Check port
            port_open = self.check_port_open('localhost', service_config['port'])
            service_status['port_open'] = port_open

            if not port_open:
                service_status['issues'].append(f"Port {service_config['port']} not open")
                issues.append(f"{service_name}: Port {service_config['port']} not accessible")
                status_report['overall_status'] = 'ERROR'
            else:
                # Check health endpoint
                health_status, health_error = self.check_http_endpoint(service_config['health_url'])
                service_status['health_ok'] = health_status == 200

                if health_status != 200:
                    service_status['issues'].append(f"Health check failed: {health_error}")
                    issues.append(f"{service_name}: Health check failed ({health_status})")
                    status_report['overall_status'] = 'ERROR'

                # Check API endpoints
                for endpoint in service_config.get('api_endpoints', []):
                    api_status, api_error = self.check_http_endpoint(endpoint)
                    service_status['api_endpoints'][endpoint] = {
                        'status': api_status,
                        'error': api_error
                    }

                    if api_status != 200:
                        service_status['issues'].append(f"API {endpoint} failed: {api_error}")
                        issues.append(f"{service_name}: API endpoint {endpoint} failed")
                        status_report['overall_status'] = 'ERROR'

            status_report['services'][service_name] = service_status

        # Check WebSocket gateway
        ws_ok, ws_error = self.check_websocket_gateway()
        status_report['websocket'] = {
            'status': 'OK' if ws_ok else 'ERROR',
            'message': ws_error
        }
        if not ws_ok:
            issues.append(f"WebSocket Gateway: {ws_error}")
            status_report['overall_status'] = 'ERROR'

        # Update error tracking
        for issue in issues:
            service = issue.split(':')[0]
            self.error_count[service] = self.error_count.get(service, 0) + 1

        # Update last successful check
        if status_report['overall_status'] == 'HEALTHY':
            for service in self.services:
                self.last_successful_check[service] = timestamp

        status_report['issues'] = issues
        self.status_history.append(status_report)

        return status_report

    def print_status_report(self, report):
        """Print formatted status report."""
        print("\n" + "="*80)
        print(f"System Status Check - {report['timestamp']}")
        print("="*80)
        print(f"Overall Status: {report['overall_status']}")

        # Redis status
        redis_status = report['redis']
        print(f"Redis: {redis_status['status']} - {redis_status['message']}")

        # Services status
        for service_name, service_status in report['services'].items():
            port_status = "[OK]" if service_status['port_open'] else "[FAIL]"
            health_status = "[OK]" if service_status['health_ok'] else "[FAIL]"
            print(f"{port_status} {service_name}: Port {self.services[service_name]['port']} {health_status} Health")

            if service_status['issues']:
                for issue in service_status['issues']:
                    print(f"   WARNING: {issue}")

        # WebSocket status
        ws_status = report['websocket']
        ws_indicator = "[OK]" if ws_status['status'] == 'OK' else "[FAIL]"
        print(f"{ws_indicator} WebSocket Gateway: {ws_status['message'] or 'OK'}")

        if report['issues']:
            print(f"\nISSUES FOUND: {len(report['issues'])}")
            for issue in report['issues']:
                print(f"   • {issue}")
        else:
            print("\nAll systems operational!")

        # Error summary
        if self.error_count:
            print("\n📈 Error Summary:")
            for service, count in self.error_count.items():
                last_success = self.last_successful_check.get(service)
                if last_success:
                    time_since = datetime.now() - last_success
                    print(f"   • {service}: {count} errors (last OK: {time_since.seconds}s ago)")
                else:
                    print(f"   • {service}: {count} errors (never OK)")

    def run_monitoring_loop(self):
        """Run the main monitoring loop."""
        logger.info("Starting comprehensive system monitoring for 2 hours...")

        check_count = 0
        while self.monitoring_active and datetime.now() < self.end_time:
            check_count += 1
            logger.info(f"Performing check #{check_count}")

            try:
                report = self.perform_comprehensive_check()
                self.print_status_report(report)

                # Log to file
                with open('monitoring_report.json', 'a') as f:
                    f.write(json.dumps(report) + '\n')

            except Exception as e:
                logger.error(f"Monitoring check failed: {e}")

            # Wait for next check
            time.sleep(self.check_interval)

        logger.info("Monitoring completed!")
        self.generate_final_report()

    def generate_final_report(self):
        """Generate comprehensive final report."""
        total_checks = len(self.status_history)
        healthy_checks = sum(1 for r in self.status_history if r['overall_status'] == 'HEALTHY')
        health_percentage = (healthy_checks / total_checks * 100) if total_checks > 0 else 0

        print("\n" + "="*100)
        print("FINAL MONITORING REPORT - 2 Hour System Test")
        print("="*100)
        print(f"Monitoring Duration: {datetime.now() - self.start_time}")
        print(f"Total Checks: {total_checks}")
        print(".1f")
        print(f"System Health: {'EXCELLENT' if health_percentage > 95 else 'GOOD' if health_percentage > 80 else 'FAIR' if health_percentage > 60 else 'POOR'}")

        if self.error_count:
            print("\nError Summary:")
            for service, count in sorted(self.error_count.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_checks * 100)
                print(".1f")

        # Service uptime analysis
        print("\nService Uptime Analysis:")
        for service in self.services:
            last_success = self.last_successful_check.get(service)
            if last_success:
                uptime = datetime.now() - self.start_time
                print(".1f")
            else:
                print(f"   • {service}: NEVER successfully checked")

        if health_percentage > 90:
            print("\nCONCLUSION: System is PRODUCTION READY!")
            print("   [OK] Excellent stability and reliability")
            print("   [OK] All critical components functioning")
            print("   [OK] Ready for 24/7 operation")
        else:
            print("\nCONCLUSION: System needs attention")
            print("   [WARN] Investigate failing components")
            print("   [WARN] Check error logs for root causes")
            print("   [WARN] Address stability issues before production")

        print(f"\n📄 Detailed logs saved to: system_monitor.log, monitoring_report.json")

def main():
    monitor = SystemMonitor()

    # Start monitoring in background thread
    monitoring_thread = threading.Thread(target=monitor.run_monitoring_loop)
    monitoring_thread.daemon = True
    monitoring_thread.start()

    try:
        # Keep main thread alive
        while monitoring_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Monitoring interrupted by user")
        monitor.monitoring_active = False
        monitoring_thread.join(timeout=10)
        monitor.generate_final_report()

if __name__ == "__main__":
    main()