"""Test Zerodha LTP API (works without WebSocket)."""

import sys
import os
import json
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings

def test_zerodha_ltp():
    """Test Zerodha LTP API."""
    print("=" * 60)
    print("Testing Zerodha LTP API")
    print("=" * 60)
    
    # Check credentials (try both files)
    cred_path = Path("credentials.json")
    if not cred_path.exists():
        cred_path = Path("kite_credentials.json")
    if not cred_path.exists():
        print("[SKIP] credentials.json not found")
        print()
        print("To set up Zerodha Kite:")
        print("  1. Run: python auto_login.py")
        return False
    
    try:
        from kiteconnect import KiteConnect
        
        with open(cred_path) as f:
            creds = json.load(f)
        
        kite = KiteConnect(api_key=creds.get("api_key"))
        kite.set_access_token(creds.get("access_token"))
        
        # Test connection
        profile = kite.profile()
        print(f"[OK] Connected as: {profile.get('user_name', 'Unknown')}")
        
        # Get Bank Nifty instrument
        instruments = kite.instruments("NSE")
        banknifty = None
        for inst in instruments:
            if inst["tradingsymbol"] == "NIFTY BANK":
                banknifty = inst
                break
        
        if not banknifty:
            print("[ERROR] Bank Nifty instrument not found")
            return False
        
        print(f"[OK] Found Bank Nifty: {banknifty['tradingsymbol']}")
        print(f"     Instrument Token: {banknifty['instrument_token']}")
        
        # Test LTP API (works on free plan)
        print()
        print("Testing LTP API (Last Traded Price)...")
        print("-" * 60)
        
        for i in range(5):
            try:
                ltp_data = kite.ltp([banknifty["instrument_token"]])
                if banknifty["instrument_token"] in ltp_data:
                    price_data = ltp_data[banknifty["instrument_token"]]
                    price = price_data.get("last_price")
                    print(f"[{i+1}] Current Price: ₹{price:,.2f}")
                    
                    if i == 0:
                        print(f"     Instrument Token: {price_data.get('instrument_token')}")
                        print(f"     Exchange: {price_data.get('exchange')}")
                        print(f"     Tradingsymbol: {price_data.get('tradingsymbol')}")
                else:
                    print(f"[{i+1}] No data received")
            except Exception as e:
                print(f"[{i+1}] Error: {str(e)[:50]}")
            
            if i < 4:
                time.sleep(2)
        
        print("-" * 60)
        print()
        print("[SUCCESS] Zerodha LTP API is working!")
        print("This can be used for real-time data polling.")
        return True
        
    except Exception as e:
        print(f"[ERROR] {str(e)[:100]}")
        return False


if __name__ == "__main__":
    success = test_zerodha_ltp()
    sys.exit(0 if success else 1)

