#!/usr/bin/env python3
"""Check current BankNifty futures instrument tokens."""

import json
import os

def main():
    # Load credentials
    cred_path = "credentials.json"
    try:
        with open(cred_path, 'r') as f:
            creds = json.load(f)
        api_key = creds.get('api_key')
        access_token = creds.get('access_token')
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return

    if not api_key or not access_token:
        print("No credentials available")
        return

    try:
        from kiteconnect import KiteConnect
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)

        instruments = kite.instruments('NFO')
        banknifty_futs = [i for i in instruments if i['name'] == 'BANKNIFTY' and i['instrument_type'] == 'FUT']
        print("Current BankNifty Futures:")
        for fut in banknifty_futs[:5]:
            print(f"{fut['instrument_token']}: {fut['tradingsymbol']} - {fut['expiry']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()