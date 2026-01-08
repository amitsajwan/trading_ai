import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict

try:
    import redis  # type: ignore
except ImportError:
    redis = None

try:
    from kiteconnect import KiteConnect  # type: ignore
except ImportError:
    KiteConnect = None


def load_credentials():
    api_key = os.getenv("KITE_API_KEY")
    access_token = os.getenv("KITE_ACCESS_TOKEN")

    if api_key and access_token:
        return api_key, access_token

    cred_path = os.path.join(os.getcwd(), "credentials.json")
    if os.path.exists(cred_path):
        try:
            with open(cred_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            z = data.get("zerodha") or {}
            api_key = api_key or z.get("api_key")
            access_token = access_token or z.get("access_token") or z.get("public_token")
        except Exception:
            pass
    return api_key, access_token


def build_kite_client():
    try:
        from market_data.providers.factory import get_provider
        provider = get_provider()
        return provider
    except Exception as e:
        print(f"Error resolving provider: {e}")
        return None


def get_symbol_config():
    trading_symbol = os.getenv("INSTRUMENT_TRADING_SYMBOL")
    symbol = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY")
    exchange = os.getenv("INSTRUMENT_EXCHANGE", "NSE")
    if trading_symbol:
        return exchange, trading_symbol
    return exchange, symbol


def sanitize_key(symbol: str) -> str:
    return symbol.upper().replace(" ", "")


class LTPDataCollector:
    """Lightweight LTP collector for Zerodha or synthetic fallback."""

    def __init__(self, kite: Any, market_memory: Any) -> None:
        self.kite = kite
        self.market_memory = market_memory
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.exchange, self.symbol = get_symbol_config()
        self.key = sanitize_key(self.symbol)
        self.price = 44000.0  # seed
        self.drift = 0.0
        self.r = None

        if redis:
            self.r = redis.Redis(host=self.redis_host, port=self.redis_port, db=0, decode_responses=True)

    def fetch_quote(self) -> Dict[str, Any]:
        if self.kite:
            quotes = self.kite.quote([f"{self.exchange}:{self.symbol}"])
            return list(quotes.values())[0]
        # synthetic fallback
        self.drift += random.uniform(-5, 5)
        self.price = max(1.0, self.price + self.drift)
        return {"last_price": self.price, "depth": {}}

    def collect_once(self) -> None:
        ts = datetime.now(timezone.utc).replace(tzinfo=None)
        quote = self.fetch_quote()
        price = float(quote.get("last_price") or quote.get("last") or self.price)
        depth = quote.get("depth") or {}
        self.price = price

        if self.r:
            self.r.set(f"price:{self.key}:last_price", price)
            self.r.set(f"price:{self.key}:latest_ts", ts.isoformat())
            self.r.set(f"price:{self.key}:quote", json.dumps({"last_price": price, "depth": depth}))

        # If market_memory is provided, push a simple tick
        if self.market_memory:
            try:
                tick = {
                    "instrument_token": self.key,
                    "last_price": price,
                    "timestamp": ts,
                }
                self.market_memory.append_tick(tick)  # type: ignore[attr-defined]
            except Exception:
                pass

        print(f"[ltp] {self.symbol} price={price:.2f} ts={ts.isoformat()}")

    def run_forever(self, interval_seconds: float = 2.0) -> None:
        while True:
            try:
                self.collect_once()
            except Exception as e:
                print(f"[ltp] error: {e}", file=sys.stderr)
            time.sleep(interval_seconds)


def main():
    # Standalone runner mainly for container entrypoint
    kite_client = build_kite_client()
    collector = LTPDataCollector(kite_client, market_memory=None)
    collector.run_forever(interval_seconds=2.0)


if __name__ == "__main__":
    main()

