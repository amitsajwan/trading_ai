"""Get enctoken from Zerodha Kite Connect session."""

import sys
import json
from pathlib import Path
from kiteconnect import KiteConnect
from dotenv import load_dotenv
import os

load_dotenv()

def get_enctoken():
    """Get enctoken from Kite Connect session."""
    print("=" * 60)
    print("Getting Zerodha WebSocket enctoken")
    print("=" * 60)
    
    # Load credentials
    cred_path = Path("credentials.json")
    if not cred_path.exists():
        print("[ERROR] credentials.json not found")
        print("        Run: python -m market_data.tools.kite_auth")
        return None
    
    with open(cred_path) as f:
        creds = json.load(f)
    
    api_key = creds.get("api_key") or creds.get("apiKey")
    access_token = creds.get("access_token") or creds.get("accessToken")
    user_id = creds.get("user_id") or creds.get("userId")
    
    if not api_key or not access_token:
        print("[ERROR] Missing api_key or access_token")
        return None
    
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    print(f"[OK] API Key: {api_key[:10]}...")
    print(f"[OK] User ID: {user_id}")
    
    # Try to get enctoken from session
    # Note: KiteTicker internally gets enctoken, but we can't access it directly
    # However, we can test if WebSocket works by using KiteTicker
    
    print()
    print("Note: KiteTicker automatically handles enctoken internally")
    print("      The WebSocket URL you see in browser uses enctoken,")
    print("      but KiteTicker class handles this automatically.")
    print()
    print("To test WebSocket connection:")
    print("  python -m data.run_ingestion")
    print()
    print("If WebSocket doesn't work, you may need:")
    print("  1. Market Data subscription (Rs 500/month)")
    print("  2. Or wait for market hours (9:15 AM - 3:30 PM IST)")
    
    # Check if we can get enctoken from any API endpoint
    try:
        # Some Kite Connect versions expose enctoken in profile or other endpoints
        profile = kite.profile()
        print()
        print(f"[OK] Profile fetched: {profile.get('user_name', 'Unknown')}")
        
        # Try to get instruments (this might reveal if we have market data access)
        instruments = kite.instruments("NSE")
        print(f"[OK] Instruments fetched: {len(instruments)} instruments")
        
    except Exception as e:
        print(f"[WARN] Error: {e}")
    
    return {
        "api_key": api_key,
        "user_id": user_id,
        "access_token": access_token[:20] + "..." if access_token else None
    }

if __name__ == "__main__":
    result = get_enctoken()
    if result:
        print()
        print("=" * 60)
        print("Setup Complete")
        print("=" * 60)
        print()
        print("Next steps:")
        print("  1. Start WebSocket: python -m data.run_ingestion")
        print("  2. Check logs for connection status")
        print("  3. If no data, check market hours or subscription")


