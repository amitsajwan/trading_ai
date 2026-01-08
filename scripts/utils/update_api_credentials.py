"""Update Zerodha API credentials in .env file."""

import os
from pathlib import Path
from dotenv import load_dotenv, set_key

def update_credentials():
    """Update KITE_API_KEY and KITE_API_SECRET in .env file."""
    print("=" * 60)
    print("Updating Zerodha API Credentials")
    print("=" * 60)
    
    # Get credentials from environment variables or prompt user
    new_api_key = os.getenv("KITE_API_KEY")
    if not new_api_key:
        new_api_key = input("Enter Zerodha API Key: ").strip()
        if not new_api_key:
            print("API key is required. Exiting.")
            return
    
    new_api_secret = os.getenv("KITE_API_SECRET")
    if not new_api_secret:
        new_api_secret = input("Enter Zerodha API Secret: ").strip()
        if not new_api_secret:
            print("API secret is required. Exiting.")
            return
    
    env_path = Path(".env")
    
    # Load existing .env if it exists
    if env_path.exists():
        load_dotenv(env_path)
        print("[OK] Found existing .env file")
    else:
        print("[INFO] Creating new .env file")
        env_path.touch()
    
    # Update credentials
    set_key(env_path, "KITE_API_KEY", new_api_key)
    set_key(env_path, "KITE_API_SECRET", new_api_secret)
    
    print()
    print(f"[OK] Updated KITE_API_KEY: {new_api_key}")
    print(f"[OK] Updated KITE_API_SECRET: {new_api_secret[:10]}...")
    print()
    print("=" * 60)
    print("Credentials Updated Successfully!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Re-authenticate: python auto_login.py")
    print("  2. Test WebSocket: python scripts/test_websocket_direct.py")
    print("  3. Start data feed: python -m data.run_ingestion")
    print()

if __name__ == "__main__":
    update_credentials()


