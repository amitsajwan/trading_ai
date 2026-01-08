#!/usr/bin/env python3
"""Kite Authentication Service (in-package)

This module mirrors the functionality previously provided by the top-level
`kite_auth_service.py` but lives under the `market_data` package so it can be
managed and shipped as part of the module.
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
import requests

# Avoid binding `login_via_browser` at module import time so tests can monkeypatch
# the function on the kite_auth module; we'll import it dynamically inside the
# trigger method.

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KiteAuthService:
    """Service to manage Kite authentication tokens."""

    def __init__(self, cred_path: str = "credentials.json"):
        self.cred_path = cred_path
        self.api_key = os.getenv("KITE_API_KEY", "")
        self.api_secret = os.getenv("KITE_API_SECRET", "")
        # Allow interactive login triggered by the service (default enabled)
        self.allow_interactive = os.getenv("KITE_ALLOW_INTERACTIVE_LOGIN", "1") != "0"
        # Token age (hours) after which token is considered stale (default 23)
        try:
            self.max_token_age_hours = int(os.getenv("KITE_TOKEN_MAX_AGE_HOURS", "23"))
        except Exception:
            self.max_token_age_hours = 23

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

            # Check if login time is recent
            if login_time:
                try:
                    login_dt = datetime.fromisoformat(login_time.replace('Z', '+00:00'))
                    if datetime.now(login_dt.tzinfo) - login_dt > timedelta(hours=self.max_token_age_hours):
                        logger.info(f"Token expired ({self.max_token_age_hours}h limit)")
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
        """Refresh access token using refresh token or enctoken.

        Currently, this method contains placeholders because Kite's refresh
        endpoints/flows are not publicly documented in this codebase. If a
        refresh flow is added later, it should return a new credentials dict
        on success.
        """
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

    def trigger_interactive_login(self, timeout: int = 300) -> bool:
        """Trigger the browser-based login flow.

        Returns True if credentials were obtained and saved, False otherwise.
        This will first try to call the `login_via_browser` helper from
        this package, falling back to running the CLI module if needed.
        """
        cred_path = Path(self.cred_path)

        # Try dynamic import so tests can monkeypatch the helper
        try:
            import importlib
            ka = importlib.import_module('market_data.tools.kite_auth')
            login_via_browser = getattr(ka, 'login_via_browser')

            logger.info("Triggering interactive login via in-package helper")
            creds, code = login_via_browser(api_key=self.api_key or None,
                                           api_secret=self.api_secret or None,
                                           force_mode=True,
                                           timeout=timeout)
            if creds and code == 0:
                try:
                    self.save_credentials(creds)
                except Exception:
                    logger.exception("Failed to save credentials returned by login_via_browser")
                logger.info("Interactive login succeeded")
                return True
        except Exception as e:
            logger.warning(f"Interactive import/call failed: {e}, falling back to subprocess")

        # If helper didn't work, try subprocess fallback
        try:
            import subprocess, sys

            before_mtime = cred_path.stat().st_mtime if cred_path.exists() else None
            logger.info("Launching CLI subprocess for interactive login")
            proc = subprocess.Popen([sys.executable, "-m", "market_data.tools.kite_auth"])

            deadline = time.time() + timeout
            while time.time() < deadline:
                if cred_path.exists():
                    mtime = cred_path.stat().st_mtime
                    if before_mtime is None or mtime > before_mtime:
                        # New credentials written
                        logger.info("Detected updated credentials.json after subprocess login")
                        proc.terminate()
                        return True
                time.sleep(1)

            # Timed out
            logger.error("Timed out waiting for credentials.json after subprocess login")
            try:
                proc.terminate()
            except Exception:
                pass
            return False

        except Exception as e:
            logger.exception(f"Subprocess fallback failed: {e}")
            return False

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

                        # If allowed, try interactive browser-based login
                        if self.allow_interactive:
                            logger.info("Attempting interactive login to obtain new credentials")
                            success = self.trigger_interactive_login()
                            if not success:
                                logger.error("Interactive login failed - manual intervention required")
                        else:
                            logger.error("Interactive login disabled (KITE_ALLOW_INTERACTIVE_LOGIN=0); manual intervention required")

                # Check every 15 minutes
                time.sleep(900)

            except Exception as e:
                logger.error(f"Auth check error: {e}")
                time.sleep(300)  # Wait 5 minutes on error


def main():
    service = KiteAuthService()
    service.run_auth_check()


if __name__ == "__main__":
    main()
