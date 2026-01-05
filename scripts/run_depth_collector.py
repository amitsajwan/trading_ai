import json
from pathlib import Path
import logging

from kiteconnect import KiteConnect
from data.market_memory import MarketMemory
from data.depth_collector import DepthCollector


def main():
    logging.basicConfig(level=logging.INFO)
    cred_path = Path("credentials.json")
    if not cred_path.exists():
        raise SystemExit("credentials.json missing; run auto_login.py first")
    creds = json.loads(cred_path.read_text())
    api_key = creds.get("api_key") or creds.get("apiKey")
    access_token = creds.get("access_token") or creds.get("accessToken")
    if not api_key or not access_token:
        raise SystemExit("Missing api_key/access_token in credentials.json")

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    mm = MarketMemory()
    collector = DepthCollector(kite, mm)
    collector.collect(interval_seconds=3)


if __name__ == "__main__":
    main()
