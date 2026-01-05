"""Shim to preserve top-level `generate_session` CLI while implementation lives in the data_niftybank module."""

from data_niftybank.tools.generate_session import main

if __name__ == "__main__":
    main()

def get_env_or_prompt(name):
    val = os.environ.get(name)
    if val:
        return val
    return input(f"Enter {name}: ").strip()


def serialize_data(data):
    """Convert datetime objects in the data dictionary to strings."""
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    return data


def main():
    api_key = get_env_or_prompt("KITE_API_KEY")
    api_secret = get_env_or_prompt("KITE_API_SECRET")
    request_token = input("Paste the request_token from redirect URL: ").strip()

    kite = KiteConnect(api_key=api_key)
    try:
        data = kite.generate_session(request_token, api_secret=api_secret)
    except Exception as e:
        print("Failed to generate session:", e)
        return

    kite.set_access_token(data["access_token"])

    # Serialize datetime objects to strings
    data = serialize_data(data)

    cred = {
        "api_key": api_key,
        "api_secret": api_secret,
        "access_token": data.get("access_token"),
        "user_id": data.get("user_id"),
        "data": data,
    }

    out = Path("credentials.json")
    out.write_text(json.dumps(cred, indent=2))
    print("Saved credentials to", out.resolve())
    print("Logged in as:", data.get("user_id"))


if __name__ == "__main__":
    main()
