"""Comprehensive verification script for Docker deployment.

This script checks all system components and provides detailed diagnostics.
Run this to verify the entire system is functioning correctly.
"""

import json
import os
import sys
import time
from typing import Dict, List, Tuple
from datetime import datetime

try:
    import requests
    import pymongo
    import redis
except ImportError:
    print("❌ Missing dependencies. Install: pip install requests pymongo redis")
    sys.exit(1)


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


class SystemVerifier:
    """Comprehensive system verification."""
    
    def __init__(self):
        self.results: List[Tuple[str, bool, str]] = []
        self.mongodb_client = None
        self.redis_client = None
    
    def check(self, name: str, condition: bool, message: str = ""):
        """Record a check result."""
        self.results.append((name, condition, message))
        status = f"{Colors.GREEN}✓{Colors.END}" if condition else f"{Colors.RED}✗{Colors.END}"
        print(f"{status} {name}: {message}")
        return condition
    
    def section(self, title: str):
        """Print section header."""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    
    def verify_credentials(self) -> bool:
        """Verify credentials.json structure and validity."""
        self.section("Credentials Verification")
        
        creds_file = "credentials.json"
        if not os.path.exists(creds_file):
            self.check("Credentials file", False, f"{creds_file} not found")
            return False
        
        try:
            with open(creds_file, 'r') as f:
                creds = json.load(f)
            
            self.check("Credentials file", True, f"{creds_file} exists and is valid JSON")
            
            required_fields = ["api_key", "api_secret", "access_token"]
            for field in required_fields:
                has_field = field in creds
                value = creds.get(field, "")
                is_empty = not value or value == ""
                
                if has_field and not is_empty:
                    masked_value = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
                    self.check(f"Credential: {field}", True, f"Present ({masked_value})")
                elif has_field:
                    self.check(f"Credential: {field}", False, "Empty - run auto_login.py")
                else:
                    self.check(f"Credential: {field}", False, "Missing field")
            
            return all(creds.get(field) for field in required_fields)
        
        except json.JSONDecodeError as e:
            self.check("Credentials JSON", False, f"Invalid JSON: {e}")
            return False
        except Exception as e:
            self.check("Credentials read", False, str(e))
            return False
    
    def verify_mongodb(self) -> bool:
        """Verify MongoDB connectivity and data."""
        self.section("MongoDB Verification")
        
        try:
            self.mongodb_client = pymongo.MongoClient(
                "mongodb://localhost:27018/",
                serverSelectionTimeoutMS=5000
            )
            self.mongodb_client.admin.command('ping')
            self.check("MongoDB connection", True, "localhost:27018 reachable")
            
            db = self.mongodb_client["zerodha_trading"]
            collections = db.list_collection_names()
            self.check("Database exists", True, f"zerodha_trading ({len(collections)} collections)")
            
            expected_collections = ["ohlc_history", "trades_executed", "agent_decisions", "news_events"]
            for coll in expected_collections:
                exists = coll in collections
                if exists:
                    count = db[coll].count_documents({})
                    self.check(f"Collection: {coll}", True, f"{count} documents")
                else:
                    self.check(f"Collection: {coll}", False, "Not found")
            
            return True
        
        except pymongo.errors.ServerSelectionTimeoutError:
            self.check("MongoDB connection", False, "Timeout - is Docker running?")
            return False
        except Exception as e:
            self.check("MongoDB", False, str(e))
            return False
    
    def verify_redis(self) -> bool:
        """Verify Redis connectivity."""
        self.section("Redis Verification")
        
        try:
            self.redis_client = redis.Redis(
                host='localhost',
                port=6380,
                decode_responses=True,
                socket_timeout=5
            )
            self.redis_client.ping()
            self.check("Redis connection", True, "localhost:6380 reachable")
            
            keys = self.redis_client.keys("*")
            self.check("Redis keys", len(keys) > 0, f"{len(keys)} keys found")
            
            # Check for LTP data
            ltp_keys = [k for k in keys if 'ltp' in k.lower() or 'price' in k.lower()]
            if ltp_keys:
                sample_key = ltp_keys[0]
                value = self.redis_client.get(sample_key)
                self.check("LTP data sample", True, f"{sample_key} = {value}")
            
            return True
        
        except redis.exceptions.ConnectionError:
            self.check("Redis connection", False, "Connection failed - is Docker running?")
            return False
        except Exception as e:
            self.check("Redis", False, str(e))
            return False
    
    def verify_docker_containers(self) -> bool:
        """Verify Docker containers are running."""
        self.section("Docker Container Verification")
        
        containers = {
            "BTC": "http://localhost:8001/health",
            "BANKNIFTY": "http://localhost:8002/health",
            "NIFTY": "http://localhost:8003/health",
        }
        
        all_ok = True
        for name, url in containers.items():
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")
                    self.check(f"Container: {name}", True, f"{url} → {status}")
                else:
                    self.check(f"Container: {name}", False, f"HTTP {response.status_code}")
                    all_ok = False
            except requests.exceptions.ConnectionError:
                self.check(f"Container: {name}", False, "Not reachable - container may be down")
                all_ok = False
            except Exception as e:
                self.check(f"Container: {name}", False, str(e))
                all_ok = False
        
        return all_ok
    
    def verify_dashboards(self) -> bool:
        """Verify dashboard rendering with correct instrument names."""
        self.section("Dashboard Verification")
        
        dashboards = {
            "BTC": ("http://localhost:8001/", "BTC-USD"),
            "BANKNIFTY": ("http://localhost:8002/", "NIFTY BANK"),
            "NIFTY": ("http://localhost:8003/", "NIFTY 50"),
        }
        
        all_ok = True
        for name, (url, expected_instrument) in dashboards.items():
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    html = response.text
                    
                    # Check title
                    title_check = f"Trading Dashboard - {expected_instrument}" in html
                    self.check(
                        f"Dashboard {name} title",
                        title_check,
                        f"{'✓' if title_check else '✗'} Instrument name in title"
                    )
                    
                    # Check JavaScript variable
                    js_check = f'window.INSTRUMENT_SYMBOL = "{expected_instrument}"' in html
                    self.check(
                        f"Dashboard {name} JS var",
                        js_check,
                        f"{'✓' if js_check else '✗'} INSTRUMENT_SYMBOL set"
                    )
                    
                    all_ok = all_ok and title_check and js_check
                else:
                    self.check(f"Dashboard {name}", False, f"HTTP {response.status_code}")
                    all_ok = False
            except Exception as e:
                self.check(f"Dashboard {name}", False, str(e))
                all_ok = False
        
        return all_ok
    
    def verify_data_collection(self) -> bool:
        """Verify data is being collected."""
        self.section("Data Collection Verification")
        
        if not self.mongodb_client:
            self.check("Data collection", False, "MongoDB not connected")
            return False
        
        db = self.mongodb_client["zerodha_trading"]
        
        # Check for recent OHLC data (last 1 hour)
        one_hour_ago = datetime.now().timestamp() - 3600
        recent_ohlc = db["ohlc_history"].count_documents({
            "timestamp": {"$gte": one_hour_ago}
        })
        
        self.check(
            "Recent OHLC data",
            recent_ohlc > 0,
            f"{recent_ohlc} candles in last hour"
        )
        
        # Check instruments in database
        instruments = db["ohlc_history"].distinct("instrument")
        if instruments:
            self.check(
                "Instruments tracked",
                True,
                f"{len(instruments)} instruments: {', '.join(instruments)}"
            )
        else:
            self.check("Instruments tracked", False, "No instruments found")
        
        return recent_ohlc > 0
    
    def verify_environment_files(self) -> bool:
        """Verify .env files exist and are configured."""
        self.section("Environment Configuration")
        
        env_files = {
            ".env.btc": ["INSTRUMENT_SYMBOL=BTC-USD", "DATA_SOURCE=CRYPTO"],
            ".env.banknifty": ["INSTRUMENT_SYMBOL=NIFTY BANK", "DATA_SOURCE=ZERODHA"],
            ".env.nifty": ["INSTRUMENT_SYMBOL=NIFTY 50", "DATA_SOURCE=ZERODHA"],
        }
        
        all_ok = True
        for filename, required_settings in env_files.items():
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    content = f.read()
                
                missing = [s for s in required_settings if s not in content]
                if not missing:
                    self.check(f"Config: {filename}", True, "All required settings present")
                else:
                    self.check(f"Config: {filename}", False, f"Missing: {', '.join(missing)}")
                    all_ok = False
            else:
                self.check(f"Config: {filename}", False, "File not found")
                all_ok = False
        
        return all_ok
    
    def print_summary(self):
        """Print summary of all checks."""
        self.section("Verification Summary")
        
        passed = sum(1 for _, success, _ in self.results if success)
        total = len(self.results)
        percentage = (passed / total * 100) if total > 0 else 0
        
        print(f"\n{Colors.BOLD}Results: {passed}/{total} checks passed ({percentage:.1f}%){Colors.END}")
        
        if passed == total:
            print(f"{Colors.GREEN}{Colors.BOLD}✓ All systems operational{Colors.END}")
            return 0
        else:
            failed = total - passed
            print(f"{Colors.RED}{Colors.BOLD}✗ {failed} issues detected{Colors.END}")
            print(f"\n{Colors.YELLOW}Failed checks:{Colors.END}")
            for name, success, message in self.results:
                if not success:
                    print(f"  • {name}: {message}")
            return 1
    
    def run_all(self) -> int:
        """Run all verifications."""
        print(f"{Colors.BOLD}Zerodha Trading System Verification{Colors.END}")
        print(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        self.verify_environment_files()
        self.verify_credentials()
        self.verify_mongodb()
        self.verify_redis()
        self.verify_docker_containers()
        self.verify_dashboards()
        self.verify_data_collection()
        
        return self.print_summary()


def main():
    """Main entry point."""
    verifier = SystemVerifier()
    exit_code = verifier.run_all()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
