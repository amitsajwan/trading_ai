"""Test Kite Connect API access using credentials.json.

This script verifies that the access token and API key are valid by fetching the user's profile.
"""
import json
from pathlib import Path
from kiteconnect import KiteConnect

def load_credentials():
    """Load credentials from credentials.json."""
    cred_path = Path("credentials.json")
    if not cred_path.exists():
        print("Error: credentials.json not found. Run auto_login.py first.")
        return None

    try:
        return json.loads(cred_path.read_text())
    except Exception as e:
        print("Error reading credentials.json:", e)
        return None

def fetch_positions_and_balance(kite):
    """Fetch and display open positions and account balance."""
    try:
        # Fetch positions
        positions = kite.positions()
        print("\nOpen Positions:")
        print(json.dumps(positions, indent=2))

        # Fetch account balance (margins)
        margins = kite.margins(segment="equity")
        print("\nAccount Balance (Margins):")
        print(json.dumps(margins, indent=2))
    except Exception as e:
        print("Failed to fetch positions or balance:", e)

def place_order(kite):
    """Place a sample order."""
    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NSE,
            tradingsymbol="INFY",
            transaction_type=kite.TRANSACTION_TYPE_BUY,
            quantity=1,
            product=kite.PRODUCT_CNC,
            order_type=kite.ORDER_TYPE_MARKET
        )
        print("\nOrder placed successfully! Order ID:", order_id)
    except Exception as e:
        print("Failed to place order:", e)

def main():
    # Load credentials
    creds = load_credentials()
    if not creds:
        return

    # Initialize KiteConnect
    kite = KiteConnect(api_key=creds["api_key"])
    kite.set_access_token(creds["access_token"])

    # Test API access by fetching user profile
    try:
        profile = kite.profile()
        print("API access successful! User profile:")
        print(json.dumps(profile, indent=2))
    except Exception as e:
        print("Failed to access API:", e)
        return

    # Fetch positions and balance
    fetch_positions_and_balance(kite)

    # Place a sample order
    place_order(kite)

if __name__ == "__main__":
    main()