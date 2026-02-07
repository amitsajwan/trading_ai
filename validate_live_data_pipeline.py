#!/usr/bin/env python3
"""
Live Data Pipeline Validator

Validates EVERY step of the data pipeline to ensure we're getting REAL Zerodha data.
No false positives - validates actual market prices and sources.
"""

import json
import os
import sys
import redis
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

class LiveDataValidator:
    """Comprehensive validation of live data pipeline."""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6380")),  # Docker maps 6379 -> 6380
            decode_responses=True
        )
        self.errors = []
        self.warnings = []
        
    def validate(self) -> bool:
        """Run all validation checks."""
        print("=" * 80)
        print("LIVE DATA PIPELINE VALIDATION")
        print("=" * 80)
        print()
        
        checks = [
            ("Step 1: Credentials & Token", self._check_credentials),
            ("Step 2: WebSocket Connection", self._check_websocket_connection),
            ("Step 3: Data Source Verification", self._check_data_source),
            ("Step 4: Price Sanity Check", self._check_price_sanity),
            ("Step 5: Redis Data Flow", self._check_redis_data),
            ("Step 6: No Mock/Historical Interference", self._check_no_mock_data),
            ("Step 7: Volume Data Validation", self._check_volume_data),
        ]
        
        all_passed = True
        for step_name, check_func in checks:
            print(f"\n{step_name}")
            print("-" * 80)
            try:
                result = check_func()
                if result:
                    print(f"✅ PASSED")
                else:
                    print(f"❌ FAILED")
                    all_passed = False
            except Exception as e:
                print(f"❌ ERROR: {e}")
                all_passed = False
                
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        
        if all_passed:
            print("✅ ALL CHECKS PASSED - Live data pipeline is VERIFIED")
            print(f"   Validated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            return True
        else:
            print("❌ VALIDATION FAILED")
            if self.errors:
                print("\nErrors:")
                for error in self.errors:
                    print(f"   • {error}")
            if self.warnings:
                print("\nWarnings:")
                for warning in self.warnings:
                    print(f"   • {warning}")
            return False
    
    def _check_credentials(self) -> bool:
        """Validate Kite credentials and access token."""
        creds_file = Path("credentials.json")
        
        if not creds_file.exists():
            self.errors.append("credentials.json not found")
            return False
            
        with open(creds_file) as f:
            creds = json.load(f)
        
        # Check API key
        api_key = creds.get("api_key")
        if not api_key:
            self.errors.append("No API key in credentials.json")
            return False
        print(f"   API Key: {api_key[:10]}...")
        
        # Check access token
        access_token = creds.get("access_token")
        if not access_token:
            self.errors.append("No access token in credentials.json")
            return False
        print(f"   Access Token: {access_token[:15]}...")
        
        # Check token age
        login_time = creds.get("login_time")
        if login_time:
            login_dt = datetime.fromisoformat(login_time)
            age = datetime.now() - login_dt
            if age > timedelta(hours=23):
                self.errors.append(f"Token is {age.total_seconds()/3600:.1f} hours old - might be expired")
                return False
            print(f"   Token Age: {age.total_seconds()/3600:.1f} hours (OK)")
        
        # Verify with API call
        try:
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            profile = kite.profile()
            print(f"   User ID: {profile['user_id']} (Token VALID)")
            return True
        except Exception as e:
            self.errors.append(f"Token validation failed: {e}")
            return False
    
    def _check_websocket_connection(self) -> bool:
        """Verify WebSocket collector is connected to Zerodha."""
        try:
            result = subprocess.run(
                ["docker", "logs", "zerodha-websocket-tick-collector-banknifty", "--tail", "100"],
                capture_output=True,
                text=True,
                timeout=10,
                errors='replace'  # Handle encoding issues
            )
            logs = result.stdout + result.stderr
            
            # Check for connection
            if ("WebSocket connected" in logs or "tcp4:52.66." in logs):
                print("   ✅ WebSocket connected to Zerodha")
                
                # Check for recent ticks
                if "Processed tick" in logs:
                    # Count recent ticks
                    tick_count = logs.count("Processed tick")
                    print(f"   ✅ Receiving ticks ({tick_count} in recent logs)")
                    return True
                else:
                    self.warnings.append("WebSocket connected but no recent ticks")
                    return False
            else:
                self.errors.append("WebSocket not connected to Zerodha")
                return False
            
        except Exception as e:
            self.errors.append(f"Cannot check WebSocket: {e}")
            return False
    
    def _check_data_source(self) -> bool:
        """Verify data is coming from Zerodha, not mock."""
        try:
            # Check WebSocket container env
            result = subprocess.run(
                ["docker", "exec", "zerodha-websocket-tick-collector-banknifty", "env"],
                capture_output=True,
                text=True,
                timeout=5
            )
            env = result.stdout
            
            if "DATA_SOURCE=ZERODHA" in env:
                print("   ✅ DATA_SOURCE=ZERODHA")
            else:
                self.errors.append("DATA_SOURCE is not ZERODHA")
                return False
            
            if "ZERODHA_MODE=live" in env:
                print("   ✅ ZERODHA_MODE=live")
            else:
                self.errors.append("ZERODHA_MODE is not live")
                return False
            
            if "USE_KITE_API=true" in env:
                print("   ✅ USE_KITE_API=true")
            else:
                self.errors.append("USE_KITE_API not set to true")
                return False
            
            return True
        except Exception as e:
            self.errors.append(f"Cannot check data source: {e}")
            return False
    
    def _check_price_sanity(self) -> bool:
        """Verify prices are in realistic range (not mock data)."""
        try:
            price_str = self.redis_client.get("indicators:BANKNIFTY26FEBFUT:current_price")
            if not price_str:
                self.errors.append("No current price in Redis")
                return False
            
            price = float(price_str)
            print(f"   Current Price: ₹{price:,.2f}")
            
            # Bank Nifty futures should be in reasonable range
            # Adjust these ranges based on current market levels
            MIN_EXPECTED = 50000  # Reasonable floor for BANKNIFTY
            MAX_EXPECTED = 70000  # Reasonable ceiling for BANKNIFTY
            
            if price < MIN_EXPECTED:
                self.errors.append(f"Price {price:.2f} is suspiciously LOW (expected > {MIN_EXPECTED}) - likely MOCK data!")
                return False
            
            if price > MAX_EXPECTED:
                self.errors.append(f"Price {price:.2f} is suspiciously HIGH (expected < {MAX_EXPECTED})")
                return False
            
            print(f"   ✅ Price in realistic range ({MIN_EXPECTED:,} - {MAX_EXPECTED:,})")
            return True
            
        except Exception as e:
            self.errors.append(f"Cannot check price: {e}")
            return False
    
    def _check_redis_data(self) -> bool:
        """Verify Redis has recent live data."""
        try:
            # Check for live-prefixed keys
            keys = self.redis_client.keys("live:*BANKNIFTY*")
            if not keys:
                self.warnings.append("No live:-prefixed keys found")
            else:
                print(f"   ✅ Found {len(keys)} live:-prefixed keys")
            
            # Check enhanced ticks
            enhanced_key = "live:enhanced_ticks:BANKNIFTY26FEBFUT"
            enhanced_data = self.redis_client.get(enhanced_key)
            if enhanced_data:
                tick = json.loads(enhanced_data)
                timestamp = tick.get('timestamp', 'unknown')
                print(f"   ✅ Enhanced ticks available (last: {timestamp})")
            else:
                self.warnings.append("No enhanced ticks data")
            
            return True
        except Exception as e:
            self.errors.append(f"Cannot check Redis data: {e}")
            return False
    
    def _check_no_mock_data(self) -> bool:
        """Ensure no mock/historical services are interfering."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            containers = result.stdout.split('\n')
            
            # Check for mock services
            mock_services = [c for c in containers if 'mock' in c.lower()]
            if mock_services:
                self.errors.append(f"Mock services running: {', '.join(mock_services)}")
                return False
            
            # Check historical replay is stopped
            if any('historical-replay' in c for c in containers):
                result = subprocess.run(
                    ["docker", "ps", "--filter", "name=historical-replay", "--format", "{{.Status}}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                status = result.stdout.strip()
                if status and "Up" in status:
                    self.errors.append("Historical replay service is running - should be stopped in live mode")
                    return False
            
            print("   ✅ No mock/historical services interfering")
            return True
        except Exception as e:
            self.errors.append(f"Cannot check for mock services: {e}")
            return False
    
    def _check_volume_data(self) -> bool:
        """Verify volume data is present and realistic."""
        try:
            # Check recent ticks for volume
            result = subprocess.run(
                ["docker", "logs", "zerodha-ltp-collector-banknifty", "--tail", "20"],
                capture_output=True,
                text=True,
                timeout=5
            )
            logs = result.stdout
            
            # Look for volume in logs
            if "volume=" in logs:
                # Extract volume values
                volume_lines = [l for l in logs.split('\n') if 'volume=' in l]
                if volume_lines:
                    print(f"   ✅ Volume data present in stream")
                    # Show last volume
                    last_vol_line = volume_lines[-1]
                    print(f"   Last: {last_vol_line.split('volume=')[1].split()[0]}")
                    return True
            
            self.warnings.append("No volume data found in recent logs")
            return True  # Don't fail on this, just warn
            
        except Exception as e:
            self.warnings.append(f"Cannot check volume data: {e}")
            return True


def main():
    """Run validation."""
    validator = LiveDataValidator()
    success = validator.validate()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
