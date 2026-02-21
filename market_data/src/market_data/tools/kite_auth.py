"""Kite authentication helpers (moved from top-level).

This file contains the same CLI helpers as before but lives under the
`market_data` module (tools package). Keep exports minimal so callers
use `main()`.
"""

# Copied from top-level auto_login.py with no behavior changes
import os
import sys
import webbrowser
import json
from pathlib import Path
from kiteconnect import KiteConnect
from datetime import datetime, timedelta
import http.server
import threading
import time
from urllib.parse import unquote
from dotenv import load_dotenv
from typing import Optional, Dict, Any
from market_data.kite_client import create_kite_client

def _load_dotenv_candidates() -> None:
    """Load env vars from common project .env locations, independent of cwd."""
    if (os.environ.get("KITE_SKIP_DOTENV_LOAD") or "").strip() in ("1", "true", "yes"):
        return
    try:
        here = Path(__file__).resolve()
        candidates = [
            Path.cwd() / ".env",
            here.parents[4] / ".env",  # trading_ai/.env
            here.parents[4] / "market_data" / ".env",
        ]
        for p in candidates:
            if p.exists():
                load_dotenv(dotenv_path=p, override=False)
    except Exception:
        # Keep auth flow resilient even if env-file discovery fails.
        pass


# Load environment variables at import time using stable paths.
_load_dotenv_candidates()

class CredentialsValidator:
    """Validates and manages Kite Connect credentials."""
    
    @staticmethod
    def is_token_valid(credentials: Dict[str, Any]) -> bool:
        """Check if access token is still valid (less than 24 hours old)."""
        if not credentials.get("access_token"):
            return False
        
        login_time_str = credentials.get("data", {}).get("login_time")
        if not login_time_str:
            return False
        
        try:
            login_time = datetime.fromisoformat(login_time_str)
            # Kite tokens expire after 24 hours
            return datetime.now() - login_time < timedelta(hours=23)
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def verify_credentials(api_key: str, access_token: str) -> bool:
        """Verify credentials by making a test API call."""
        try:
            kite = create_kite_client(api_key=api_key, access_token=access_token)
            # Test API call
            profile = kite.profile()
            print(f"Credentials verified for user: {profile.get('user_id')}")
            return True
        except Exception as e:
            print(f"Credential verification failed: {e}")
            return False


def get_env_or_prompt(name: str) -> str:
    """Get environment variable or prompt the user."""
    val = os.environ.get(name)
    if val:
        return val
    return input(f"Enter {name}: ").strip()


def serialize_data(data):
    """Convert datetime objects in the data dictionary to strings."""
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    return data


def start_http_server(port: int = 5000):
    """Start a local HTTP server to capture the request_token.

    Uses a fixed callback port (default 5000) so Kite app redirect URI stays stable.
    """
    class RequestHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Suppress default logging
            pass
        
        def do_GET(self):
            # Handle any path (/, /login, etc.) and extract request_token from query string
            query_string = ""
            if "?" in self.path:
                query_string = self.path.split("?")[1]
            
            # Parse query parameters
            params = {}
            if query_string:
                for param in query_string.split("&"):
                    if "=" in param:
                        key, value = param.split("=", 1)
                        params[key] = value
            
            request_token = params.get("request_token")
            status = params.get("status", "")
            
            if request_token:
                self.server.request_token = request_token
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                success_msg = b"""
                <html>
                <head><title>Login Successful</title></head>
                <body>
                    <h1>Login Successful!</h1>
                    <p>You can close this tab and return to the terminal.</p>
                    <p>Request token received: """ + request_token.encode() + b"""</p>
                </body>
                </html>
                """
                self.wfile.write(success_msg)
                print(f"\n[SUCCESS] Request token received: {request_token[:20]}...")
            elif status == "success" and not request_token:
                # Sometimes Zerodha redirects with status=success but token in different format
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Processing...</h1><p>Please check the terminal for status.</p></body></html>")
                print(f"\n[WARNING] Received status=success but no request_token in URL")
                print(f"   Full path: {self.path}")
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                error_msg = b"""
                <html>
                <head><title>Login Failed</title></head>
                <body>
                    <h1>Failed to capture request_token</h1>
                    <p>Please check the terminal for error messages.</p>
                    <p>Path: """ + self.path.encode() + b"""</p>
                </body>
                </html>
                """
                self.wfile.write(error_msg)
                print(f"\n[WARNING] Failed to capture request_token from path: {self.path}")

    configured_port = (os.environ.get("KITE_AUTH_CALLBACK_PORT") or "").strip()
    if configured_port:
        try:
            port = int(configured_port)
        except ValueError:
            raise RuntimeError(
                f"Invalid KITE_AUTH_CALLBACK_PORT='{configured_port}'. Expected an integer port."
            )

    try:
        server = http.server.HTTPServer(("127.0.0.1", port), RequestHandler)
        server.request_token = None
        print(f"[OK] HTTP server started on http://127.0.0.1:{port}")
    except OSError as e:
        raise RuntimeError(
            f"Could not start HTTP server on 127.0.0.1:{port}. "
            f"Ensure this port is free and set Kite redirect URI to http://127.0.0.1:{port}/login. "
            f"Original error: {e}"
        ) from e

    def run_server():
        server.serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    
    # Give server a moment to start
    time.sleep(0.5)
    
    return server


def login_via_browser(api_key: Optional[str] = None,
                      api_secret: Optional[str] = None,
                      verify_mode: bool = False,
                      force_mode: bool = False,
                      timeout: int = 120,
                      docker_mode: bool = False):
    """Perform the browser-based Kite Connect login flow.

    Returns a tuple: (credentials_dict | None, exit_code)
    - credentials_dict: dict written to `credentials.json` on success (or existing creds if valid)
    - exit_code: 0 on success, non-zero on failure
    """
    # Resolve keys from environment if not provided
    _load_dotenv_candidates()
    if api_key is None:
        api_key = os.environ.get("KITE_API_KEY")
    if api_secret is None:
        api_secret = os.environ.get("KITE_API_SECRET")

    # Fallback: infer from local credentials.json when env isn't available.
    if (not api_key or not api_secret):
        try:
            cred_candidates = [Path.cwd() / "credentials.json"]
            configured_cred = (os.environ.get("KITE_CREDENTIALS_PATH") or "").strip()
            if configured_cred:
                cred_candidates.insert(0, Path(configured_cred))
            for cp in cred_candidates:
                if not cp.exists():
                    continue
                payload = json.loads(cp.read_text(encoding="utf-8-sig"))
                if not api_key:
                    api_key = payload.get("api_key") or payload.get("KITE_API_KEY")
                if not api_secret:
                    api_secret = payload.get("api_secret") or payload.get("KITE_API_SECRET")
                if api_key and api_secret:
                    break
        except Exception:
            pass

    if not api_key or not api_secret:
        print("Error: Please set KITE_API_KEY and KITE_API_SECRET as environment variables.")
        print("   Or add them to your .env file")
        return None, 1

    # Check existing credentials
    cred_path = Path("credentials.json")
    validator = CredentialsValidator()

    if cred_path.exists() and not force_mode:
        try:
            existing_creds = json.loads(cred_path.read_text())

            if verify_mode:
                # Verify existing credentials
                print("Verifying existing credentials...")
                if validator.verify_credentials(api_key, existing_creds.get("access_token", "")):
                    print("[OK] Existing credentials are valid")
                    return existing_creds, 0
                else:
                    print("Existing credentials are invalid or expired")
                    return None, 1

            # Check if token is still valid
            if validator.is_token_valid(existing_creds):
                print("Valid credentials found (less than 23 hours old)")
                if validator.verify_credentials(api_key, existing_creds.get("access_token", "")):
                    print("Credentials verified with Kite API")
                    print("   Use --force to generate new credentials")
                    return existing_creds, 0
        except Exception as e:
            print(f"Error reading existing credentials: {e}")

    print("Starting Kite Connect authentication...")

    # Initialize KiteConnect
    kite = create_kite_client(api_key=api_key)

    # Start HTTP server to capture request_token
    server = start_http_server()
    server_port = server.server_address[1]
    redirect_uri = f"http://127.0.0.1:{server_port}/login"

    print(f"\n[INFO] Redirect URI: {redirect_uri}")
    print("   [WARNING] IMPORTANT: Make sure this redirect URI is configured in your Kite Connect app settings!")
    print("   [INFO] Go to: https://kite.zerodha.com/apps/")
    print("   [INFO] Edit your app and add this redirect URI if not already present\n")

    # Generate login URL with explicit redirect_uri
    # Note: login_url() may use default redirect_uri from Kite Connect app settings
    # If redirect_uri doesn't match, you'll get "URL not found" error
    try:
        # Try to pass redirect_uri if supported
        login_url = kite.login_url()
    except Exception as e:
        print(f"Error generating login URL: {e}")
        return None, 1

    print("Login URL:")
    print("   ", login_url)
    print(f"\n[WARNING] IMPORTANT: The redirect URI in your Kite Connect app must match:")
    print(f"   {redirect_uri}")
    print(f"\n[INFO] If you get 'URL not found' error, check:")
    print(f"   1. Go to https://kite.zerodha.com/apps/")
    print(f"   2. Edit your app (API Key: {api_key[:8]}...)")
    print(f"   3. Add/verify redirect URI: {redirect_uri}")
    print(f"   4. Also try: http://127.0.0.1:{server_port}/ (without /login)")
    print("\nPlease open the following URL in your browser and log in:")
    print(f"   {login_url}")
    print(f"   (You have {timeout} seconds to complete the login)\n")

    # Try to open browser automatically, even in Docker
    # If it fails, fall back to manual instructions
    try:
        webbrowser.open(login_url)
        print("Browser opened automatically. Please complete the login.")
    except Exception as e:
        print(f"Could not open browser automatically: {e}")
        print("Please open the following URL manually in your browser:")
        print(f"   {login_url}")

    if docker_mode:
        print("\n" + "="*80)
        print("DOCKER MODE: Authentication URL")
        print("="*80)
        print("Copy and open this URL in your browser:")
        print(f"   {login_url}")
        print("2. Log in with your Zerodha credentials")
        print("3. Complete the authentication flow")
        print("4. The system will automatically detect when authentication is complete")
        print("="*80 + "\n")

    # Wait for request_token with timeout
    print("Waiting for authentication...")
    start_time = time.time()

    while not server.request_token:
        if time.time() - start_time > timeout:
            print(f"\nTimeout: No response received within {timeout} seconds")
            server.shutdown()
            return None, 1
        time.sleep(0.5)

    request_token = server.request_token
    server.shutdown()
    print("Request token received")

    # Exchange request_token for access_token with retry
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Generating session (attempt {attempt + 1}/{max_retries})...")
            data = kite.generate_session(request_token, api_secret=api_secret)
            break
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"\nFailed to generate session after {max_retries} attempts: {e}")
                return None, 1
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2)

    kite.set_access_token(data["access_token"])
    print("Access token generated")

    # Serialize datetime objects to strings
    data = serialize_data(data)

    # Save credentials
    cred = {
        "api_key": api_key,
        "api_secret": api_secret,
        "access_token": data.get("access_token"),
        "user_id": data.get("user_id"),
        "data": data,
    }

    out = Path("credentials.json")

    # Backup existing credentials if they exist
    if out.exists():
        backup = Path("credentials.json.backup")
        backup.write_text(out.read_text())
        print("Backed up existing credentials")

    # Save new credentials
    out.write_text(json.dumps(cred, indent=2))
    print(f"\nCredentials saved to: {out.resolve()}")
    print(f"Logged in as: {data.get('user_id')}")
    print(f"Login time: {data.get('login_time')}")
    print(f"Token expires: {(datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')}")

    # Verify the saved credentials
    print("\nVerifying saved credentials...")
    if validator.verify_credentials(api_key, cred["access_token"]):
        print("All systems ready! You can now start the trading containers.")
        return cred, 0
    else:
        print("Credentials saved but verification failed. Please try again.")
        return cred, 1


def main():
    # CLI wrapper preserves original behavior (exit codes)
    verify_mode = "--verify" in sys.argv
    force_mode = "--force" in sys.argv
    docker_mode = "--docker" in sys.argv or os.environ.get('DOCKER_CONTAINER') == 'true'

    creds, code = login_via_browser(verify_mode=verify_mode, force_mode=force_mode, docker_mode=docker_mode)
    return code


if __name__ == "__main__":
    exit(main())
