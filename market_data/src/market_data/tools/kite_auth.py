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

# Load environment variables from .env file
load_dotenv()

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
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
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


def start_http_server():
    """Start a local HTTP server to capture the request_token."""
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
                print(f"\n✓ Request token received: {request_token[:20]}...")
            elif status == "success" and not request_token:
                # Sometimes Zerodha redirects with status=success but token in different format
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Processing...</h1><p>Please check the terminal for status.</p></body></html>")
                print(f"\n⚠️  Received status=success but no request_token in URL")
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
                print(f"\n⚠️  Failed to capture request_token from path: {self.path}")

    # Try to find an available port (start with 5000, try others if needed)
    port = 5000
    max_attempts = 10
    server = None
    
    for attempt in range(max_attempts):
        try:
            server = http.server.HTTPServer(("127.0.0.1", port), RequestHandler)
            server.request_token = None
            print(f"✓ HTTP server started on http://127.0.0.1:{port}")
            break
        except OSError as e:
            if "Address already in use" in str(e) or "address is already in use" in str(e).lower():
                port += 1
                if attempt < max_attempts - 1:
                    print(f"⚠️  Port {port-1} in use, trying {port}...")
                    continue
            raise
    
    if server is None:
        raise RuntimeError(f"Could not start HTTP server on any port (tried {5000}-{5000+max_attempts-1})")

    def run_server():
        server.serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    
    # Give server a moment to start
    time.sleep(0.5)
    
    return server


def main():
    # Parse command line arguments
    verify_mode = "--verify" in sys.argv
    force_mode = "--force" in sys.argv
    
    # Get API key and secret from environment variables
    api_key = os.environ.get("KITE_API_KEY")
    api_secret = os.environ.get("KITE_API_SECRET")

    if not api_key or not api_secret:
        print("Error: Please set KITE_API_KEY and KITE_API_SECRET as environment variables.")
        print("   Or add them to your .env file")
        return 1

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
                    print("✓ Existing credentials are valid")
                    return 0
                else:
                    print("Existing credentials are invalid or expired")
                    return 1
            
            # Check if token is still valid
            if validator.is_token_valid(existing_creds):
                print("Valid credentials found (less than 23 hours old)")
                if validator.verify_credentials(api_key, existing_creds.get("access_token", "")):
                    print("Credentials verified with Kite API")
                    print("   Use --force to generate new credentials")
                    return 0
        except Exception as e:
            print(f"Error reading existing credentials: {e}")

    print("Starting Kite Connect authentication...")

    # Initialize KiteConnect
    kite = KiteConnect(api_key=api_key)

    # Start HTTP server to capture request_token
    server = start_http_server()
    server_port = server.server_address[1]
    redirect_uri = f"http://127.0.0.1:{server_port}/login"
    
    print(f"\n📋 Redirect URI: {redirect_uri}")
    print("   ⚠️  IMPORTANT: Make sure this redirect URI is configured in your Kite Connect app settings!")
    print("   💡 Go to: https://kite.zerodha.com/apps/")
    print("   💡 Edit your app and add this redirect URI if not already present\n")

    # Generate login URL with explicit redirect_uri
    # Note: login_url() may use default redirect_uri from Kite Connect app settings
    # If redirect_uri doesn't match, you'll get "URL not found" error
    try:
        # Try to pass redirect_uri if supported
        login_url = kite.login_url()
    except Exception as e:
        print(f"Error generating login URL: {e}")
        return 1
    
    print("Login URL:")
    print("   ", login_url)
    print(f"\n⚠️  IMPORTANT: The redirect URI in your Kite Connect app must match:")
    print(f"   {redirect_uri}")
    print(f"\n💡 If you get 'URL not found' error, check:")
    print(f"   1. Go to https://kite.zerodha.com/apps/")
    print(f"   2. Edit your app (API Key: {api_key[:8]}...)")
    print(f"   3. Add/verify redirect URI: {redirect_uri}")
    print(f"   4. Also try: http://127.0.0.1:{server_port}/ (without /login)")
    print("\nOpening browser... please log in and authorize the app")
    print("   (You have 120 seconds to complete the login)\n")

    try:
        webbrowser.open(login_url)
    except Exception as e:
        print(f"Could not open browser automatically: {e}")
        print("   Please open the URL manually in your browser")

    # Wait for request_token with timeout
    print("Waiting for authentication...")
    timeout = 120  # 2 minutes
    start_time = time.time()

    while not server.request_token:
        if time.time() - start_time > timeout:
            print("\nTimeout: No response received within 120 seconds")
            server.shutdown()
            return 1
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
                return 1
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
        return 0
    else:
        print("Credentials saved but verification failed. Please try again.")
        return 1

if __name__ == "__main__":
    exit(main())
