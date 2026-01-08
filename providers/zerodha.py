import json
import os
from typing import Any, Dict, List, Optional

try:
    from kiteconnect import KiteConnect
except ImportError:
    KiteConnect = None

from .base import ProviderBase
from schemas import Quote


class ZerodhaProvider(ProviderBase):
    def __init__(self, api_key: str, access_token: str):
        if not KiteConnect:
            raise RuntimeError("KiteConnect library not installed")
        self.kite = KiteConnect(api_key=api_key)
        self.kite.set_access_token(access_token)

    @staticmethod
    def from_credentials_file(path: str = "credentials.json") -> Optional["ZerodhaProvider"]:
        if not KiteConnect:
            return None
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                creds = json.load(f)
            api_key = creds.get("api_key")
            access_token = creds.get("access_token")
            if not api_key or not access_token:
                return None
            return ZerodhaProvider(api_key, access_token)
        except Exception:
            return None

    def quote(self, symbols: List[str]) -> Dict[str, Any]:
        # Convert Kite quote response into Quote dataclass instances
        quotes = self.kite.quote(symbols)
        from schemas import Quote, Depth, PriceLevel
        out = {}
        from datetime import datetime
        for symbol, data in quotes.items():
            # Try to extract last_price and depth structure
            last_price = data.get('last_price') or data.get('last') or data.get('ltp') or None
            ts = datetime.now().isoformat()
            depth_raw = data.get('depth', {}) or {}
            buy = [PriceLevel(price=d.get('price'), quantity=d.get('quantity')) for d in depth_raw.get('buy', [])]
            sell = [PriceLevel(price=d.get('price'), quantity=d.get('quantity')) for d in depth_raw.get('sell', [])]
            depth = Depth(buy=buy, sell=sell, timestamp=ts)
            out[symbol] = Quote(symbol=symbol, last_price=float(last_price) if last_price is not None else 0.0, timestamp=ts, depth=depth)
        return out

    def profile(self) -> Dict[str, Any]:
        return self.kite.profile()

    def historical_data(self, instrument_token: str, from_date: str, to_date: str, interval: str) -> List[Dict[str, Any]]:
        return self.kite.historical_data(instrument_token, from_date, to_date, interval)
