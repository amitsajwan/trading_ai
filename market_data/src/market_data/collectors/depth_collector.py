"""Market depth data collector - instrument agnostic.

Collects top 5 bid/ask levels from Kite quote() API and stores in Redis.
Works for any instrument via environment variables.

Environment Variables:
    INSTRUMENT_SYMBOL: e.g., "NIFTY BANK", "RELIANCE", "BTCUSDT"
    INSTRUMENT_EXCHANGE: e.g., "NSE", "BSE", "BINANCE"
    REDIS_HOST: Redis server host (default: localhost)
    REDIS_PORT: Redis server port (default: 6379)
    KITE_API_KEY: Zerodha API key
    KITE_ACCESS_TOKEN: Zerodha access token
"""
import json
import os
import redis
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from kiteconnect import KiteConnect
except ImportError:
    KiteConnect = None

try:
    from market_data.tools.kite_auth import CredentialsValidator
except ImportError:
    CredentialsValidator = None


def get_symbol_config():
    """Get instrument configuration from environment variables."""
    trading_symbol = os.getenv("INSTRUMENT_TRADING_SYMBOL")
    symbol = os.getenv("INSTRUMENT_SYMBOL", "NIFTY BANK")
    exchange = os.getenv("INSTRUMENT_EXCHANGE", "NSE")
    
    if trading_symbol:
        # Determine correct exchange based on symbol type
        if "FUT" in trading_symbol.upper() or "CE" in trading_symbol.upper() or "PE" in trading_symbol.upper():
            exchange = "NFO"  # Futures & Options
        return exchange, trading_symbol
    return exchange, symbol


def sanitize_key(symbol: str) -> str:
    """Convert symbol to Redis-safe key format."""
    return symbol.upper().replace(" ", "").replace("-", "_").replace(":", "_")


class DepthCollector:
    """Collects and stores market depth data for any instrument."""
    
    def __init__(self, kite: Optional[Any] = None, redis_client: Optional[redis.Redis] = None):
        """Initialize depth collector.
        
        Args:
            kite: KiteConnect instance (optional, will build from env if None)
            redis_client: Redis client (optional, will build from env if None)
        """
        self.kite = kite
        self.exchange, self.symbol = get_symbol_config()
        self.full_symbol = f"{self.exchange}:{self.symbol}"
        self.key = sanitize_key(self.symbol)
        
        # Build Redis client if not provided
        if redis_client is None:
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            self.r = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        else:
            self.r = redis_client
    
    def collect_once(self) -> None:
        """Collect and store depth data once."""
        try:
            if not self.kite:
                raise ValueError("Kite client required for live depth data")
            
            # Normalize symbol: BANKNIFTY -> NIFTY BANK (Zerodha format)
            normalized_symbol = self.symbol
            if normalized_symbol.upper() == "BANKNIFTY":
                normalized_symbol = "NIFTY BANK"
            elif normalized_symbol.upper() == "NIFTYBANK":
                normalized_symbol = "NIFTY BANK"
            elif normalized_symbol.upper() == "NIFTY":
                normalized_symbol = "NIFTY 50"
            
            # Fetch quote with depth
            try:
                # Try primary format: NSE:NIFTY BANK
                primary_symbol = f"{self.exchange}:{normalized_symbol}"
                quotes = self.kite.quote([primary_symbol])
                if quotes and len(quotes) > 0:
                    q = list(quotes.values())[0]
                else:
                    raise ValueError(f"No quote data returned for {primary_symbol}")
            except (IndexError, KeyError, ValueError) as e:
                # Try alternative symbol formats
                alt_symbols = [
                    f"NSE:{normalized_symbol}",
                    f"NSE:{self.symbol}",  # Original symbol
                    f"NFO:{normalized_symbol}",
                    normalized_symbol,  # Just symbol without exchange
                    self.symbol,  # Original symbol without exchange
                ]
                
                q = None
                for alt_symbol in alt_symbols:
                    try:
                        quotes = self.kite.quote([alt_symbol])
                        if quotes and len(quotes) > 0:
                            q = list(quotes.values())[0]
                            break
                    except:
                        continue
                
                if q is None:
                    # All attempts failed
                    print(f"[depth] Warning: Could not fetch depth for {self.full_symbol} (tried: NSE:NIFTY BANK, {self.exchange}:{self.symbol}, and alternatives)")
                    buy_depth = []
                    sell_depth = []
                    return
                # Normalize if it's a Quote dataclass
                if hasattr(q, 'to_dict'):
                    q = q.to_dict()
                depth = q.get('depth', {})
                
                # Extract buy/sell depth
                buy_depth = depth.get('buy', [])
                sell_depth = depth.get('sell', [])
            
            # Store in Redis
            timestamp = datetime.now().isoformat()
            self.r.set(f"depth:{self.key}:buy", json.dumps(buy_depth))
            self.r.set(f"depth:{self.key}:sell", json.dumps(sell_depth))
            self.r.set(f"depth:{self.key}:timestamp", timestamp)
            
            # Calculate depth stats
            total_bid_qty = sum(level.get('quantity', 0) for level in buy_depth)
            total_ask_qty = sum(level.get('quantity', 0) for level in sell_depth)
            
            self.r.set(f"depth:{self.key}:total_bid_qty", total_bid_qty)
            self.r.set(f"depth:{self.key}:total_ask_qty", total_ask_qty)
            
            print(f"[depth] {self.full_symbol} - {len(buy_depth)} bids ({total_bid_qty}), "
                  f"{len(sell_depth)} asks ({total_ask_qty})")
        
        except Exception as e:
            print(f"[depth] Error collecting depth for {self.full_symbol}: {e}", file=sys.stderr)
    
    def run_forever(self, interval: float = 5.0) -> None:
        """Run collection loop forever.
        
        Args:
            interval: Seconds between collections (default: 5.0)
        """
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
        from providers.factory import get_provider
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
    
    # Get interval from env (default: 5 seconds)
    interval = float(os.getenv("DEPTH_COLLECTOR_INTERVAL", "5.0"))
    
    collector.run_forever(interval=interval)


if __name__ == "__main__":
    main()

