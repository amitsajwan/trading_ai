from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional


@dataclass
class PriceLevel:
    price: float
    quantity: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Depth:
    buy: List[PriceLevel]
    sell: List[PriceLevel]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "buy": [p.to_dict() for p in self.buy],
            "sell": [p.to_dict() for p in self.sell],
            "timestamp": self.timestamp
        }


@dataclass
class Quote:
    symbol: str
    last_price: float
    timestamp: str
    depth: Depth
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["depth"] = self.depth.to_dict()
        return d


@dataclass
class HistoricalCandle:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Profile:
    user_id: str
    broker: str
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


QuoteMap = Dict[str, Quote]
