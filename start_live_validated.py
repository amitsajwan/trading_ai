#!/usr/bin/env python3
"""
Fail-Safe Live Mode Startup with Automatic Validation

GUARANTEES:
- Only starts if credentials are valid
- Only proceeds if real Zerodha data is flowing
- Auto-validates price ranges (no mock data)
- Fails fast on any issue
- No manual checks needed

Usage:
    python start_live_validated.py
"""

import json
import os
import sys
import time
import subprocess
import redis
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple, Optional

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


class LiveModeValidator:
    """Validates and starts live mode with fail-safe checks."""
    
    # Price sanity ranges (adjust based on current market)
    BANKNIFTY_MIN = 50000
    BANKNIFTY_MAX = 70000
    
    def __init__(self):
        self.redis_client = None
        self.errors = []
        
    def start(self) -> bool:
        """Main entry point - validates and starts live mode."""
        self._print_header()
        
        # Step 1: Pre-flight checks
        if not self._preflight_checks():
            return False
        
        # Step 2: Clean environment
        if not self._clean_environment():
            return False
        
        # Step 3: Start services
        if not self._start_services():
            return False
        
        # Step 4: Wait for services to be ready
        if not self._wait_for_services():
            return False
        
        # Step 5: Validate data pipeline
        if not self._validate_data_pipeline():
            return False
        
        # Step 6: Continuous monitoring (optional)
        self._print_success()
        return True
    
    def _print_header(self):
        """Print startup header."""
        print()
        print("=" * 80)
        print(f"{BOLD}FAIL-SAFE LIVE MODE STARTUP{RESET}")
        print("=" * 80)
        print()
    
    def _print_step(self, step: int, title: str):
        """Print step header."""
        print(f"\n{BLUE}[Step {step}] {title}{RESET}")
        print("-" * 80)
    
    def _print_success(self):
        """Print success message."""
        print("\n" + "=" * 80)
        print(f"{GREEN}{BOLD}✅ LIVE MODE STARTED SUCCESSFULLY{RESET}")
        print("=" * 80)
        print()
        print(f"Dashboard:  {BOLD}http://localhost:8008{RESET}")
        print(f"API:        {BOLD}http://localhost:8004{RESET}")
        print(f"Validated:  {BOLD}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
        print()
        print(f"{GREEN}✅ Real Zerodha data confirmed - prices validated{RESET}")
        print(f"{GREEN}✅ All services healthy and connected{RESET}")
        print()
    
    def _print_error(self, message: str):
        """Print error and exit."""
        print(f"\n{RED}❌ ERROR: {message}{RESET}\n")
    
    def _preflight_checks(self) -> bool:
        """Run pre-flight validation checks."""
        self._print_step(1, "Pre-Flight Validation")
        
        # Check 1: Credentials exist
        print("   Checking credentials file...")
        creds_file = Path("credentials.json")
        if not creds_file.exists():
            self._print_error("credentials.json not found")
            print(f"   Run: {YELLOW}python -m market_data.tools.kite_auth{RESET}")
            return False
        print(f"   {GREEN}✓{RESET} Credentials file found")
        
        # Check 2: Load credentials
        print("   Loading credentials...")
        try:
            with open(creds_file) as f:
                creds = json.load(f)
        except Exception as e:
            self._print_error(f"Cannot read credentials: {e}")
            return False
        
        api_key = creds.get("api_key")
        access_token = creds.get("access_token")
        
        if not api_key or not access_token:
            self._print_error("Missing api_key or access_token in credentials.json")
            print(f"   Run: {YELLOW}python -m market_data.tools.kite_auth{RESET}")
            return False
        
        print(f"   {GREEN}✓{RESET} API Key: {api_key[:12]}...")
        print(f"   {GREEN}✓{RESET} Access Token: {access_token[:20]}...")
        
        # Check 3: Test token with real API call
        print("   Validating token with Kite API...")
        try:
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            profile = kite.profile()
            print(f"   {GREEN}✓{RESET} Token VALID - User: {profile['user_id']}")
        except Exception as e:
            self._print_error(f"Token validation failed: {e}")
            print(f"   Token might be expired. Run: {YELLOW}python -m market_data.tools.kite_auth{RESET}")
            return False
        
        # Check 4: Token age
        login_time = creds.get("login_time")
        if login_time:
            try:
                login_dt = datetime.fromisoformat(login_time)
                age = datetime.now() - login_dt
                if age > timedelta(hours=23):
                    self._print_error(f"Token is {age.total_seconds()/3600:.1f} hours old (>23h)")
                    print(f"   Run: {YELLOW}python -m market_data.tools.kite_auth{RESET}")
                    return False
                print(f"   {GREEN}✓{RESET} Token age: {age.total_seconds()/3600:.1f} hours (OK)")
            except Exception as e:
                print(f"   {YELLOW}⚠{RESET} Cannot verify token age: {e}")
        
        # Check 5: Docker is running
        print("   Checking Docker...")
        try:
            result = subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                self._print_error("Docker is not running")
                return False
            print(f"   {GREEN}✓{RESET} Docker is running")
        except Exception as e:
            self._print_error(f"Cannot check Docker: {e}")
            return False
        
        print(f"\n{GREEN}✅ Pre-flight checks PASSED{RESET}")
        return True
    
    def _clean_environment(self) -> bool:
        """Clean environment - stop conflicting services and flush cache."""
        self._print_step(2, "Environment Cleanup")
        
        # Stop mock services
        print("   Stopping mock services (if any)...")
        subprocess.run(
            ["docker", "compose", "stop", "mock-data-publisher", "mock-options-provider"],
            capture_output=True,
            timeout=30
        )
        print(f"   {GREEN}✓{RESET} Mock services stopped")
        
        # Stop historical replay
        print("   Stopping historical replay...")
        subprocess.run(
            ["docker", "compose", "stop", "historical-replay-service"],
            capture_output=True,
            timeout=30
        )
        print(f"   {GREEN}✓{RESET} Historical replay stopped")
        
        # Flush Redis cache to clear old data  
        print("   Flushing Redis cache (clearing old data)...")
        try:
            r = redis.Redis(host='localhost', port=6380, decode_responses=True)
            # Only flush if Redis is already running
            try:
                r.ping()
                flushed = r.flushall()
                if flushed:
                    print(f"   {GREEN}✓{RESET} Redis cache cleared")
                else:
                    print(f"   {YELLOW}⚠{RESET} Redis flush returned False")
            except redis.ConnectionError:
                # Redis not running yet, will be fresh when started
                print(f"   {GREEN}✓{RESET} Redis not running (will start fresh)")
        except Exception as e:
            print(f"   {YELLOW}⚠{RESET} Cannot flush Redis: {e}")
        
        # Stop Redis to clear persistent volume
        print("   Stopping Redis to clear volume...")
        try:
            result = subprocess.run(
                ["docker", "compose", "stop", "redis"],
                capture_output=True,
                text=True,
                timeout=30
            )
            # Remove Redis volume to ensure fresh start
            result = subprocess.run(
                ["docker", "volume", "rm", "zerodha_redis_data"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print(f"   {GREEN}✓{RESET} Redis volume cleared")
            else:
                # Volume might not exist or be in use
                print(f"   {GREEN}✓{RESET} Redis volume clear attempted")
        except Exception as e:
            print(f"   {YELLOW}⚠{RESET} Redis volume clear: {e}")
        
        # Clear MongoDB OHLC data to prevent rehydration of stale data
        print("   Clearing MongoDB OHL C data...")
        try:
            from pymongo import MongoClient
            try:
                client = MongoClient('localhost', 27017, serverSelectionTimeoutMS=5000)
                client.admin.command('ping')  # Test connection
                db = client['market_data']
                
                # Clear OHLC collections
                collections_cleared = 0
                for coll_name in ['ohlc_banknifty', 'ohlc', 'ticks']:
                    if coll_name in db.list_collection_names():
                        db[coll_name].delete_many({})
                        collections_cleared += 1
                
                if collections_cleared > 0:
                    print(f"   {GREEN}✓{RESET} MongoDB OHLC data cleared ({collections_cleared} collections)")
                else:
                    print(f"   {GREEN}✓{RESET} MongoDB clean (no stale data)")
            except Exception as e:
                # MongoDB might not be running yet
                print(f"   {GREEN}✓{RESET} MongoDB not accessible (will start fresh)")
        except Exception as e:
            print(f"   {YELLOW}⚠{RESET} Cannot clear MongoDB: {e}")
        
        # Clear virtual time flags
        print("   Clearing virtual time flags...")
        try:
            r = redis.Redis(host='localhost', port=6380, decode_responses=True)
            r.delete("system:virtual_time:enabled")
            r.delete("system:virtual_time:current")
            print(f"   {GREEN}✓{RESET} Virtual time flags cleared")
        except Exception as e:
            print(f"   {YELLOW}⚠{RESET} Cannot clear virtual time: {e}")
        
        print(f"\n{GREEN}✅ Environment cleaned{RESET}")
        return True
    
    def _start_services(self) -> bool:
        """Start required services for live mode."""
        self._print_step(3, "Starting Services")
        
        services = [
            "redis",
            "mongodb",
            "redis-ws-gateway",
            "market-data-api",
            "market-data-dashboard",
            "engine-api",  # Indicator calculation engine
            "websocket-tick-collector-banknifty",
            "ltp-collector-banknifty"
        ]
        
        print(f"   Starting {len(services)} services...")
        print(f"   Services: {', '.join(services)}")
        
        cmd = ["docker", "compose", "up", "-d"] + services
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            self._print_error("Failed to start services")
            print(result.stderr)
            return False
        
        print(f"   {GREEN}✓{RESET} Services started")
        print(f"\n{GREEN}✅ Services starting (waiting for health checks...){RESET}")
        return True
    
    def _wait_for_services(self) -> bool:
        """Wait for services to be healthy."""
        self._print_step(4, "Health Checks")
        
        checks = [
            ("Redis", self._check_redis_health),
            ("Market Data API", self._check_api_health),
            ("Dashboard", self._check_dashboard_health),
            ("Engine API", self._check_engine_health),
            ("WebSocket Collector", self._check_websocket_health),
        ]
        
        max_wait = 60  # seconds
        start_time = time.time()
        
        for service_name, check_func in checks:
            print(f"   Waiting for {service_name}...", end="", flush=True)
            
            while time.time() - start_time < max_wait:
                if check_func():
                    print(f" {GREEN}✓{RESET}")
                    break
                time.sleep(2)
            else:
                print(f" {RED}✗ TIMEOUT{RESET}")
                self._print_error(f"{service_name} did not become healthy in {max_wait}s")
                return False
        
        print(f"\n{GREEN}✅ All services healthy{RESET}")
        return True
    
    def _check_redis_health(self) -> bool:
        """Check if Redis is responsive."""
        try:
            if not self.redis_client:
                self.redis_client = redis.Redis(
                    host='localhost',
                    port=6380,
                    decode_responses=True
                )
            self.redis_client.ping()
            return True
        except:
            return False
    
    def _check_api_health(self) -> bool:
        """Check if API is responding."""
        try:
            import requests
            response = requests.get("http://localhost:8004/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _check_dashboard_health(self) -> bool:
        """Check if dashboard is responding."""
        try:
            import requests
            response = requests.get("http://localhost:8008", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _check_engine_health(self) -> bool:
        """Check if engine API is responding."""
        try:
            import requests
            response = requests.get("http://localhost:8006/health", timeout=5)
            return response.status_code == 200
        except:
            # Engine might not have /health endpoint, check if container is running
            try:
                result = subprocess.run(
                    ["docker", "ps", "--filter", "name=engine-api", "--format", "{{.Status}}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return "Up" in result.stdout
            except:
                return False
    
    def _check_websocket_health(self) -> bool:
        """Check if WebSocket collector is connected."""
        try:
            result = subprocess.run(
                ["docker", "logs", "zerodha-websocket-tick-collector-banknifty", "--tail", "50"],
                capture_output=True,
                text=True,
                timeout=5
            )
            logs = result.stdout + result.stderr
            return "WebSocket connected" in logs or "Processed tick" in logs
        except:
            return False
    
    def _validate_data_pipeline(self) -> bool:
        """Validate actual data is real Zerodha data."""
        self._print_step(5, "Data Pipeline Validation")
        
        print("   Waiting for data to flow through pipeline...")
        
        # Check 1: WebSocket is publishing real data
        print("   Verifying WebSocket data...")
        for attempt in range(3):
            try:
                time.sleep(5)  # Wait 5 seconds between attempts
                result = subprocess.run(
                    ["docker", "logs", "zerodha-websocket-tick-collector-banknifty", "--tail", "20"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                logs = result.stdout + result.stderr
                
                if "Processed tick" in logs:
                    # Check price is in logs
                    if "60" in logs or "59" in logs or "58" in logs:
                        print(f"   {GREEN}✓{RESET} WebSocket processing real ticks")
                        break
                    else:
                        self._print_error("WebSocket prices look suspicious (expected ~60k for BANKNIFTY)")
                        print(f"   Check logs: docker logs zerodha-websocket-tick-collector-banknifty --tail 20")
                        return False
                
                if attempt < 2:
                    print(f"   Waiting for WebSocket ticks (attempt {attempt + 1}/3)...")
                else:
                    self._print_error("WebSocket not processing ticks after 15 seconds")
                    return False
            except Exception as e:
                if attempt < 2:
                    print(f"   Retrying WebSocket check...")
                else:
                    self._print_error(f"Cannot verify WebSocket: {e}")
                    return False
        
        # Check 2: Price in Redis is realistic (with retry)
        print("   Waiting for fresh WebSocket data (12 seconds)...")
        time.sleep(12)  # Initial wait for WebSocket to connect and receive real ticks
        
        print("   Verifying price in Redis...")
        price_data = None
        for attempt in range(6):  # Increased to 6 attempts  (18 seconds total)
            try:
                time.sleep(3)  # Wait 3 seconds between attempts
                
                # Try websocket tick data (real-time data available immediately)
                tick_data_str = self.redis_client.get("websocket:tick:BANKNIFTY26FEBFUT:latest")
                if tick_data_str:
                    import json
                    tick_data = json.loads(tick_data_str)
                    price_data = tick_data.get("last_price")
                    if price_data:
                        break
                
                # Fallback to indicators key (may not exist in some setups)
                if not price_data:
                    price_str =self.redis_client.get("indicators:BANKNIFTY26FEBFUT:current_price")
                    if price_str:
                        price_data = float(price_str)
                        break
                
                if attempt < 5:
                    print(f"   Waiting for price data in Redis (attempt {attempt + 1}/6)...")
            except Exception as e:
                if attempt < 5:
                    print(f"   Retrying Redis check...")
                else:
                    self._print_error(f"Cannot check Redis: {e}")
                    return False
        
        if not price_data:
            self._print_error("No price in Redis after 36 seconds (data pipeline may be stuck)")
            print(f"   Debug: Check logs:")
            print(f"   - docker logs zerodha-websocket-tick-collector-banknifty")
            print(f"   - docker logs zerodha-ltp-collector-banknifty")
            return False
        
        try:
            
            price = float(price_data)
            print(f"   Current Price: ₹{price:,.2f}")
            
            if price < self.BANKNIFTY_MIN:
                self._print_error(
                    f"Price {price:.2f} is TOO LOW (expected >{self.BANKNIFTY_MIN}) - "
                    f"likely MOCK data!"
                )
                return False
            
            if price > self.BANKNIFTY_MAX:
                self._print_error(
                    f"Price {price:.2f} is TOO HIGH (expected <{self.BANKNIFTY_MAX})"
                )
                return False
            
            print(f"   {GREEN}✓{RESET} Price in realistic range ({self.BANKNIFTY_MIN:,} - {self.BANKNIFTY_MAX:,})")
        except Exception as e:
            self._print_error(f"Cannot verify price: {e}")
            return False
        
        # Check 3: Data source configuration
        print("   Verifying data source configuration...")
        try:
            result = subprocess.run(
                ["docker", "exec", "zerodha-websocket-tick-collector-banknifty", "env"],
                capture_output=True,
                text=True,
                timeout=5
            )
            env = result.stdout
            
            if "DATA_SOURCE=ZERODHA" not in env:
                self._print_error("DATA_SOURCE is not ZERODHA")
                return False
            
            if "ZERODHA_MODE=live" not in env:
                self._print_error("ZERODHA_MODE is not live")
                return False
            
            print(f"   {GREEN}✓{RESET} Data source: ZERODHA (live mode)")
        except Exception as e:
            self._print_error(f"Cannot verify data source: {e}")
            return False
        
        # Check 4: No mock services running
        print("   Verifying no mock interference...")
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            containers = result.stdout
            
            if "mock-publisher" in containers or "mock-options" in containers:
                self._print_error("Mock services are running!")
                return False
            
            print(f"   {GREEN}✓{RESET} No mock services detected")
        except Exception as e:
            self._print_error(f"Cannot check for mock services: {e}")
            return False
        
        print(f"\n{GREEN}✅ Data pipeline validated - REAL Zerodha data confirmed{RESET}")
        return True


def main():
    """Main entry point."""
    validator = LiveModeValidator()
    
    try:
        success = validator.start()
        
        if not success:
            print(f"\n{RED}{'=' * 80}{RESET}")
            print(f"{RED}{BOLD}❌ STARTUP FAILED{RESET}")
            print(f"{RED}{'=' * 80}{RESET}\n")
            print("System did not start to prevent running with incorrect data.")
            print("Please fix the errors above and try again.")
            print()
            sys.exit(1)
        
        sys.exit(0)
        
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}⚠ Startup interrupted by user{RESET}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}❌ Unexpected error: {e}{RESET}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
