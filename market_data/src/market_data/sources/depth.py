"""Market depth data source - instrument agnostic.

Collects top 5 bid/ask levels from Kite quote() API and stores in Redis.
Works for any instrument via environment variables.
"""
import json
import os
import redis
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from market_data.providers.base import ProviderBase

try:
    from kiteconnect import KiteConnect
except ImportError:
    KiteConnect = None

try:
    from market_data.tools.kite_auth import CredentialsValidator
except ImportError:
    CredentialsValidator = None

try:
    from redis_key_manager import get_redis_key
except Exception:
    def get_redis_key(key: str, *args, **kwargs):
        return key


def get_symbol_config():
    """Get instrument configuration from environment variables."""
    trading_symbol = os.getenv("INSTRUMENT_TRADING_SYMBOL")
    symbol = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY26JANFUT")
    exchange = os.getenv("INSTRUMENT_EXCHANGE", "NSE")

    if trading_symbol and ("FUT" in trading_symbol.upper() or "CE" in trading_symbol.upper() or "PE" in trading_symbol.upper()):
        exchange = "NFO"
    elif "FUT" in symbol.upper() or "CE" in symbol.upper() or "PE" in symbol.upper():
        exchange = "NFO"

    if trading_symbol:
        return exchange, trading_symbol
    return exchange, symbol


def sanitize_key(symbol: str) -> str:
    """Convert symbol to Redis-safe key format."""
    return symbol.upper().replace(" ", "").replace("-", "_").replace(":", "_")


def get_banknifty_futures_symbol(kite, exchange: str = "NFO") -> Optional[str]:
    """Get the current/next expiry BANKNIFTY futures contract symbol."""
    try:
        instruments = kite.instruments(exchange)
        today = datetime.now()

        banknifty_futures = [
            inst for inst in instruments
            if inst.get("name") == "BANKNIFTY"
            and inst.get("instrument_type") == "FUT"
            and inst.get("expiry")
        ]

        if not banknifty_futures:
            return None

        def get_expiry_date(inst):
            expiry_str = inst.get("expiry", "")
            try:
                return datetime.strptime(expiry_str, "%Y-%m-%d")
            except Exception:
                return datetime.max

        banknifty_futures.sort(key=get_expiry_date)

        for fut in banknifty_futures:
            expiry_date = get_expiry_date(fut)
            if expiry_date >= today:
                trading_symbol = fut.get("tradingsymbol")
                if trading_symbol:
                    return trading_symbol

        if banknifty_futures:
            return banknifty_futures[0].get("tradingsymbol")

        return None
    except Exception as e:
        print(f"[depth] Error getting BANKNIFTY futures: {e}", file=sys.stderr)
        return None


class DepthCollector:
    """Collects and stores market depth data for any instrument."""

    def __init__(self, kite: Optional[Any] = None, redis_client: Optional[redis.Redis] = None):
        self.kite = kite
        self.exchange, self.symbol = get_symbol_config()
        self.full_symbol = f"{self.exchange}:{self.symbol}"
        self.key = sanitize_key(self.symbol)

        self._futures_symbol = None
        self._futures_symbol_cache_time = None

        if redis_client is None:
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            self.r = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        else:
            self.r = redis_client

    def collect_once(self) -> None:
        try:
            if not self.kite:
                raise ValueError("Kite client required for live depth data")

            symbol_upper = self.symbol.upper()
            is_index = symbol_upper in ["BANKNIFTY", "NIFTY BANK", "NIFTYBANK", "NIFTY", "NIFTY 50"]

            if is_index and self.exchange == "NSE":
                current_time = time.time()
                if (
                    self._futures_symbol is None
                    or self._futures_symbol_cache_time is None
                    or (current_time - self._futures_symbol_cache_time) > 3600
                ):
                    kite_instance = self.kite.kite if hasattr(self.kite, "kite") else self.kite

                    futures_symbol = get_banknifty_futures_symbol(kite_instance, "NFO")
                    if futures_symbol:
                        self._futures_symbol = futures_symbol
                        self._futures_symbol_cache_time = current_time
                        print(f"[depth] Using BANKNIFTY futures {futures_symbol} for depth data (index doesn't have depth)")
                    else:
                        print("[depth] Warning: Could not find BANKNIFTY futures contract, trying index anyway")
                        depth_symbol = f"{self.exchange}:NIFTY BANK"

                if self._futures_symbol:
                    depth_symbol = f"NFO:{self._futures_symbol}"
                else:
                    depth_symbol = f"{self.exchange}:NIFTY BANK"
            else:
                normalized_symbol = self.symbol
                if normalized_symbol.upper() == "BANKNIFTY":
                    normalized_symbol = "NIFTY BANK"
                elif normalized_symbol.upper() == "NIFTYBANK":
                    normalized_symbol = "NIFTY BANK"
                elif normalized_symbol.upper() == "NIFTY":
                    normalized_symbol = "NIFTY 50"

                depth_symbol = f"{self.exchange}:{normalized_symbol}"

            q = None
            try:
                kite_instance = self.kite.kite if hasattr(self.kite, "kite") else self.kite
                quotes = kite_instance.quote([depth_symbol])
                if quotes and len(quotes) > 0:
                    q = list(quotes.values())[0]
                else:
                    raise ValueError(f"No quote data returned for {depth_symbol}")
            except (IndexError, KeyError, ValueError):
                alt_symbols = [
                    depth_symbol,
                    "NSE:NIFTY BANK",
                    f"NSE:{self.symbol}",
                    self.symbol,
                ]

                kite_instance = self.kite.kite if hasattr(self.kite, "kite") else self.kite
                for alt_symbol in alt_symbols:
                    try:
                        quotes = kite_instance.quote([alt_symbol])
                        if quotes and len(quotes) > 0:
                            q = list(quotes.values())[0]
                            break
                    except Exception:
                        continue

            if q is None:
                print(f"[depth] Warning: Could not fetch depth for {self.full_symbol} (tried: NSE:NIFTY BANK, {self.exchange}:{self.symbol}, and alternatives)")
                return

            buy_depth = []
            sell_depth = []
            depth_data = None

            if isinstance(q, dict):
                depth_data = q.get("depth")
            elif hasattr(q, "depth"):
                depth_data = q.depth

            if depth_data:
                if isinstance(depth_data, dict):
                    buy_depth = depth_data.get("buy", [])
                    sell_depth = depth_data.get("sell", [])
                elif hasattr(depth_data, "buy") and hasattr(depth_data, "sell"):
                    buy_depth = list(depth_data.buy) if depth_data.buy else []
                    sell_depth = list(depth_data.sell) if depth_data.sell else []
                elif hasattr(depth_data, "to_dict"):
                    depth_dict = depth_data.to_dict()
                    buy_depth = depth_dict.get("buy", [])
                    sell_depth = depth_dict.get("sell", [])

            if not buy_depth and not sell_depth:
                current_time = time.time()
                if not hasattr(self, "_last_depth_warning_time") or (current_time - self._last_depth_warning_time) > 60:
                    self._last_depth_warning_time = current_time
                    print(f"[depth] Info: Depth data not available for {self.full_symbol} (normal for indices or outside market hours)")
                return

            timestamp = datetime.now().isoformat()
            self.r.set(get_redis_key(f"depth:{self.key}:buy"), json.dumps(buy_depth))
            self.r.set(get_redis_key(f"depth:{self.key}:sell"), json.dumps(sell_depth))
            self.r.set(get_redis_key(f"depth:{self.key}:timestamp"), timestamp)

            total_bid_qty = sum(level.get("quantity", 0) for level in buy_depth)
            total_ask_qty = sum(level.get("quantity", 0) for level in sell_depth)

            self.r.set(get_redis_key(f"depth:{self.key}:total_bid_qty"), total_bid_qty)
            self.r.set(get_redis_key(f"depth:{self.key}:total_ask_qty"), total_ask_qty)

            print(f"[depth] {self.full_symbol} - {len(buy_depth)} bids ({total_bid_qty}), {len(sell_depth)} asks ({total_ask_qty})")

        except Exception as e:
            print(f"[depth] Error collecting depth for {self.full_symbol}: {e}", file=sys.stderr)

    def run_forever(self, interval: float = 5.0) -> None:
        print(f"[depth] Starting depth collector for {self.full_symbol} (interval: {interval}s)")

        while True:
            try:
                self.collect_once()
            except KeyboardInterrupt:
                print("\n[depth] Stopped by user")
                break
            except Exception as e:
                print(f"[depth] Unexpected error: {e}", file=sys.stderr)

            time.sleep(interval)


def build_kite_client() -> Optional["ProviderBase"]:
    """Return a provider (Zerodha or Mock) based on configuration/environment."""
    try:
        from market_data.providers.factory import get_provider
        provider = get_provider()
        return provider
    except Exception as e:
        print(f"Error resolving provider: {e}")
        return None


def main():
    """Standalone entrypoint for Docker/systemd."""
    print("=" * 60)
    print("Market Depth Collector - Instrument Agnostic")
    print("=" * 60)

    kite = build_kite_client()

    if not kite:
        print("ERROR: No Kite credentials available")
        print("Set KITE_API_KEY and KITE_ACCESS_TOKEN environment variables")
        print("Or add to credentials.json in current directory")
        sys.exit(1)

    collector = DepthCollector(kite=kite)

    interval = float(os.getenv("DEPTH_COLLECTOR_INTERVAL", "5.0"))

    collector.run_forever(interval=interval)


class DepthSource(DepthCollector):
    """Alias for DepthCollector."""


def start_depth_source(kite=None, redis_client=None) -> DepthSource:
    collector = DepthSource(kite=kite, redis_client=redis_client)
    collector.collect_once()
    return collector


if __name__ == "__main__":
    main()
