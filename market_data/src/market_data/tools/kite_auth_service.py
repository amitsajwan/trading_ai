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
from market_data.env_settings import redis_config
from market_data.kite_client import create_kite_client

# Avoid binding `login_via_browser` at module import time so tests can monkeypatch
# the function on the kite_auth module; we'll import it dynamically inside the
# trigger method.

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KiteAuthService:
    """Service to manage Kite authentication tokens."""

    def __init__(self, cred_path: str = "credentials.json"):
        print("DEBUG: Initializing KiteAuthService")
        logger.info("Initializing KiteAuthService")
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
        
        # Redis client for publishing auth status
        self.redis_client = None
        try:
            import redis
            redis_cfg = redis_config(decode_responses=True)
            self.redis_client = redis.Redis(**redis_cfg)
            # Test connection
            self.redis_client.ping()
            logger.info(
                "Redis client initialized successfully (host: %s:%s)",
                redis_cfg.get("host"),
                redis_cfg.get("port"),
            )
        except Exception as e:
            logger.warning(f"Redis not available for auth status publishing: {e}")

    def publish_auth_status(self, status: str, message: str, details: Optional[Dict[str, Any]] = None):
        """Publish authentication status to Redis for dashboard display."""
        if not self.redis_client:
            logger.warning("Redis client not available for publishing auth status")
            return
        
        try:
            auth_status = {
                "type": "auth_status",
                "status": status,  # "authenticated", "failed", "expired", "pending"
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "details": details or {}
            }
            
            # Publish to auth status channel
            self.redis_client.publish("auth:status", json.dumps(auth_status))
            
            # Also store latest status in Redis
            self.redis_client.setex(
                "auth:status:latest",
                3600,  # 1 hour expiry
                json.dumps(auth_status)
            )
            
            logger.info(f"Published auth status: {status} - {message}")
        except Exception as e:
            logger.error(f"Failed to publish auth status: {e}")

    @staticmethod
    def _read_json_file(path: Path) -> Optional[Dict[str, Any]]:
        """Safely read a JSON object from disk."""
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            logger.error(f"Failed to read JSON file {path}: {e}")
        return None

    @staticmethod
    def _extract_access_token(payload: Dict[str, Any]) -> Optional[str]:
        """Extract access_token from common payload shapes."""
        token = payload.get("access_token")
        if not token and isinstance(payload.get("data"), dict):
            token = payload["data"].get("access_token")
        return token

    def load_credentials(self) -> Optional[Dict[str, Any]]:
        """Load credentials from credentials.json and optional access_token.json.

        Merge strategy:
        - Base object comes from credentials.json (self.cred_path) if present.
        - If access_token.json exists alongside credentials, its token overrides
          stale token fields in the base object.
        """
        cred_path = Path(self.cred_path)
        creds = self._read_json_file(cred_path) or {}

        token_override = None
        token_login_time = None

        # Optional sidecar token file support.
        token_path_override = (os.getenv("KITE_ACCESS_TOKEN_PATH") or "").strip()
        token_candidates = []
        if token_path_override:
            token_candidates.append(Path(token_path_override))
        token_candidates.append(cred_path.with_name("access_token.json"))

        for token_path in token_candidates:
            token_payload = self._read_json_file(token_path)
            if not token_payload:
                continue
            token = self._extract_access_token(token_payload)
            if token:
                token_override = token
                token_login_time = (
                    token_payload.get("login_time")
                    or (token_payload.get("data") or {}).get("login_time")
                    or token_payload.get("timestamp")
                )
                break

        if token_override:
            creds["access_token"] = token_override
            data_obj = creds.get("data") if isinstance(creds.get("data"), dict) else {}
            data_obj["access_token"] = token_override
            if token_login_time and not data_obj.get("login_time"):
                data_obj["login_time"] = token_login_time
            creds["data"] = data_obj

        # Fill from environment when file does not include api_key.
        if not creds.get("api_key") and self.api_key:
            creds["api_key"] = self.api_key
        if not creds.get("api_secret") and self.api_secret:
            creds["api_secret"] = self.api_secret

        if not creds:
            return None
        return creds

    def save_credentials(self, creds: Dict[str, Any]) -> bool:
        """Save credentials to file."""
        try:
            with open(self.cred_path, 'w', encoding='utf-8') as f:
                json.dump(creds, f, indent=2, ensure_ascii=False)
            # Keep current process in sync with newly saved credentials.
            api_key = creds.get("api_key")
            access_token = creds.get("access_token") or (creds.get("data") or {}).get("access_token")
            if api_key:
                os.environ["KITE_API_KEY"] = str(api_key)
            if access_token:
                os.environ["KITE_ACCESS_TOKEN"] = str(access_token)
            logger.info("Credentials updated successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            return False

    def is_token_valid(self, creds: Dict[str, Any]) -> bool:
        """Check if access token is still valid."""
        try:
            access_token = creds.get('access_token') or creds.get('data', {}).get('access_token')
            login_time = (
                creds.get('data', {}).get('login_time')
                or creds.get('login_time')
                or creds.get('timestamp')
            )

            # Get API key from creds (preferred) or use env
            api_key = creds.get('api_key') or creds.get('KITE_API_KEY') or self.api_key

            if not access_token:
                return False

            if not api_key:
                logger.warning("No API key available for token validation")
                return False

            # Check if login time is recent
            token_fresh = False
            if login_time:
                try:
                    login_dt = datetime.fromisoformat(login_time.replace('Z', '+00:00'))
                    token_age = datetime.now(login_dt.tzinfo) - login_dt
                    if token_age > timedelta(hours=self.max_token_age_hours):
                        logger.info(f"Token expired ({self.max_token_age_hours}h limit)")
                        return False
                    token_fresh = True
                except Exception as e:
                    logger.warning(f"Could not parse login_time: {e}")

            # Try a simple API call to verify token using KiteConnect (more reliable)
            try:
                kite = create_kite_client(api_key=api_key, access_token=access_token)
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
            except requests.exceptions.RequestException as e:
                # Transient network/SSL failure should not force immediate re-auth if token is still fresh.
                if token_fresh:
                    logger.warning(
                        "Token validation skipped due to network/SSL issue, keeping fresh token as valid: %s",
                        e,
                    )
                    return True
                logger.error("Token validation error: %s", e)
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
        callback_port = (os.environ.get("KITE_AUTH_CALLBACK_PORT") or "5000").strip()
        if not os.environ.get("KITE_AUTH_CALLBACK_PORT"):
            os.environ["KITE_AUTH_CALLBACK_PORT"] = callback_port

        # Check if running in Docker
        is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'

        # Try dynamic import so tests can monkeypatch the helper
        try:
            import importlib
            ka = importlib.import_module('market_data.tools.kite_auth')
            login_via_browser = getattr(ka, 'login_via_browser')

            logger.info("Triggering interactive login via in-package helper")
            if is_docker:
                logger.info("Running in Docker - authentication URL will be displayed for manual login")
                # In Docker, we need to handle login differently
                creds, code = login_via_browser(api_key=self.api_key or None,
                                               api_secret=self.api_secret or None,
                                               force_mode=True,
                                               timeout=timeout,
                                               docker_mode=True)
            else:
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
            if is_docker:
                logger.info("Running in Docker - subprocess will display authentication URL")
            env = os.environ.copy()
            env["KITE_AUTH_CALLBACK_PORT"] = callback_port
            auth_cwd = str(cred_path.parent) if cred_path.parent else None
            try:
                proc = subprocess.Popen(
                    [sys.executable, "-m", "market_data.tools.kite_auth"],
                    env=env,
                    cwd=auth_cwd,
                )
            except TypeError:
                # Test doubles may not accept keyword args like env/cwd.
                proc = subprocess.Popen([sys.executable, "-m", "market_data.tools.kite_auth"])

            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    poll_fn = getattr(proc, "poll", None)
                    if callable(poll_fn):
                        exit_code = poll_fn()
                        if exit_code is not None:
                            logger.error(
                                f"Auth subprocess exited early (code={exit_code}) before credentials were written. "
                                f"Ensure redirect URI is http://127.0.0.1:{callback_port}/login and port {callback_port} is free."
                            )
                            return False
                except Exception:
                    pass
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
                    self.publish_auth_status("failed", "No credentials file found. Please complete authentication.", {
                        "action_required": "manual_login",
                        "url": "http://localhost:8000/auth"  # Dashboard auth page
                    })
                    time.sleep(300)  # Wait 5 minutes
                    continue

                # Check if token is valid
                if self.is_token_valid(creds):
                    logger.info("Token is valid")
                    self.publish_auth_status("authenticated", "Successfully authenticated with Zerodha", {
                        "user_id": creds.get("user_id", "unknown")
                    })
                else:
                    logger.warning("Token is invalid, attempting refresh...")
                    self.publish_auth_status("expired", "Access token expired, attempting refresh...")
                    
                    new_creds = self.refresh_token(creds)
                    if new_creds:
                        self.save_credentials(new_creds)
                        logger.info("Token refreshed successfully")
                        self.publish_auth_status("authenticated", "Token refreshed successfully", {
                            "user_id": new_creds.get("user_id", "unknown")
                        })
                    else:
                        logger.error("Token refresh failed - manual intervention required")
                        self.publish_auth_status("failed", "Token refresh failed. Manual authentication required.", {
                            "action_required": "manual_login",
                            "url": "http://localhost:8000/auth"
                        })

                        # If allowed, try interactive browser-based login
                        if self.allow_interactive:
                            logger.info("Attempting interactive login to obtain new credentials")
                            self.publish_auth_status("pending", "Attempting automatic authentication...")
                            success = self.trigger_interactive_login()
                            if not success:
                                logger.error("Interactive login failed - manual intervention required")
                                self.publish_auth_status("failed", "Automatic authentication failed. Please complete manual login.", {
                                    "action_required": "manual_login",
                                    "url": "http://localhost:8000/auth"
                                })
                            else:
                                self.publish_auth_status("authenticated", "Authentication successful")
                        else:
                            logger.error("Interactive login disabled (KITE_ALLOW_INTERACTIVE_LOGIN=0); manual intervention required")
                            self.publish_auth_status("failed", "Interactive login disabled. Manual authentication required.", {
                                "action_required": "manual_login",
                                "url": "http://localhost:8000/auth"
                            })

                # Check every 15 minutes
                time.sleep(900)

            except Exception as e:
                logger.error(f"Auth check error: {e}")
                self.publish_auth_status("error", f"Authentication service error: {str(e)}")
                time.sleep(300)  # Wait 5 minutes on error


def main():
    service = KiteAuthService()
    service.run_auth_check()


if __name__ == "__main__":
    main()
