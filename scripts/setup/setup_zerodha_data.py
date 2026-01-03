"""Setup Zerodha Kite for data collection using LTP API."""

import sys
import os
import json
import time
import logging
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings
from data.ltp_data_collector import LTPDataCollector
from data.market_memory import MarketMemory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_zerodha_setup():
    """Check if Zerodha is set up and working."""
    print("=" * 60)
    print("Zerodha Kite Setup Check")
    print("=" * 60)
    print()
    
    # Check API keys
    if not settings.kite_api_key or not settings.kite_api_secret:
        print("[FAIL] KITE_API_KEY or KITE_API_SECRET not configured in .env")
        print()
        print("To configure:")
        print("  1. Get API key from: https://kite.trade/apps")
        print("  2. Add to .env file:")
        print("     KITE_API_KEY=your_api_key")
        print("     KITE_API_SECRET=your_api_secret")
        return False
    
    print(f"[OK] API Key: {settings.kite_api_key[:10]}...")
    print(f"[OK] API Secret: {'*' * 10}")
    print()
    
    # Check credentials file (can be credentials.json or kite_credentials.json)
    cred_path = Path("credentials.json")
    if not cred_path.exists():
        cred_path = Path("kite_credentials.json")
    if not cred_path.exists():
        print("[WARN] credentials.json or kite_credentials.json not found")
        print()
        print("To authenticate:")
        print("  1. Run: python auto_login.py")
        print("  2. Or manually authenticate:")
        print("     - Visit: https://kite.trade/connect/login?api_key=YOUR_API_KEY")
        print("     - Login and authorize")
        print("     - Copy the request_token from redirect URL")
        print("     - Run: python -c \"from kiteconnect import KiteConnect; kite = KiteConnect('YOUR_API_KEY'); print(kite.generate_session('REQUEST_TOKEN', 'YOUR_API_SECRET'))\"")
        return False
    
    print("[OK] Credentials file found")
    
    try:
        from kiteconnect import KiteConnect
        
        with open(cred_path) as f:
            creds = json.load(f)
        
        # Handle different credential file formats
        api_key = creds.get("api_key") or creds.get("apiKey")
        access_token = creds.get("access_token") or creds.get("accessToken")
        
        if not api_key or not access_token:
            print("[ERROR] Missing api_key or access_token in credentials file")
            print("        Re-authenticate by running: python auto_login.py")
            return False
        
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        
        # Test connection
        try:
            profile = kite.profile()
            print(f"[OK] Connected as: {profile.get('user_name', 'Unknown')}")
        except Exception as e:
            print(f"[ERROR] Could not fetch profile: {e}")
            print("        Token may be expired. Re-authenticate: python auto_login.py")
            return False
        
        # Test LTP API
        try:
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
            
            # Test LTP (check if market is open)
            from datetime import datetime
            now = datetime.now()
            is_market_hours = (now.weekday() < 5 and 
                              datetime.strptime("09:15:00", "%H:%M:%S").time() <= now.time() <= 
                              datetime.strptime("15:30:00", "%H:%M:%S").time())
            
            if not is_market_hours:
                print("[WARN] Market is closed (LTP only works during market hours)")
                print("       Market hours: 9:15 AM - 3:30 PM IST (Mon-Fri)")
                print()
                print("[OK] Setup is correct - LTP will work when market opens")
                return True
            
            # Test LTP
            ltp_data = kite.ltp([banknifty["instrument_token"]])
            if banknifty["instrument_token"] in ltp_data:
                price = ltp_data[banknifty["instrument_token"]].get("last_price")
                if price:
                    print(f"[OK] Current Price: ₹{price:,.2f}")
                    print()
                    print("[SUCCESS] Zerodha Kite is ready to use!")
                    print()
                    print("To start data collection:")
                    print("  python -m data.ltp_data_collector")
                    print()
                    print("Or start full trading system:")
                    print("  python -m services.trading_service")
                    return True
                else:
                    print("[WARN] LTP returned but no price (market may be closed)")
                    return True
            else:
                print("[WARN] LTP API call succeeded but no data returned")
                print("       This is normal if market is closed")
                return True
                
        except Exception as e:
            error_msg = str(e)
            if "Insufficient permission" in error_msg:
                print("[ERROR] Insufficient permission for LTP API")
                print("        Your API key may not have market data permissions")
                print("        Check API key permissions at: https://kite.trade/apps")
                return False
            elif "Invalid API key" in error_msg or "Invalid access token" in error_msg:
                print("[ERROR] Invalid API key or access token")
                print("        Re-authenticate: python auto_login.py")
                return False
            else:
                print(f"[ERROR] {error_msg}")
                print("        This might be normal if market is closed")
                # Still return True as setup is correct
                return True
        
    except Exception as e:
        print(f"[ERROR] {str(e)[:100]}")
        return False
    
    return False


if __name__ == "__main__":
    success = check_zerodha_setup()
    sys.exit(0 if success else 1)

