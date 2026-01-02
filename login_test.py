"""Simple Kite Connect login URL opener.

Usage:
 - Set environment variable KITE_API_KEY or enter when prompted.
 - Run: python login_test.py
 - Browser will open the Zerodha login URL; complete login to get request_token on redirect.
"""
import os
import webbrowser
from kiteconnect import KiteConnect


def get_api_key():
    key = os.environ.get("KITE_API_KEY")
    if key:
        return key
    return input("Enter your Kite API_KEY: ").strip()


def main():
    api_key = get_api_key()
    kite = KiteConnect(api_key=api_key)
    login_url = kite.login_url()
    print("Login URL:\n", login_url)
    print("Opening browser... log in and copy the request_token from the redirect URL.")
    webbrowser.open(login_url)


if __name__ == "__main__":
    main()
