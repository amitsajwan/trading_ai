#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Startup Script for Zerodha Trading System
Seamlessly handles LIVE and HISTORICAL modes with auto-configuration
"""

import os
import sys
import json
import argparse
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Optional

# Fix Windows encoding issues
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add market_data/src to Python path for module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'market_data', 'src'))

try:
    from redis_key_manager import get_redis_key, clear_mode_data, get_execution_mode
except Exception as e:
    print(f"[DEBUG] redis_key_manager import failed: {e}")
    get_redis_key = lambda key, mode=None: key  # Fallback
    clear_mode_data = lambda r, mode: 0
    get_execution_mode = lambda: "live"

try:
    from market_data.tools.auth_startup import AuthStartup
except Exception as e:
    print(f"[DEBUG] AuthStartup import failed: {e}")
    AuthStartup = None

try:
    from market_data.tools.kite_auth_service import KiteAuthService
except Exception as e:
    print(f"[DEBUG] KiteAuthService import failed: {e}")
    KiteAuthService = None

try:
    import redis
except Exception:
    redis = None

class UnifiedStarter:
    """Unified startup manager for both LIVE and HISTORICAL modes"""
    
    def __init__(self):
        self.config_file = Path(".mode_config.json")
        self.creds_file = Path("credentials.json")
    
    def _load_config(self) -> dict:
        """Load current mode configuration"""
        if self.config_file.exists():
            with open(self.config_file) as f:
                return json.load(f)
        return {"mode": "live"}

    def _run_cmd(self, cmd: list[str]) -> int:
        """Run a subprocess command and return exit code."""
        try:
            result = subprocess.run(cmd, check=False)
            return result.returncode
        except Exception as e:
            print(f"   ❌ Error running {' '.join(cmd)}: {e}")
            return 1

    def _stop_historical_service(self):
        print("\n⏹️  Stopping historical services (if running)...")
        services_to_stop = [
            "historical-replay-service",
            "ohlc-aggregator"
        ]
        for service in services_to_stop:
            self._run_cmd(["docker-compose", "stop", service])
        print("   ✅ Historical services stopped")

    def _clear_virtual_time(self, r):
        try:
            r.delete("system:virtual_time:enabled")
            r.delete("system:virtual_time:current")
            print("   ✅ Cleared virtual time flags")
        except Exception as e:
            print(f"   ⚠️ Could not clear virtual time: {e}")

    def _clear_ohlc(self, r, instrument: str, mode: str = "live"):
        """Clear OHLC data for specific mode."""
        try:
            # Clear all timeframes for this mode
            timeframes = ['1min', '5min', '15min', '1h', '4h', '1d']
            total_cleared = 0
            for tf in timeframes:
                sorted_key = get_redis_key(f"ohlc_sorted:{instrument}:{tf}", mode=mode)
                removed = r.delete(sorted_key)
                if removed:
                    total_cleared += 1
                    print(f"   ✅ Cleared {sorted_key}")
            
            if total_cleared == 0:
                print(f"   💡 No {mode.upper()} OHLC data to clear")
            else:
                print(f"   ✅ Cleared {total_cleared} {mode.upper()} timeframes for {instrument}")
        except Exception as e:
            print(f"   ⚠️ Could not clear OHLC data: {e}")

    def _load_today_historical_data(self, mode: str = "live"):
        """Load today's historical OHLC data from Zerodha to populate chart"""
        try:
            from kiteconnect import KiteConnect
            from datetime import datetime
            
            print(f"\n📥 Loading today's historical data for {mode.upper()} mode...")
            
            # Load credentials
            with open(self.creds_file) as f:
                creds = json.load(f)
            
            # Initialize Kite
            kite = KiteConnect(api_key=creds['api_key'])
            kite.set_access_token(creds['data']['access_token'])
            
            # Fetch today's data from 9:15 AM to now
            instrument_token = 260105  # BANKNIFTY26FEBFUT
            instrument = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY26FEBFUT").upper()
            from_date = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
            to_date = datetime.now()
            
            data = kite.historical_data(instrument_token, from_date, to_date, 'minute')
            print(f"   ✅ Fetched {len(data)} bars from Zerodha API")
            
            if len(data) == 0:
                print("   ⚠️ No historical data available (market might not have opened yet)")
                return
            
            # Connect to Redis
            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", "6379"))
            r = redis.Redis(host=host, port=port, decode_responses=False)
            
            # Store in Redis with mode prefix
            timeframe = "1min"
            stored_count = 0
            
            for bar in data:
                ohlc_bar = {
                    "timestamp": bar['date'].strftime("%Y-%m-%dT%H:%M:%S+05:30"),
                    "open": float(bar['open']),
                    "high": float(bar['high']),
                    "low": float(bar['low']),
                    "close": float(bar['close']),
                    "volume": int(bar['volume']),
                    "instrument": instrument,
                    "timeframe": timeframe,
                    "_stored_at": datetime.utcnow().isoformat() + "+00:00",
                    "_stored_by": "start_unified_auto",
                    "_format_version": "2.0"
                }
                
                score = bar['date'].timestamp()
                redis_key = get_redis_key(f"ohlc_sorted:{instrument}:{timeframe}", mode=mode)
                r.zadd(redis_key, {json.dumps(ohlc_bar): score})
                stored_count += 1
            
            redis_key = get_redis_key(f"ohlc_sorted:{instrument}:{timeframe}", mode=mode)
            total_bars = r.zcard(redis_key)
            print(f"   ✅ Stored {stored_count} bars in {redis_key} (total: {total_bars})")
            print(f"   💡 Chart will display indicators (RSI needs 14, MACD needs 26 bars)")
            
        except Exception as e:
            print(f"   ⚠️ Could not load historical data: {e}")
            print(f"   💡 Chart will start from scratch with live ticks only")
    
    def _prep_live_datastore(self, mode: str = "live"):
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        instrument = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY26FEBFUT").upper()
        if not redis:
            print("   ⚠️ redis-py not available; skipping Redis cleanup")
            return
        try:
            r = redis.Redis(host=host, port=port, db=0, decode_responses=True)
            r.ping()
            print(f"\n🧹 Preparing Redis datastore for {mode.upper()} mode ({instrument})...")
            self._clear_virtual_time(r)
            self._clear_ohlc(r, instrument, mode=mode)
            
            # Load today's historical data for chart initialization
            self._load_today_historical_data(mode=mode)
            
        except Exception as e:
            print(f"   ⚠️ Redis prep skipped (connection failed?): {e}")

    def _start_live_services(self):
        print("\n🐳 Starting core services for LIVE mode...")
        services = [
            "redis",
            "redis-ws-gateway",
            "websocket-tick-collector-banknifty",
            "ltp-collector-banknifty",
            "ohlc-aggregator",
            "multi-timeframe-aggregator",
            "market-data-api",
            "market-data-dashboard"
        ]
        cmd = ["docker-compose", "up", "-d", *services]
        code = self._run_cmd(cmd)
        if code == 0:
            print("   ✅ Services started")
        else:
            print("   ❌ Failed to start live services")
    
    def _ensure_credentials(self):
        """Ensure Zerodha credentials are available - uses new AuthStartup module"""
        print("\n🔐 Checking Zerodha credentials...")
        
        # Try new centralized auth startup module (recommended)
        try:
            # Use sys.path setup to import the module properly
            from market_data.tools.auth_startup import AuthStartup as AuthStartupClass
            
            auth = AuthStartupClass(str(self.creds_file))
            print("   📡 Using new AuthStartup module for authentication...")
            success, message = auth.startup_check()
            
            if success:
                print(f"   ✅ {message}")
                return True
            else:
                print(f"   ⚠️ {message}")
                print("   🔄 Attempting fallback authentication...")
                
        except Exception as e:
            print(f"   ℹ️ AuthStartup not available: {str(e)[:60]}...")
        
        # Fallback: legacy KiteAuthService approach
        print("   🔄 Using legacy authentication flow...")
        try:
            from market_data.tools.kite_auth_service import KiteAuthService as KAS
            
            svc = KAS(str(self.creds_file))
            creds = svc.load_credentials()

            def _validate(creds_obj):
                if creds_obj and svc.is_token_valid(creds_obj):
                    user = creds_obj.get("user_id", "Unknown")
                    api_key = (creds_obj.get("api_key") or creds_obj.get("KITE_API_KEY") or "")[:15] + "..."
                    print(f"   ✅ Valid token for user: {user}")
                    print(f"      API Key: {api_key}")
                    return True
                else:
                    if not creds_obj:
                        print("   ⚠️ No credentials found")
                    else:
                        print("   ⚠️ Token invalid or expired")
                    return False

            if _validate(creds):
                return True

            print("   🌐 Attempting interactive browser-based login...")
            try:
                success = svc.trigger_interactive_login(timeout=300)
                if success:
                    creds = svc.load_credentials()
                    if _validate(creds):
                        print("   ✅ Interactive login successful!")
                        return True
                    else:
                        print("   ❌ Credentials file created but token validation failed")
                        return False
                else:
                    print("   ❌ Interactive login timed out or was cancelled")
                    return False
            except Exception as e:
                print(f"   ❌ Interactive login error: {e}")
                return False
                
        except Exception as e:
            print(f"   ⚠️ KiteAuthService not available: {str(e)[:60]}...")

        # Ultimate fallback: basic file check
        print("   📂 Checking for credentials file...")
        if self.creds_file.exists():
            try:
                with open(self.creds_file) as f:
                    creds = json.load(f)
                user = creds.get("user_id", "Unknown")
                api_key = creds.get("api_key", "")[:15] + "..."
                print(f"   ✅ Credentials file found for user: {user}")
                print(f"      API Key: {api_key}")
                print("   ⚠️ Note: Token not validated (validation disabled)")
                return True
            except Exception as e:
                print(f"   ❌ Error reading credentials: {e}")
        
        print("   ❌ No credentials available - authentication required")
        print("   💡 Set environment variables and restart:")
        print("      export KITE_API_KEY='your_key'")
        print("      export KITE_API_SECRET='your_secret'")
        return False
    
    def start_live_mode(self):
        """Start system in LIVE mode with Zerodha WebSocket"""
        print("\n" + "="*70)
        print("🚀 STARTING LIVE MODE - ZERODHA WEBSOCKET FEED")
        print("="*70)
        
        # Set execution mode environment variable for all services
        os.environ["EXECUTION_MODE"] = "live"
        print(f"\n🔧 Set EXECUTION_MODE=LIVE (Redis keys will use 'live:' prefix)")
        
        # Ensure credentials
        if not self._ensure_credentials():
            return False
        
        print("\n📊 Configuration:")
        print("   Mode: LIVE")
        print("   Source: Zerodha Kite WebSocket API")
        print("   Credentials: Required ✅")
        print("   Updates: Real-time tick stream")
        print("   Data Isolation: live:* Redis keys")

        # Stop historical, clear virtual time and stale OHLC for a clean slate
        self._stop_historical_service()
        self._prep_live_datastore(mode="live")
        
        print("\n📦 Starting services...")
        self._start_live_services()

        # Set mode via existing mode manager (keeps compatibility)
        cmd = [
            sys.executable, "mode_manager.py",
            "--mode", "live",
            "--start"
        ]

        try:
            result = subprocess.run(cmd, check=False)
            if result.returncode == 0:
                print("\n✅ Live mode started successfully!")
                print("\n📊 Accessing system:")
                print("   Dashboard: http://localhost:8008")
                print("   API: http://localhost:8004")
                return True
        except Exception as e:
            print(f"\n❌ Error starting live mode: {e}")

        return False
    
    def start_historical_mode(self, date: Optional[str] = None, speed: float = 1.0):
        """Start system in HISTORICAL mode"""
        print("\n" + "="*70)
        print("📈 STARTING HISTORICAL MODE - ZERODHA HISTORICAL API")
        print("="*70)
        
        # Use provided date or default to 28 Jan 2026
        if not date:
            date = "2026-01-28"
        
        print(f"\n📊 Configuration:")
        print(f"   Mode: HISTORICAL")
        print(f"   Date: {date}")
        print(f"   Speed: {speed}x")
        print(f"   Source: Zerodha Historical API")
        
        # Validate date format
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            print(f"\n❌ Invalid date format: {date}")
            print("   Use format: YYYY-MM-DD")
            return False
        
        print(f"\n⏳ Market day: {date}")
        print(f"   Duration: ~6.25 hours (9:15 AM - 3:30 PM IST)")
        print(f"   Expected duration at {speed}x speed: {6.25/speed:.1f} hours")
        
        print("\n📦 Starting services...")
        
        # Set mode and start
        cmd = [
            sys.executable, "mode_manager.py",
            "--mode", "historical",
            "--date", date,
            "--speed", str(speed),
            "--start"
        ]
        
        try:
            result = subprocess.run(cmd, check=False)
            if result.returncode == 0:
                print("\n✅ Historical mode started successfully!")
                print(f"\n📊 Accessing system:")
                print(f"   Dashboard: http://localhost:8008")
                print(f"   API: http://localhost:8004")
                print(f"\n⏱️  Virtual time: {date} 09:15 IST")
                print(f"   Replay speed: {speed}x")
                return True
        except Exception as e:
            print(f"\n❌ Error starting historical mode: {e}")
        
        return False
    
    def show_status(self):
        """Show current system status"""
        config = self._load_config()
        mode = config.get("mode", "live").upper()
        date = config.get("date")
        speed = config.get("speed", 1.0)
        
        print("\n" + "="*70)
        print("📊 SYSTEM STATUS")
        print("="*70)
        print(f"\nCurrent Mode: {mode}")
        if date:
            print(f"Date: {date}")
        print(f"Speed: {speed}x")
        
        print("\n📋 Available modes:")
        print("   python start_unified.py --live")
        print("   python start_unified.py --historical [--date YYYY-MM-DD] [--speed 1.0]")
        
        # Show Docker status
        print("\n🐳 Docker services:")
        try:
            subprocess.run(["docker-compose", "ps"], check=False)
        except:
            print("   (Docker not available or not running)")
        
        print("\n" + "="*70)

def main():
    parser = argparse.ArgumentParser(
        description="Unified Startup for Zerodha Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start in LIVE mode (real-time Zerodha feed)
  python start_unified.py --live
  
  # Start in HISTORICAL mode (default 28 Jan 2026 at 1x speed)
  python start_unified.py --historical
  
  # Historical mode for specific date and speed
  python start_unified.py --historical --date 2026-01-27 --speed 10.0
  
  # Show current status
  python start_unified.py --status
  
  # Example: Trade 5 days of historical data at 10x speed
  python start_unified.py --historical --date 2026-01-24 --speed 10.0
        """
    )
    
    parser.add_argument(
        "--live",
        action="store_true",
        help="Start in LIVE mode (Zerodha WebSocket feed)"
    )
    
    parser.add_argument(
        "--historical",
        action="store_true",
        help="Start in HISTORICAL mode (Zerodha API replay)"
    )
    
    parser.add_argument(
        "--date",
        type=str,
        default="2026-01-28",
        help="Date for historical mode (YYYY-MM-DD, default: 2026-01-28)"
    )
    
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Replay speed multiplier (default: 1.0 = real-time)"
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current system status"
    )
    
    args = parser.parse_args()
    
    starter = UnifiedStarter()
    
    try:
        # Show status if no mode selected
        if not args.live and not args.historical and not args.status:
            starter.show_status()
            return
        
        # Handle mode selection
        if args.status:
            starter.show_status()
        elif args.live:
            success = starter.start_live_mode()
            sys.exit(0 if success else 1)
        elif args.historical:
            success = starter.start_historical_mode(args.date, args.speed)
            sys.exit(0 if success else 1)
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
