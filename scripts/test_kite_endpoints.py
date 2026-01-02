"""Test different Zerodha Kite API endpoints to find what works."""

import sys
import os
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kiteconnect import KiteConnect

def test_endpoints():
    """Test different Kite API endpoints."""
    print("=" * 60)
    print("Testing Zerodha Kite API Endpoints")
    print("=" * 60)
    
    # Load credentials
    cred_path = Path("credentials.json")
    if not cred_path.exists():
        print("[ERROR] credentials.json not found")
        return
    
    with open(cred_path) as f:
        creds = json.load(f)
    
    api_key = creds.get("api_key") or creds.get("apiKey")
    access_token = creds.get("access_token") or creds.get("accessToken")
    
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    print(f"[OK] Connected as: {kite.profile().get('user_name')}")
    print()
    
    # Get Bank Nifty token
    instruments = kite.instruments("NSE")
    banknifty = None
    for inst in instruments:
        if inst["tradingsymbol"] == "NIFTY BANK":
            banknifty = inst
            break
    
    if not banknifty:
        print("[ERROR] Bank Nifty not found")
        return
    
    token = banknifty["instrument_token"]
    print(f"[OK] Bank Nifty Token: {token}")
    print()
    
    # Test different endpoints
    endpoints = [
        ("LTP", lambda: kite.ltp([token])),
        ("Quote", lambda: kite.quote([token])),
        ("OHLC", lambda: kite.ohlc([token])),
    ]
    
    print("Testing Endpoints:")
    print("-" * 60)
    
    for name, func in endpoints:
        try:
            result = func()
            if result:
                if token in result:
                    data = result[token]
                    if name == "LTP":
                        price = data.get("last_price")
                        print(f"[OK] {name:10} - Price: ₹{price:,.2f}" if price else f"[NO DATA] {name:10}")
                    elif name == "Quote":
                        price = data.get("last_price") or data.get("net_price")
                        print(f"[OK] {name:10} - Price: ₹{price:,.2f}" if price else f"[NO DATA] {name:10}")
                    elif name == "OHLC":
                        ohlc = data.get("ohlc", {})
                        if ohlc:
                            print(f"[OK] {name:10} - Close: ₹{ohlc.get('close', 0):,.2f}")
                        else:
                            print(f"[NO DATA] {name:10}")
                else:
                    print(f"[NO DATA] {name:10}")
            else:
                print(f"[NO DATA] {name:10}")
        except Exception as e:
            error_msg = str(e)
            if "Insufficient permission" in error_msg:
                print(f"[PERMISSION] {name:10} - Insufficient permission")
            elif "Invalid" in error_msg:
                print(f"[INVALID] {name:10} - {error_msg[:50]}")
            else:
                print(f"[ERROR] {name:10} - {error_msg[:50]}")
    
    print("-" * 60)
    print()
    print("Note: 'Insufficient permission' means API key needs market data access")
    print("      Check permissions at: https://kite.trade/apps")

if __name__ == "__main__":
    test_endpoints()

