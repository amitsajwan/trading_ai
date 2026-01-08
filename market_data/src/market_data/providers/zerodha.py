import json
import os
from typing import Any, Dict, List, Optional

try:
    from kiteconnect import KiteConnect
except ImportError:
    KiteConnect = None

from .base import ProviderBase
from schemas import Quote, Depth, PriceLevel


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
        quotes = self.kite.quote(symbols)
        # Convert to Quote objects
        result = {}
        for symbol, data in quotes.items():
            depth_data = data.get('depth', {})
            depth = Depth(
                buy=[PriceLevel(price=b['price'], quantity=b['quantity']) for b in depth_data.get('buy', [])],
                sell=[PriceLevel(price=s['price'], quantity=s['quantity']) for s in depth_data.get('sell', [])],
                timestamp=data.get('timestamp', '')
            )
            quote = Quote(
                symbol=symbol,
                last_price=data['last_price'],
                timestamp=data.get('timestamp', ''),
                depth=depth
            )
            result[symbol] = quote
        return result

    def profile(self) -> Dict[str, Any]:
        return self.kite.profile()

    def historical_data(self, instrument_token: str, from_date: str, to_date: str, interval: str) -> List[Dict[str, Any]]:
        return self.kite.historical_data(instrument_token, from_date, to_date, interval)
