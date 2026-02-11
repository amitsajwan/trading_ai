"""Enhanced Market Tick with depth data support.

Extends the basic MarketTick to include full market depth information
from Kite's Full Mode streaming.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass
class DepthLevel:
    """Single level of market depth."""
    price: float
    quantity: int
    orders: int = 0


@dataclass
class MarketDepth:
    """Market depth data (5 levels buy/sell)."""
    buy: List[DepthLevel]
    sell: List[DepthLevel]
    
    @property
    def best_bid(self) -> Optional[DepthLevel]:
        """Get best bid (highest buy price)."""
        return self.buy[0] if self.buy else None
    
    @property
    def best_ask(self) -> Optional[DepthLevel]:
        """Get best ask (lowest sell price)."""
        return self.sell[0] if self.sell else None
    
    @property
    def spread(self) -> Optional[float]:
        """Calculate bid-ask spread."""
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return None
    
    @property
    def mid_price(self) -> Optional[float]:
        """Calculate mid price."""
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2
        return None
    
    @property
    def total_bid_quantity(self) -> int:
        """Total quantity on buy side."""
        return sum(level.quantity for level in self.buy)
    
    @property
    def total_ask_quantity(self) -> int:
        """Total quantity on sell side."""
        return sum(level.quantity for level in self.sell)
    
    @property
    def order_imbalance(self) -> float:
        """Calculate order book imbalance ratio.
        
        Returns:
            Positive = more buyers, Negative = more sellers
            Range: -1 to +1
        """
        total_bid = self.total_bid_quantity
        total_ask = self.total_ask_quantity
        total = total_bid + total_ask
        
        if total == 0:
            return 0.0
        
        return (total_bid - total_ask) / total


@dataclass
class EnhancedMarketTick:
    """Enhanced market tick with full depth data.
    
    Includes all data from Kite Full Mode:
    - Basic tick data (price, volume)
    - Market depth (5 levels bid/ask)
    - OHLC data
    - Open Interest (derivatives)
    """
    # Basic tick data
    instrument: str
    timestamp: datetime
    last_price: float
    volume: int
    
    # Additional tick fields
    last_quantity: Optional[int] = None
    average_price: Optional[float] = None
    
    # Depth data (Kite Full Mode)
    depth: Optional[MarketDepth] = None
    
    # OHLC (from Kite)
    ohlc_open: Optional[float] = None
    ohlc_high: Optional[float] = None
    ohlc_low: Optional[float] = None
    ohlc_close: Optional[float] = None
    
    # Derivatives data
    open_interest: Optional[int] = None
    oi_day_high: Optional[int] = None
    oi_day_low: Optional[int] = None
    
    # Volume breakup
    buy_quantity: Optional[int] = None
    sell_quantity: Optional[int] = None
    
    # Compatibility fields
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    
    def __post_init__(self):
        """Calculate derived fields from depth if available."""
        if self.depth:
            # Set bid/ask from depth if not provided
            if not self.bid_price and self.depth.best_bid:
                self.bid_price = self.depth.best_bid.price
            if not self.ask_price and self.depth.best_ask:
                self.ask_price = self.depth.best_ask.price
    
    @classmethod
    def from_kite_tick(cls, tick_data: dict, instrument: str) -> 'EnhancedMarketTick':
        """Create from Kite ticker tick data.
        
        Args:
            tick_data: Raw tick from KiteTicker
            instrument: Instrument symbol
            
        Returns:
            EnhancedMarketTick instance
        """
        # Parse depth data
        depth = None
        depth_data = tick_data.get('depth')
        if depth_data:
            buy_levels = [
                DepthLevel(
                    price=level['price'],
                    quantity=level['quantity'],
                    orders=level.get('orders', 0)
                )
                for level in depth_data.get('buy', [])
            ]
            sell_levels = [
                DepthLevel(
                    price=level['price'],
                    quantity=level['quantity'],
                    orders=level.get('orders', 0)
                )
                for level in depth_data.get('sell', [])
            ]
            depth = MarketDepth(buy=buy_levels, sell=sell_levels)
        
        # Parse OHLC
        ohlc = tick_data.get('ohlc', {})
        
        return cls(
            instrument=instrument,
            timestamp=tick_data.get('timestamp') or tick_data.get('exchange_timestamp') or datetime.now(),
            last_price=tick_data.get('last_price') or tick_data.get('last'),
            volume=tick_data.get('volume', 0),
            last_quantity=tick_data.get('last_quantity'),
            average_price=tick_data.get('average_price') or tick_data.get('average_traded_price'),
            depth=depth,
            ohlc_open=ohlc.get('open'),
            ohlc_high=ohlc.get('high'),
            ohlc_low=ohlc.get('low'),
            ohlc_close=ohlc.get('close'),
            open_interest=tick_data.get('oi'),
            oi_day_high=tick_data.get('oi_day_high'),
            oi_day_low=tick_data.get('oi_day_low'),
            buy_quantity=tick_data.get('buy_quantity'),
            sell_quantity=tick_data.get('sell_quantity')
        )
    
    def get_depth_metrics(self) -> dict:
        """Get depth-based metrics.
        
        Returns:
            Dictionary with spread, imbalance, liquidity metrics
        """
        if not self.depth:
            return {}
        
        return {
            "spread": self.depth.spread,
            "mid_price": self.depth.mid_price,
            "bid_qty": self.depth.total_bid_quantity,
            "ask_qty": self.depth.total_ask_quantity,
            "imbalance": self.depth.order_imbalance,
            "liquidity_score": (self.depth.total_bid_quantity + self.depth.total_ask_quantity) / 2
        }
