#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Mode Manager for Zerodha Trading System
Handles seamless switching between LIVE and HISTORICAL modes
Auto-manages Zerodha authentication and Docker services
"""

import os
import sys
import json

# Fix Windows encoding issues
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import subprocess
from typing import Optional, Dict

class ModeManager:
    """Manage trading mode: LIVE or HISTORICAL"""
    
    CONFIG_FILE = ".mode_config.json"
    
    def __init__(self):
        self.config_file = Path(self.CONFIG_FILE)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load mode configuration"""
        if self.config_file.exists():
            with open(self.config_file) as f:
                return json.load(f)
        return {"mode": "live", "date": None, "speed": 1.0}
    
    def _save_config(self):
        """Save mode configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def set_mode(self, mode: str, date: Optional[str] = None, speed: float = 1.0):
        """Set trading mode"""
        if mode.lower() not in ["live", "historical"]:
            raise ValueError(f"Invalid mode: {mode}. Use 'live' or 'historical'")
        
        self.config["mode"] = mode.lower()
        self.config["date"] = date
        self.config["speed"] = speed
        self._save_config()
        
        print(f"\n✅ Mode set to: {mode.upper()}")
        if date:
            print(f"   Date: {date}")
        print(f"   Speed: {speed}x")
    
    def get_mode(self) -> str:
        """Get current trading mode"""
        return self.config.get("mode", "live")
    
    def get_date(self) -> Optional[str]:
        """Get historical date (if in historical mode)"""
        return self.config.get("date")
    
    def get_speed(self) -> float:
        """Get replay speed"""
        return self.config.get("speed", 1.0)
    
    def display_config(self):
        """Display current configuration"""
        mode = self.get_mode().upper()
        date = self.get_date()
        speed = self.get_speed()
        
        print(f"\n{'='*60}")
        print(f"CURRENT CONFIGURATION")
        print(f"{'='*60}")
        print(f"Mode:  {mode}")
        if date:
            print(f"Date:  {date}")
        print(f"Speed: {speed}x")
        print(f"{'='*60}\n")

class DockerManager:
    """Manage Docker services"""
    
    @staticmethod
    def get_compose_command(mode: str, date: Optional[str] = None) -> list:
        """Build docker-compose command for mode"""
        cmd = ["docker-compose"]
        
        # Start with main compose file
        cmd.extend(["-f", "docker-compose.yml"])
        
        # Add mode-specific override
        if mode.lower() == "historical":
            cmd.extend(["-f", "docker-compose.historical.yml"])
        elif mode.lower() == "live":
            cmd.extend(["-f", "docker-compose.live.yml"])
        
        return cmd
    
    @staticmethod
    def start_services(mode: str, date: Optional[str] = None):
        """Start services for mode"""
        cmd = DockerManager.get_compose_command(mode, date)
        cmd.extend(["up", "-d", "--build"])
        
        print(f"\n📦 Starting Docker services in {mode.upper()} mode...")
        print(f"   Command: {' '.join(cmd)}\n")
        
        try:
            subprocess.run(cmd, check=True)
            print(f"\n✅ Services started successfully")
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Failed to start services: {e}")
            return False
        
        return True
    
    @staticmethod
    def stop_services():
        """Stop all services"""
        cmd = ["docker-compose", "down"]
        print(f"\n🛑 Stopping Docker services...")
        
        try:
            subprocess.run(cmd, check=True)
            print(f"\n✅ Services stopped")
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Failed to stop services: {e}")
            return False
        
        return True
    
    @staticmethod
    def status():
        """Show service status"""
        cmd = ["docker-compose", "ps"]
        try:
            subprocess.run(cmd, check=False)
        except Exception as e:
            print(f"❌ Error checking status: {e}")

class ZerodhaAuthManager:
    """Manage Zerodha authentication"""
    
    CREDS_FILE = "credentials.json"
    
    @staticmethod
    def has_valid_token() -> bool:
        """Check if valid access token exists"""
        if not Path(ZerodhaAuthManager.CREDS_FILE).exists():
            return False
        
        try:
            with open(ZerodhaAuthManager.CREDS_FILE) as f:
                creds = json.load(f)
            
            access_token = creds.get("access_token")
            if not access_token:
                return False
            
            # Could add token expiry check here
            return True
        except:
            return False
    
    @staticmethod
    def get_login_url() -> str:
        """Get Kite Connect login URL"""
        if not Path(ZerodhaAuthManager.CREDS_FILE).exists():
            return None
        
        try:
            with open(ZerodhaAuthManager.CREDS_FILE) as f:
                creds = json.load(f)
            api_key = creds.get("api_key")
            if api_key:
                return f"https://kite.zerodha.com/connect/login?api_key={api_key}&v=3"
        except:
            pass
        
        return None
    
    @staticmethod
    def ensure_authenticated():
        """Ensure Zerodha authentication"""
        print("\n🔐 Checking Zerodha authentication...")
        
        if ZerodhaAuthManager.has_valid_token():
            print("   ✅ Valid credentials found")
            return True
        
        print("   ⚠️  No valid credentials found")
        print("\n   📋 To authenticate:")
        print("      1. Run: python kite_auth_service.py")
        print("      2. Or: python start_local.py (will prompt for login)")
        
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Unified Mode Manager for Zerodha Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Switch to LIVE mode
  python mode_manager.py --mode live
  
  # Switch to HISTORICAL mode for specific date
  python mode_manager.py --mode historical --date 2026-01-28
  
  # Historical with 10x speed
  python mode_manager.py --mode historical --date 2026-01-28 --speed 10.0
  
  # Show current configuration
  python mode_manager.py --status
  
  # Start services for current mode
  python mode_manager.py --start
  
  # Stop all services
  python mode_manager.py --stop
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["live", "historical"],
        help="Trading mode (live or historical)"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Date for historical mode (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Replay speed multiplier for historical mode (default: 1.0)"
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Start Docker services for current mode"
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop all Docker services"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current configuration and service status"
    )
    parser.add_argument(
        "--ps",
        action="store_true",
        help="Show Docker service status (alias for --status)"
    )
    parser.add_argument(
        "--auth",
        action="store_true",
        help="Ensure Zerodha authentication"
    )
    
    args = parser.parse_args()
    
    # Initialize manager
    manager = ModeManager()
    
    try:
        # Handle mode setting
        if args.mode:
            manager.set_mode(args.mode, args.date, args.speed)
        
        # Handle authentication
        if args.auth or args.start:
            if args.start and manager.get_mode() in ["live", "historical"]:
                ZerodhaAuthManager.ensure_authenticated()
        
        # Handle service operations
        if args.start:
            mode = manager.get_mode()
            date = manager.get_date()
            DockerManager.start_services(mode, date)
        
        if args.stop:
            DockerManager.stop_services()
        
        # Handle status/display
        if args.status or args.ps or (not args.mode and not args.start and not args.stop):
            manager.display_config()
            DockerManager.status()
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
