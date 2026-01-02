"""Automated Kite Connect login and session generation.

This script combines the functionality of `login_test.py` and `generate_session.py`.
It generates the login URL, opens it in the browser, and exchanges the request_token
for an access_token, saving the credentials to `credentials.json`.

Usage:
  python auto_login.py
"""
import os
import webbrowser
import json
from pathlib import Path
from kiteconnect import KiteConnect
from datetime import datetime
import http.server
import threading
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_env_or_prompt(name):
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
    # Get API key and secret from environment variables
    api_key = os.environ.get("KITE_API_KEY")
    api_secret = os.environ.get("KITE_API_SECRET")

    if not api_key or not api_secret:
        print("Error: Please set KITE_API_KEY and KITE_API_SECRET as environment variables.")
        return

    # Initialize KiteConnect
    kite = KiteConnect(api_key=api_key)

    # Start HTTP server to capture request_token
    server = start_http_server()

    # Generate login URL and open in browser
    login_url = kite.login_url()
    print("Login URL:\n", login_url)
    print("Opening browser... log in and wait for the redirect.")
    webbrowser.open(login_url)

    # Wait for request_token
    print("Waiting for request_token...")
    while not server.request_token:
        pass

    request_token = server.request_token
    server.shutdown()

    # Exchange request_token for access_token
    try:
        data = kite.generate_session(request_token, api_secret=api_secret)
    except Exception as e:
        print("Failed to generate session:", e)
        return

    kite.set_access_token(data["access_token"])

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
    out.write_text(json.dumps(cred, indent=2))
    print("Saved credentials to", out.resolve())
    print("Logged in as:", data.get("user_id"))

if __name__ == "__main__":
    main()