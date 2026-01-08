import json
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

from .base import ProviderBase
from config import get_config
from schemas import Quote, Depth, PriceLevel


class MockProvider(ProviderBase):
    def __init__(self, seed_price: float = None):
        cfg = get_config()
        self.symbol = cfg.instrument_symbol
        self.key = cfg.instrument_key
        self.price = seed_price or (60000.0 if self.symbol.upper().startswith("BANK") else 1000.0)

    def quote(self, symbols: List[str]) -> Dict[str, Any]:
        # Accept list of symbols like ['NSE:BANKNIFTY'] or one-element
        out = {}
        for s in symbols:
            # Simple deterministic-ish price movement
            change = random.uniform(-20, 20)
            self.price = max(0.01, self.price + change)
            depth = Depth(
                buy=[PriceLevel(price=round(self.price - 1, 2), quantity=100)],
                sell=[PriceLevel(price=round(self.price + 1, 2), quantity=100)],
                timestamp=datetime.now().isoformat()
            )
            q = Quote(symbol=s, last_price=round(self.price, 2), timestamp=datetime.now().isoformat(), depth=depth)
            out[s] = q
        return out

    def profile(self) -> Dict[str, Any]:
        return {"user_id": "mock_user", "broker": "MOCK"}

    def historical_data(self, instrument_token: str, from_date: str, to_date: str, interval: str) -> List[Dict[str, Any]]:
        # Return simple synthetic candles between from_date and to_date
        start = datetime.fromisoformat(from_date)
        end = datetime.fromisoformat(to_date)
        candles = []
        cur = start
        while cur <= end:
            open_p = round(self.price + random.uniform(-10, 10), 2)
            close_p = round(open_p + random.uniform(-5, 5), 2)
            high = max(open_p, close_p) + random.uniform(0, 2)
            low = min(open_p, close_p) - random.uniform(0, 2)
            candles.append({
                "date": cur.isoformat(),
                "timestamp": cur.isoformat(),
                "open": open_p,
                "high": round(high, 2),
                "low": round(low, 2),
                "close": close_p,
                "volume": random.randint(1000, 10000)
            })
            if interval.lower().startswith("1"):
                cur += timedelta(minutes=1)
            else:
                cur += timedelta(minutes=5)
        return candles
