"""Kite authentication helpers (moved from top-level).

This file contains the same CLI helpers as before but lives under the
`data_niftybank` module (tools package). Keep exports minimal so callers
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
            print(f"✓ Credentials verified for user: {profile.get('user_id')}")
            return True
        except Exception as e:
            print(f"✗ Credential verification failed: {e}")
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
        def do_GET(self):
            query = self.path.split("?")[1] if "?" in self.path else ""
            params = dict(qc.split("=") for qc in query.split("&") if "=" in qc)
            request_token = params.get("request_token")
            if request_token:
                self.server.request_token = request_token
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Login successful! You can close this tab.")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Failed to capture request_token.")

    server = http.server.HTTPServer(("127.0.0.1", 5000), RequestHandler)
    server.request_token = None

    def run_server():
        server.serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return server


def main():
    # Parse command line arguments
    verify_mode = "--verify" in sys.argv
    force_mode = "--force" in sys.argv
    
    # Get API key and secret from environment variables
    api_key = os.environ.get("KITE_API_KEY")
    api_secret = os.environ.get("KITE_API_SECRET")

    if not api_key or not api_secret:
        print("❌ Error: Please set KITE_API_KEY and KITE_API_SECRET as environment variables.")
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
                print("🔍 Verifying existing credentials...")
                if validator.verify_credentials(api_key, existing_creds.get("access_token", "")):
                    print("✓ Existing credentials are valid")
                    return 0
                else:
                    print("✗ Existing credentials are invalid or expired")
                    return 1
            
            # Check if token is still valid
            if validator.is_token_valid(existing_creds):
                print("✓ Valid credentials found (less than 23 hours old)")
                if validator.verify_credentials(api_key, existing_creds.get("access_token", "")):
                    print("✓ Credentials verified with Kite API")
                    print("   Use --force to generate new credentials")
                    return 0
        except Exception as e:
            print(f"⚠ Error reading existing credentials: {e}")
    
    print("🔐 Starting Kite Connect authentication...")
    
    # Initialize KiteConnect
    kite = KiteConnect(api_key=api_key)

    # Start HTTP server to capture request_token
    server = start_http_server()

    # Generate login URL and open in browser
    login_url = kite.login_url()
    print("\n📋 Login URL:")
    print("   ", login_url)
    print("\n🌐 Opening browser... please log in and authorize the app")
    print("   (You have 120 seconds to complete the login)\n")
    
    try:
        webbrowser.open(login_url)
    except Exception as e:
        print(f"⚠ Could not open browser automatically: {e}")
        print("   Please open the URL manually in your browser")

    # Wait for request_token with timeout
    print("⏳ Waiting for authentication...")
    timeout = 120  # 2 minutes
    start_time = time.time()
    
    while not server.request_token:
        if time.time() - start_time > timeout:
            print("\n❌ Timeout: No response received within 120 seconds")
            server.shutdown()
            return 1
        time.sleep(0.5)

    request_token = server.request_token
    server.shutdown()
    print("✓ Request token received")

    # Exchange request_token for access_token with retry
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"🔄 Generating session (attempt {attempt + 1}/{max_retries})...")
            data = kite.generate_session(request_token, api_secret=api_secret)
            break
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"\n❌ Failed to generate session after {max_retries} attempts: {e}")
                return 1
            print(f"⚠ Attempt {attempt + 1} failed: {e}")
            time.sleep(2)

    kite.set_access_token(data["access_token"])
    print("✓ Access token generated")

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
        print("✓ Backed up existing credentials")
    
    # Save new credentials
    out.write_text(json.dumps(cred, indent=2))
    print(f"\n✓ Credentials saved to: {out.resolve()}")
    print(f"✓ Logged in as: {data.get('user_id')}")
    print(f"✓ Login time: {data.get('login_time')}")
    print(f"✓ Token expires: {(datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Verify the saved credentials
    print("\n🔍 Verifying saved credentials...")
    if validator.verify_credentials(api_key, cred["access_token"]):
        print("✓ All systems ready! You can now start the trading containers.")
        return 0
    else:
        print("⚠ Credentials saved but verification failed. Please try again.")
        return 1

if __name__ == "__main__":
    exit(main())