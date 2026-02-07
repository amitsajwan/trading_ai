#!/usr/bin/env python3
"""Generate Zerodha login URL to get request token."""

import json

# Load API key from credentials
with open('credentials.json', 'r') as f:
    creds = json.load(f)

# Get API key from market_data/.env.banknifty
with open('market_data/.env.banknifty', 'r') as f:
    for line in f:
        if line.startswith('KITE_API_KEY='):
            api_key = line.split('=', 1)[1].strip()
            break

print("=" * 80)
print("ZERODHA AUTHENTICATION - STEP 1")
print("=" * 80)
print()
print("1. Open this URL in your browser:")
print()
print(f"   https://kite.zerodha.com/connect/login?api_key={api_key}")
print()
print("2. Login with your Zerodha credentials")
print("3. After login, you'll be redirected to a URL like:")
print("   http://127.0.0.1:5000/?request_token=XXXXXXXX&action=login&status=success")
print()
print("4. Copy the REQUEST_TOKEN from that URL")
print()
print("5. Run this command with your token:")
print()
print("   $env:KITE_REQUEST_TOKEN='your_request_token_here'; python complete_auth.py")
print()
print("=" * 80)
