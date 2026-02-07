"""Simple schema classes for provider responses."""

from typing import List, Optional
from dataclasses import dataclass


@dataclass
class PriceLevel:
    """Represents a price level in market depth."""
    price: float
    quantity: int


@dataclass
class Depth:
    """Represents market depth with buy/sell orders."""
    buy: List[PriceLevel]
    sell: List[PriceLevel]
    timestamp: str


@dataclass
class Quote:
    """Represents a market quote."""
    symbol: str
    last_price: float
    timestamp: str
    depth: Depth