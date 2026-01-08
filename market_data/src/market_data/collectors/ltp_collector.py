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

try:
    from market_data.tools.kite_auth import CredentialsValidator
except ImportError:
    CredentialsValidator = None

# Import config
try:
    from config import get_config
    config = get_config()
except ImportError:
    config = None


def load_credentials():
    """Load credentials from json file with automatic refresh if needed."""
    cred_path = os.path.join(os.getcwd(), "credentials.json")
    if not os.path.exists(cred_path):
        print("No credentials.json found. Please run kite_auth.py first.")
        return None, None

    try:
        with open(cred_path, "r", encoding="utf-8") as f:
            creds = json.load(f)
        
        api_key = creds.get("api_key")
        access_token = creds.get("access_token")
        
        if not api_key or not access_token:
            print("Invalid credentials in json file")
            return None, None
            
        # Check if token is still valid
        if CredentialsValidator and not CredentialsValidator.is_token_valid(creds):
            print("Access token expired, refreshing...")
            # Import and run kite_auth main to refresh
            try:
                from market_data.tools.kite_auth import main as auth_main
                # Run auth_main which will handle the refresh
                result = auth_main()
                if result == 0:
                    # Reload credentials after refresh
                    with open(cred_path, "r", encoding="utf-8") as f:
                        creds = json.load(f)
                    api_key = creds.get("api_key")
                    access_token = creds.get("access_token")
                    print("Credentials refreshed successfully")
                else:
                    print("Failed to refresh credentials")
                    return None, None
            except Exception as e:
                print(f"Error refreshing credentials: {e}")
                return None, None
        
        return api_key, access_token
        
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None, None


def build_kite_client():
    """Return a provider object implementing quote/profile/historical_data.
    Uses the provider factory which can return a Mock or Zerodha provider based on env.
    """
    try:
        from providers.factory import get_provider
        provider = get_provider()
        return provider
    except Exception as e:
        print(f"Error resolving provider: {e}")
        return None


def get_symbol_config():
    if config:
        trading_symbol = config.instrument_trading_symbol
        symbol = config.instrument_symbol
        exchange = config.instrument_exchange
        if trading_symbol:
            # Determine correct exchange based on symbol type
            if "FUT" in trading_symbol.upper() or "CE" in trading_symbol.upper() or "PE" in trading_symbol.upper():
                exchange = "NFO"  # Futures & Options
            return exchange, trading_symbol
        return exchange, symbol
    else:
        # Fallback to environment variables
        trading_symbol = os.getenv("INSTRUMENT_TRADING_SYMBOL")
        symbol = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY")
        exchange = os.getenv("INSTRUMENT_EXCHANGE", "NSE")
        if trading_symbol:
            # Determine correct exchange based on symbol type
            if "FUT" in trading_symbol.upper() or "CE" in trading_symbol.upper() or "PE" in trading_symbol.upper():
                exchange = "NFO"  # Futures & Options
            return exchange, trading_symbol
        return exchange, symbol


def sanitize_key(symbol: str) -> str:
    return symbol.upper().replace(" ", "")


class LTPDataCollector:
    """Lightweight LTP collector for Zerodha or synthetic fallback."""

    def __init__(self, kite: Any, market_memory: Any) -> None:
        self.kite = kite
        self.market_memory = market_memory
        self.exchange, self.symbol = get_symbol_config()
        self.key = config.instrument_key if config else sanitize_key(self.symbol)
        self.price = 44000.0  # seed
        self.drift = 0.0
        self.r = None

        if redis:
            redis_config = config.get_redis_config() if config else {
                "host": os.getenv("REDIS_HOST", "localhost"),
                "port": int(os.getenv("REDIS_PORT", "6379")),
                "db": 0,
                "decode_responses": True
            }
            self.r = redis.Redis(**redis_config)

    def fetch_quote(self) -> Any:
        if self.kite:
            # Normalize symbol: BANKNIFTY -> NIFTY BANK (Zerodha format)
            normalized_symbol = self.symbol
            if normalized_symbol.upper() == "BANKNIFTY":
                normalized_symbol = "NIFTY BANK"
            elif normalized_symbol.upper() == "NIFTYBANK":
                normalized_symbol = "NIFTY BANK"
            elif normalized_symbol.upper() == "NIFTY":
                normalized_symbol = "NIFTY 50"
            
            try:
                # Try primary format: NSE:NIFTY BANK
                primary_symbol = f"{self.exchange}:{normalized_symbol}"
                quotes = self.kite.quote([primary_symbol])
                if quotes and len(quotes) > 0:
                    q = list(quotes.values())[0]
                    return q
            except (IndexError, KeyError, ValueError) as e:
                pass
            
            # Try alternative symbol formats
            alt_symbols = [
                f"NSE:{normalized_symbol}",
                f"NSE:{self.symbol}",  # Original symbol
                f"NFO:{normalized_symbol}",
                normalized_symbol,  # Just symbol without exchange
                self.symbol,  # Original symbol without exchange
            ]
            
            for alt_symbol in alt_symbols:
                try:
                    quotes = self.kite.quote([alt_symbol])
                    if quotes and len(quotes) > 0:
                        q = list(quotes.values())[0]
                        return q
                except:
                    continue
            
            # All attempts failed
            raise ValueError(f"Could not fetch quote for {self.exchange}:{self.symbol} (tried: NSE:NIFTY BANK, {self.exchange}:{self.symbol}, and alternatives)")
            return q
        # synthetic fallback
        self.drift += random.uniform(-5, 5)
        self.price = max(1.0, self.price + self.drift)
        return {"last_price": self.price, "depth": {}}

    def _quote_to_dict(self, quote: Any) -> Dict[str, Any]:
        """Normalize Quote dataclass or dict to a plain dict for downstream processing."""
        if hasattr(quote, "to_dict"):
            return quote.to_dict()
        if isinstance(quote, dict):
            return quote
        # Fallback: try to build dict from attributes
        try:
            return {"last_price": getattr(quote, "last_price"), "depth": getattr(quote, "depth"), "timestamp": getattr(quote, "timestamp")}
        except Exception:
            return {"last_price": self.price, "depth": {}}

    def collect_once(self) -> None:
        ts = datetime.now(timezone.utc).replace(tzinfo=None)
        quote = self.fetch_quote()
        qd = self._quote_to_dict(quote)
        price = float(qd.get("last_price") or qd.get("last") or self.price)
        depth = qd.get("depth") or {}
        volume = qd.get("volume", 0)
        self.price = price

        # Store tick using MarketStore interface (for live mode compatibility)
        if self.market_memory:
            try:
                from ..contracts import MarketTick
                # Use normalized instrument name that matches what store expects
                instrument_name = "BANKNIFTY" if "BANK" in self.symbol.upper() else self.symbol.upper()
                tick = MarketTick(
                    instrument=instrument_name,
                    timestamp=ts,
                    last_price=price,
                    volume=volume if volume > 0 else None,
                )
                self.market_memory.store_tick(tick)  # Use store_tick() method
            except Exception as e:
                print(f"[ltp] Error storing tick via store: {e}")

        # Also maintain backward compatibility with direct Redis writes
        if self.r:
            # Write to both formats for compatibility
            instrument_name = "BANKNIFTY" if "BANK" in self.symbol.upper() else self.symbol.upper()
            tick_data = {
                "instrument": instrument_name,
                "timestamp": ts.isoformat(),
                "last_price": price,
                "volume": volume if volume > 0 else None,
            }
            self.r.setex(f"tick:{instrument_name}:latest", 86400, json.dumps(tick_data))  # 24h TTL
            self.r.setex(f"price:{instrument_name}:latest", 86400, str(price))
            self.r.setex(f"price:{instrument_name}:latest_ts", 86400, ts.isoformat())

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

