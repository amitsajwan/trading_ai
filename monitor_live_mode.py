#!/usr/bin/env python3
"""
Continuous Live Mode Monitor

Runs in background and continuously validates:
- Prices are in realistic range
- WebSocket is connected
- No mock data interference
- Services are healthy

Alerts if any issues detected.

Usage:
    python monitor_live_mode.py
"""

import redis
import time
import subprocess
from datetime import datetime
from typing import Dict, Any

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'

# Price sanity ranges
BANKNIFTY_MIN = 50000
BANKNIFTY_MAX = 70000

# Alert thresholds
MAX_PRICE_AGE_SECONDS = 60  # Alert if no update in 60 seconds
STALE_PRICE_THRESHOLD_MINUTES = 5  # Alert if same price for 5 minutes


class LiveModeMonitor:
    """Continuously monitors live mode for issues."""
    
    def __init__(self):
        self.redis = redis.Redis(host='localhost', port=6380, decode_responses=True)
        self.last_price = None
        self.last_price_time = None
        self.same_price_count = 0
        self.alert_count = 0
        
    def run(self):
        """Main monitoring loop."""
        print(f"{BOLD}Live Mode Monitor Started{RESET}")
        print(f"Monitoring for data quality issues...")
        print(f"Press Ctrl+C to stop\n")
        
        check_interval = 10  # seconds
        
        try:
            while True:
                status = self._check_system()
                self._print_status(status)
                
                if not status['all_ok']:
                    self.alert_count += 1
                    self._send_alert(status)
                else:
                    self.alert_count = 0
                
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Monitor stopped{RESET}")
    
    def _check_system(self) -> Dict[str, Any]:
        """Run all checks and return status."""
        status = {
            'timestamp': datetime.now(),
            'all_ok': True,
            'issues': []
        }
        
        # Check 1: Price sanity
        try:
            price_str = self.redis.get("indicators:BANKNIFTY26FEBFUT:current_price")
            if price_str:
                price = float(price_str)
                status['price'] = price
                
                if price < BANKNIFTY_MIN:
                    status['all_ok'] = False
                    status['issues'].append(
                        f"CRITICAL: Price {price:.2f} below {BANKNIFTY_MIN} - LIKELY MOCK DATA!"
                    )
                elif price > BANKNIFTY_MAX:
                    status['all_ok'] = False
                    status['issues'].append(
                        f"WARNING: Price {price:.2f} above {BANKNIFTY_MAX}"
                    )
                
                # Check for stale price
                if self.last_price == price:
                    self.same_price_count += 1
                    if self.same_price_count > (STALE_PRICE_THRESHOLD_MINUTES * 60 / 10):
                        status['all_ok'] = False
                        status['issues'].append(
                            f"WARNING: Price unchanged for {STALE_PRICE_THRESHOLD_MINUTES}+ minutes"
                        )
                else:
                    self.same_price_count = 0
                    self.last_price = price
            else:
                status['all_ok'] = False
                status['issues'].append("ERROR: No price in Redis")
                status['price'] = None
        except Exception as e:
            status['all_ok'] = False
            status['issues'].append(f"ERROR: Cannot read price: {e}")
            status['price'] = None
        
        # Check 2: WebSocket connection
        try:
            result = subprocess.run(
                ["docker", "logs", "zerodha-websocket-tick-collector-banknifty", "--tail", "10"],
                capture_output=True,
                text=True,
                timeout=5
            )
            logs = result.stdout + result.stderr
            
            if "connected=False" in logs or "403" in logs or "Forbidden" in logs:
                status['all_ok'] = False
                status['issues'].append("CRITICAL: WebSocket disconnected or authentication failed")
                status['websocket'] = 'disconnected'
            elif "Processed tick" in logs:
                status['websocket'] = 'connected'
            else:
                status['websocket'] = 'unknown'
        except Exception as e:
            status['all_ok'] = False
            status['issues'].append(f"ERROR: Cannot check WebSocket: {e}")
            status['websocket'] = 'error'
        
        # Check 3: No mock services
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            containers = result.stdout.lower()
            
            if "mock-publisher" in containers or "mock-options" in containers:
                status['all_ok'] = False
                status['issues'].append("CRITICAL: Mock services detected running!")
                status['mock_running'] = True
            else:
                status['mock_running'] = False
        except Exception as e:
            status['issues'].append(f"WARNING: Cannot check for mock services: {e}")
        
        # Check 4: Historical replay
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=historical-replay", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout.strip():
                status['all_ok'] = False
                status['issues'].append("WARNING: Historical replay service running")
                status['historical_running'] = True
            else:
                status['historical_running'] = False
        except Exception as e:
            status['issues'].append(f"WARNING: Cannot check historical replay: {e}")
        
        return status
    
    def _print_status(self, status: Dict[str, Any]):
        """Print monitoring status."""
        timestamp = status['timestamp'].strftime('%H:%M:%S')
        
        if status['all_ok']:
            icon = f"{GREEN}✓{RESET}"
            price = status.get('price')
            if price:
                print(f"[{timestamp}] {icon} All OK - Price: ₹{price:,.2f} | WebSocket: {status['websocket']}")
            else:
                print(f"[{timestamp}] {icon} All OK - WebSocket: {status['websocket']}")
        else:
            icon = f"{RED}✗{RESET}"
            print(f"\n[{timestamp}] {icon} {RED}{BOLD}ISSUES DETECTED:{RESET}")
            for issue in status['issues']:
                if 'CRITICAL' in issue:
                    print(f"  {RED}► {issue}{RESET}")
                elif 'ERROR' in issue:
                    print(f"  {RED}► {issue}{RESET}")
                else:
                    print(f"  {YELLOW}► {issue}{RESET}")
            print()
    
    def _send_alert(self, status: Dict[str, Any]):
        """Send alert for issues."""
        # For now just print bold alerts
        # Could extend to send emails, Slack notifications, etc.
        if self.alert_count == 1:  # First alert
            print(f"\n{RED}{'=' * 60}{RESET}")
            print(f"{RED}{BOLD}🚨 ALERT: System issue detected!{RESET}")
            print(f"{RED}{'=' * 60}{RESET}\n")


def main():
    """Main entry point."""
    monitor = LiveModeMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
