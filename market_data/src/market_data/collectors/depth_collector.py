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


def get_banknifty_futures_symbol(kite, exchange: str = "NFO") -> Optional[str]:
    """Get the current/next expiry BANKNIFTY futures contract symbol.
    
    Args:
        kite: KiteConnect instance
        exchange: Exchange code (default: "NFO" for futures)
    
    Returns:
        Trading symbol like "BANKNIFTY26JAN2026FUT" or None if not found
    """
    try:
        # Get all NFO instruments
        instruments = kite.instruments(exchange)
        
        # Filter for BANKNIFTY futures
        from datetime import datetime
        today = datetime.now()
        
        banknifty_futures = [
            inst for inst in instruments
            if inst.get("name") == "BANKNIFTY"
            and inst.get("instrument_type") == "FUT"
            and inst.get("expiry")
        ]
        
        if not banknifty_futures:
            return None
        
        # Sort by expiry date and get the nearest (current/next expiry)
        def get_expiry_date(inst):
            expiry_str = inst.get("expiry", "")
            try:
                return datetime.strptime(expiry_str, "%Y-%m-%d")
            except:
                return datetime.max
        
        banknifty_futures.sort(key=get_expiry_date)
        
        # Get the nearest expiry that's not expired
        for fut in banknifty_futures:
            expiry_date = get_expiry_date(fut)
            if expiry_date >= today:
                trading_symbol = fut.get("tradingsymbol")
                if trading_symbol:
                    return trading_symbol
        
        # If all are expired, return the most recent one anyway
        if banknifty_futures:
            return banknifty_futures[0].get("tradingsymbol")
        
        return None
    except Exception as e:
        print(f"[depth] Error getting BANKNIFTY futures: {e}", file=sys.stderr)
        return None


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
        
        # Cache for futures symbol (for indices)
        self._futures_symbol = None
        self._futures_symbol_cache_time = None
        
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
            
            # Check if we're trying to get depth for an index (which doesn't have depth)
            # If so, automatically switch to the futures contract
            symbol_upper = self.symbol.upper()
            is_index = symbol_upper in ["BANKNIFTY", "NIFTY BANK", "NIFTYBANK", "NIFTY", "NIFTY 50"]
            
            # If it's an index, get the futures contract instead
            if is_index and self.exchange == "NSE":
                # Cache futures symbol lookup (refresh every hour)
                current_time = time.time()
                if (self._futures_symbol is None or 
                    self._futures_symbol_cache_time is None or 
                    (current_time - self._futures_symbol_cache_time) > 3600):
                    
                    # Get the actual KiteConnect instance (might be wrapped in provider)
                    kite_instance = self.kite
                    if hasattr(self.kite, 'kite'):
                        kite_instance = self.kite.kite
                    
                    futures_symbol = get_banknifty_futures_symbol(kite_instance, "NFO")
                    if futures_symbol:
                        self._futures_symbol = futures_symbol
                        self._futures_symbol_cache_time = current_time
                        print(f"[depth] Using BANKNIFTY futures {futures_symbol} for depth data (index doesn't have depth)")
                    else:
                        print(f"[depth] Warning: Could not find BANKNIFTY futures contract, trying index anyway")
                        depth_symbol = f"{self.exchange}:NIFTY BANK"
                
                if self._futures_symbol:
                    depth_symbol = f"NFO:{self._futures_symbol}"
                else:
                    depth_symbol = f"{self.exchange}:NIFTY BANK"
            else:
                # Use the configured symbol
                normalized_symbol = self.symbol
                if normalized_symbol.upper() == "BANKNIFTY":
                    normalized_symbol = "NIFTY BANK"
                elif normalized_symbol.upper() == "NIFTYBANK":
                    normalized_symbol = "NIFTY BANK"
                elif normalized_symbol.upper() == "NIFTY":
                    normalized_symbol = "NIFTY 50"
                
                depth_symbol = f"{self.exchange}:{normalized_symbol}"
            
            # Fetch quote with depth
            q = None
            try:
                # Get the actual KiteConnect instance (might be wrapped in provider)
                kite_instance = self.kite
                if hasattr(self.kite, 'kite'):
                    kite_instance = self.kite.kite
                
                quotes = kite_instance.quote([depth_symbol])
                if quotes and len(quotes) > 0:
                    q = list(quotes.values())[0]
                else:
                    raise ValueError(f"No quote data returned for {depth_symbol}")
            except (IndexError, KeyError, ValueError) as e:
                # Try alternative symbol formats
                alt_symbols = [
                    depth_symbol,
                    f"NSE:NIFTY BANK",
                    f"NSE:{self.symbol}",
                    self.symbol,
                ]
                
                kite_instance = self.kite
                if hasattr(self.kite, 'kite'):
                    kite_instance = self.kite.kite
                
                for alt_symbol in alt_symbols:
                    try:
                        quotes = kite_instance.quote([alt_symbol])
                        if quotes and len(quotes) > 0:
                            q = list(quotes.values())[0]
                            break
                    except:
                        continue
            
            # Check if we got a quote
            if q is None:
                # All attempts failed
                print(f"[depth] Warning: Could not fetch depth for {self.full_symbol} (tried: NSE:NIFTY BANK, {self.exchange}:{self.symbol}, and alternatives)")
                buy_depth = []
                sell_depth = []
                return
            
            # KiteConnect quote() returns a dict-like object or dict
            # The depth data can be accessed in multiple ways depending on the response format
            buy_depth = []
            sell_depth = []
            
            # Try to extract depth data - handle both dict and object formats
            depth_data = None
            
            # Method 1: If it's a dict, get depth key
            if isinstance(q, dict):
                depth_data = q.get('depth')
            # Method 2: If it has a depth attribute
            elif hasattr(q, 'depth'):
                depth_data = q.depth
            
            # Now extract buy/sell from depth_data
            if depth_data:
                # If depth_data is a dict
                if isinstance(depth_data, dict):
                    buy_depth = depth_data.get('buy', [])
                    sell_depth = depth_data.get('sell', [])
                # If depth_data is an object with buy/sell attributes
                elif hasattr(depth_data, 'buy') and hasattr(depth_data, 'sell'):
                    buy_depth = list(depth_data.buy) if depth_data.buy else []
                    sell_depth = list(depth_data.sell) if depth_data.sell else []
                # If depth_data has to_dict method
                elif hasattr(depth_data, 'to_dict'):
                    depth_dict = depth_data.to_dict()
                    buy_depth = depth_dict.get('buy', [])
                    sell_depth = depth_dict.get('sell', [])
            
            # If still no depth data, check if market is open and depth is available
            if not buy_depth and not sell_depth:
                # KiteConnect quote() API may not return depth data for:
                # - Indices (like BANKNIFTY, NIFTY) - depth is only for stocks/options
                # - Outside market hours
                # - Some instruments don't have depth available
                # This is normal behavior, so we'll log less verbosely
                # Only log once per minute to avoid spam
                current_time = time.time()
                if not hasattr(self, '_last_depth_warning_time') or (current_time - self._last_depth_warning_time) > 60:
                    self._last_depth_warning_time = current_time
                    print(f"[depth] Info: Depth data not available for {self.full_symbol} (normal for indices or outside market hours)")
                return
            
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
    
    # Get interval from env (default: 5 seconds)
    interval = float(os.getenv("DEPTH_COLLECTOR_INTERVAL", "5.0"))
    
    collector.run_forever(interval=interval)


if __name__ == "__main__":
    main()

