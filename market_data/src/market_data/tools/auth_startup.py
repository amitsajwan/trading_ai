#!/usr/bin/env python3
"""
Zerodha Authentication Startup Module

Handles credential validation and interactive login on application startup.
This is the single entry point for all auth operations at launch time.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AuthStartup:
    """Handles authentication on application startup."""
    
    def __init__(self, cred_path: str = "credentials.json"):
        self.cred_path = Path(cred_path)
        self.api_key = os.getenv("KITE_API_KEY", "").strip()
        self.api_secret = os.getenv("KITE_API_SECRET", "").strip()
        self.max_token_age_hours = int(os.getenv("KITE_TOKEN_MAX_AGE_HOURS", "23"))
        logger.info(f"AuthStartup initialized with cred_path: {self.cred_path}")

    def load_credentials(self) -> Optional[Dict[str, Any]]:
        """Load credentials from file."""
        try:
            if self.cred_path.exists():
                with open(self.cred_path, 'r', encoding='utf-8-sig') as f:
                    creds = json.load(f)
                logger.info(f"✅ Credentials loaded from {self.cred_path}")
                return creds
        except Exception as e:
            logger.error(f"❌ Failed to load credentials: {e}")
        return None

    def save_credentials(self, creds: Dict[str, Any]) -> bool:
        """Save credentials to file and environment."""
        try:
            # Save to file
            with open(self.cred_path, 'w', encoding='utf-8') as f:
                json.dump(creds, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Credentials saved to {self.cred_path}")
            
            # Also update environment variables for immediate use
            if 'access_token' in creds:
                os.environ['KITE_ACCESS_TOKEN'] = creds['access_token']
            if 'api_key' in creds:
                os.environ['KITE_API_KEY'] = creds['api_key']
            if 'user_id' in creds:
                os.environ['KITE_USER_ID'] = creds['user_id']
                
            logger.info("✅ Environment variables updated")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to save credentials: {e}")
            return False

    def is_token_valid(self, creds: Optional[Dict[str, Any]]) -> bool:
        """Validate if access token is still valid."""
        if not creds:
            logger.warning("⚠️ No credentials provided for validation")
            return False

        try:
            access_token = creds.get('access_token') or creds.get('data', {}).get('access_token')
            login_time = creds.get('login_time') or creds.get('data', {}).get('login_time')

            if not access_token:
                logger.warning("⚠️ No access token found in credentials")
                return False

            # Check token age
            if login_time:
                try:
                    # Parse ISO format datetime
                    if login_time.endswith('Z'):
                        login_time = login_time.replace('Z', '+00:00')
                    login_dt = datetime.fromisoformat(login_time)
                    age = datetime.now(login_dt.tzinfo) - login_dt if login_dt.tzinfo else (datetime.now() - login_dt.replace(tzinfo=None))
                    
                    if age > timedelta(hours=self.max_token_age_hours):
                        logger.warning(f"⚠️ Token expired (age: {age}, limit: {self.max_token_age_hours}h)")
                        return False
                    else:
                        logger.info(f"✅ Token age check passed ({age})")
                except Exception as e:
                    logger.warning(f"⚠️ Could not parse login_time: {e}")

            # Try API validation with KiteConnect
            try:
                from kiteconnect import KiteConnect
                api_key = creds.get('api_key') or self.api_key
                if not api_key:
                    logger.error("❌ No API key available for validation")
                    return False
                
                kite = KiteConnect(api_key=api_key)
                kite.set_access_token(access_token)
                profile = kite.profile()
                
                if profile:
                    user_id = profile.get('user_id', 'unknown')
                    logger.info(f"✅ Token validated successfully for user: {user_id}")
                    return True
                else:
                    logger.warning("⚠️ Token validation returned empty profile")
                    return False
                    
            except ImportError:
                logger.warning("⚠️ KiteConnect not available; cannot validate token")
                return False
            except Exception as e:
                logger.error(f"❌ Token validation error: {e}")
                return False

        except Exception as e:
            logger.error(f"❌ Unexpected error during token validation: {e}")
            return False

    def trigger_interactive_login(self, timeout: int = 300) -> bool:
        """Trigger interactive browser-based login."""
        logger.info("🔐 Attempting interactive login...")
        
        try:
            # Try dynamic import for in-package helper
            import importlib
            try:
                ka = importlib.import_module('market_data.tools.kite_auth')
                login_via_browser = getattr(ka, 'login_via_browser', None)
                
                if login_via_browser:
                    logger.info("📱 Launching browser-based login...")
                    is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
                    
                    creds, code = login_via_browser(
                        api_key=self.api_key or None,
                        api_secret=self.api_secret or None,
                        force_mode=True,
                        timeout=timeout,
                        docker_mode=is_docker
                    )
                    
                    if creds and code == 0:
                        logger.info("✅ Browser login successful")
                        return self.save_credentials(creds)
                    else:
                        logger.error("❌ Browser login failed or timed out")
                        return False
            except Exception as e:
                logger.warning(f"⚠️ Browser login helper failed: {e}")

            # Fallback: subprocess approach
            logger.info("🔄 Falling back to subprocess login...")
            import subprocess
            
            cred_mtime_before = self.cred_path.stat().st_mtime if self.cred_path.exists() else None
            proc = subprocess.Popen([sys.executable, "-m", "market_data.tools.kite_auth"])
            
            deadline = time.time() + timeout
            while time.time() < deadline:
                if self.cred_path.exists():
                    mtime = self.cred_path.stat().st_mtime
                    if cred_mtime_before is None or mtime > cred_mtime_before:
                        logger.info("✅ Credentials updated by subprocess login")
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        return True
                time.sleep(1)
            
            logger.error(f"❌ Login timed out after {timeout} seconds")
            try:
                proc.terminate()
            except Exception:
                pass
            return False

        except Exception as e:
            logger.error(f"❌ Interactive login error: {e}")
            return False

    def startup_check(self) -> Tuple[bool, str]:
        """
        Perform complete authentication check at startup.
        
        Returns:
            (success: bool, message: str)
        """
        logger.info("\n" + "="*70)
        logger.info("🔐 ZERODHA AUTHENTICATION STARTUP CHECK")
        logger.info("="*70)
        
        # Step 1: Try to load existing credentials
        logger.info("\n📂 Step 1: Checking for saved credentials...")
        creds = self.load_credentials()
        
        if creds:
            logger.info(f"   Found credentials for user: {creds.get('user_id', 'unknown')}")
            
            # Step 2: Validate existing credentials
            logger.info("\n✓ Step 2: Validating token...")
            if self.is_token_valid(creds):
                logger.info("✅ Credentials are valid!")
                return True, "Authenticated with valid token"
            else:
                logger.warning("⚠️ Token is invalid or expired")
        else:
            logger.warning("⚠️ No saved credentials found")
        
        # Step 3: Try environment variables
        logger.info("\n📝 Step 3: Checking environment variables...")
        if self.api_key and os.getenv("KITE_ACCESS_TOKEN"):
            logger.info("   Found API key and token in environment")
            env_creds = {
                'api_key': self.api_key,
                'access_token': os.getenv("KITE_ACCESS_TOKEN"),
                'user_id': os.getenv("KITE_USER_ID", "unknown")
            }
            if self.is_token_valid(env_creds):
                logger.info("✅ Environment credentials are valid!")
                # Save to file for future use
                self.save_credentials(env_creds)
                return True, "Authenticated via environment variables"
        
        # Step 4: Interactive login required
        logger.info("\n🔄 Step 4: Interactive login required...")
        logger.info("   🌐 Opening browser for Zerodha authentication...")
        
        if self.trigger_interactive_login(timeout=300):
            logger.info("✅ Interactive login succeeded!")
            creds = self.load_credentials()
            if creds:
                return True, "Authenticated via interactive login"
        
        logger.error("\n❌ AUTHENTICATION FAILED")
        logger.error("   Could not authenticate with Zerodha")
        return False, "Authentication failed - no valid credentials"

    def run(self) -> bool:
        """Run the authentication startup check. Returns True if successful."""
        try:
            success, message = self.startup_check()
            
            if success:
                logger.info(f"\n✅ {message}")
                logger.info("="*70 + "\n")
                return True
            else:
                logger.error(f"\n❌ {message}")
                logger.error("="*70 + "\n")
                return False
                
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main entry point for authentication startup."""
    auth = AuthStartup()
    success = auth.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
