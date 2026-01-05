"""Shim to preserve top-level `login_test` CLI while implementation lives in the data_niftybank module."""

from data_niftybank.tools.login_test import main

if __name__ == "__main__":
    main()

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
