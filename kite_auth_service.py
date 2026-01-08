#!/usr/bin/env python3
"""
Kite Authentication Service

Maintains valid Kite credentials by:
1. Checking token validity periodically
2. Refreshing tokens when needed
3. Updating shared credentials.json file
4. Providing auth status endpoint
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KiteAuthService:
    """Service to manage Kite authentication tokens."""

    def __init__(self, cred_path: str = "credentials.json"):
        self.cred_path = cred_path
        self.api_key = os.getenv("KITE_API_KEY", "")
        self.api_secret = os.getenv("KITE_API_SECRET", "")

    def load_credentials(self) -> Optional[Dict[str, Any]]:
        """Load credentials from file."""
        try:
            if os.path.exists(self.cred_path):
                with open(self.cred_path, 'r', encoding='utf-8-sig') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
        return None

    def save_credentials(self, creds: Dict[str, Any]) -> bool:
        """Save credentials to file."""
        try:
            with open(self.cred_path, 'w', encoding='utf-8') as f:
                json.dump(creds, f, indent=2, ensure_ascii=False)
            logger.info("Credentials updated successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            return False

    def is_token_valid(self, creds: Dict[str, Any]) -> bool:
        """Check if access token is still valid."""
        try:
            access_token = creds.get('access_token') or creds.get('data', {}).get('access_token')
            login_time = creds.get('data', {}).get('login_time')
            
            # Get API key from creds (preferred) or use env
            api_key = creds.get('api_key') or creds.get('KITE_API_KEY') or self.api_key

            if not access_token:
                return False
            
            if not api_key:
                logger.warning("No API key available for token validation")
                return False

            # Check if login time is recent (within 24 hours)
            if login_time:
                try:
                    login_dt = datetime.fromisoformat(login_time.replace('Z', '+00:00'))
                    if datetime.now(login_dt.tzinfo) - login_dt > timedelta(hours=24):
                        logger.info("Token expired (24h limit)")
                        return False
                except Exception as e:
                    logger.warning(f"Could not parse login_time: {e}")

            # Try a simple API call to verify token using KiteConnect (more reliable)
            try:
                from kiteconnect import KiteConnect
                kite = KiteConnect(api_key=api_key)
                kite.set_access_token(access_token)
                profile = kite.profile()
                if profile:
                    logger.info(f"Token validated successfully for user: {profile.get('user_id', 'N/A')}")
                    return True
                else:
                    logger.warning("Token validation returned empty profile")
                    return False
            except ImportError:
                # Fallback to REST API if KiteConnect not available
                headers = {
                    'Authorization': f'token {api_key}:{access_token}',
                    'X-Kite-Version': '3'
                }
                response = requests.get('https://api.kite.trade/user/profile', headers=headers, timeout=10)
                if response.status_code == 200:
                    return True
                else:
                    logger.warning(f"Token validation failed: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return False

    def refresh_token(self, creds: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Refresh access token using refresh token or enctoken."""
        try:
            # Try using enctoken for login (if available)
            enctoken = creds.get('data', {}).get('enctoken')
            if enctoken:
                logger.info("Attempting to refresh using enctoken...")
                # This would require implementing Kite's login flow
                # For now, we'll mark as needing manual refresh
                logger.warning("Enctoken refresh not implemented - manual login required")
                return None

            # Alternative: Use refresh token if available
            refresh_token = creds.get('refresh_token') or creds.get('data', {}).get('refresh_token')
            if refresh_token:
                logger.info("Attempting to refresh using refresh token...")
                # Implement refresh token flow
                # This requires Kite's OAuth refresh endpoint
                pass

            return None

        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None

    def run_auth_check(self):
        """Main authentication check loop."""
        logger.info("Starting Kite authentication service...")

        while True:
            try:
                creds = self.load_credentials()

                if not creds:
                    logger.warning("No credentials file found")
                    time.sleep(300)  # Wait 5 minutes
                    continue

                # Check if token is valid
                if self.is_token_valid(creds):
                    logger.info("Token is valid")
                else:
                    logger.warning("Token is invalid, attempting refresh...")
                    new_creds = self.refresh_token(creds)
                    if new_creds:
                        self.save_credentials(new_creds)
                        logger.info("Token refreshed successfully")
                    else:
                        logger.error("Token refresh failed - manual intervention required")

                # Check every 15 minutes
                time.sleep(900)

            except Exception as e:
                logger.error(f"Auth check error: {e}")
                time.sleep(300)  # Wait 5 minutes on error

def main():
    """Main entry point."""
    service = KiteAuthService()
    service.run_auth_check()

if __name__ == "__main__":
    main()
