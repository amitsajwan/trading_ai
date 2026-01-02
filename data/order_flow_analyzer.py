"""Order flow analysis utilities."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OrderFlowAnalyzer:
    """Analyze order flow and market depth signals."""
    
    @staticmethod
    def calculate_buy_sell_imbalance(buy_quantity: int, sell_quantity: int) -> Dict[str, Any]:
        """
        Calculate buy-sell imbalance indicators.
        
        Args:
            buy_quantity: Total buy quantity
            sell_quantity: Total sell quantity
        
        Returns:
            Imbalance indicators
        """
        total_quantity = buy_quantity + sell_quantity
        
        if total_quantity == 0:
            return {
                "imbalance_ratio": 0.5,
                "imbalance_pct": 0.0,
                "imbalance_status": "NEUTRAL",
                "buy_pressure": 0.0,
                "sell_pressure": 0.0
            }
        
        imbalance_ratio = buy_quantity / total_quantity
        imbalance_pct = (imbalance_ratio - 0.5) * 200  # Convert to percentage
        
        return {
            "imbalance_ratio": float(imbalance_ratio),
            "imbalance_pct": float(imbalance_pct),
            "imbalance_status": (
                "STRONG_BUY" if imbalance_ratio > 0.7 else
                "BUY" if imbalance_ratio > 0.6 else
                "SELL" if imbalance_ratio < 0.4 else
                "STRONG_SELL" if imbalance_ratio < 0.3 else
                "NEUTRAL"
            ),
            "buy_pressure": float(buy_quantity / total_quantity) if total_quantity > 0 else 0.0,
            "sell_pressure": float(sell_quantity / total_quantity) if total_quantity > 0 else 0.0
        }
    
    @staticmethod
    def analyze_bid_ask_spread(bid_price: Optional[float], ask_price: Optional[float], current_price: float) -> Dict[str, Any]:
        """
        Analyze bid-ask spread.
        
        Args:
            bid_price: Best bid price
            ask_price: Best ask price
            current_price: Current market price
        
        Returns:
            Spread analysis
        """
        if not bid_price or not ask_price:
            return {
                "spread": None,
                "spread_pct": None,
                "spread_status": "UNKNOWN",
                "mid_price": current_price
            }
        
        spread = ask_price - bid_price
        mid_price = (bid_price + ask_price) / 2
        spread_pct = (spread / mid_price * 100) if mid_price > 0 else 0
        
        return {
            "spread": float(spread),
            "spread_pct": float(spread_pct),
            "spread_status": (
                "WIDE" if spread_pct > 0.1 else
                "NARROW" if spread_pct < 0.05 else
                "NORMAL"
            ),
            "mid_price": float(mid_price),
            "bid_price": float(bid_price),
            "ask_price": float(ask_price)
        }
    
    @staticmethod
    def analyze_market_depth(depth_buy: List[Dict[str, Any]], depth_sell: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze market depth for support/resistance levels.
        
        Args:
            depth_buy: Buy side depth
            depth_sell: Sell side depth
        
        Returns:
            Depth analysis
        """
        if not depth_buy and not depth_sell:
            return {}
        
        # Calculate total buy/sell quantity at each level
        buy_quantity_levels = {}
        sell_quantity_levels = {}
        
        for level in depth_buy[:5]:  # Top 5 levels
            price = level.get("price")
            quantity = level.get("quantity", 0)
            if price:
                buy_quantity_levels[price] = quantity
        
        for level in depth_sell[:5]:  # Top 5 levels
            price = level.get("price")
            quantity = level.get("quantity", 0)
            if price:
                sell_quantity_levels[price] = quantity
        
        # Find significant support/resistance levels
        support_levels = sorted(buy_quantity_levels.items(), key=lambda x: x[1], reverse=True)[:3]
        resistance_levels = sorted(sell_quantity_levels.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            "support_levels": [{"price": float(p), "quantity": int(q)} for p, q in support_levels],
            "resistance_levels": [{"price": float(p), "quantity": int(q)} for p, q in resistance_levels],
            "total_buy_depth": sum(buy_quantity_levels.values()),
            "total_sell_depth": sum(sell_quantity_levels.values()),
            "depth_imbalance": (
                "BUY_HEAVY" if sum(buy_quantity_levels.values()) > sum(sell_quantity_levels.values()) * 1.5 else
                "SELL_HEAVY" if sum(sell_quantity_levels.values()) > sum(buy_quantity_levels.values()) * 1.5 else
                "BALANCED"
            )
        }
    
    @staticmethod
    def detect_large_orders(depth_buy: List[Dict[str, Any]], depth_sell: List[Dict[str, Any]], threshold: int = 10000) -> Dict[str, Any]:
        """
        Detect large orders in market depth.
        
        Args:
            depth_buy: Buy side depth
            depth_sell: Sell side depth
            threshold: Minimum quantity to consider "large"
        
        Returns:
            Large order detection
        """
        large_buy_orders = []
        large_sell_orders = []
        
        for level in depth_buy:
            quantity = level.get("quantity", 0)
            if quantity >= threshold:
                large_buy_orders.append({
                    "price": level.get("price"),
                    "quantity": quantity
                })
        
        for level in depth_sell:
            quantity = level.get("quantity", 0)
            if quantity >= threshold:
                large_sell_orders.append({
                    "price": level.get("price"),
                    "quantity": quantity
                })
        
        return {
            "large_buy_orders": large_buy_orders,
            "large_sell_orders": large_sell_orders,
            "has_large_orders": len(large_buy_orders) > 0 or len(large_sell_orders) > 0,
            "large_order_pressure": (
                "BUY" if len(large_buy_orders) > len(large_sell_orders) else
                "SELL" if len(large_sell_orders) > len(large_buy_orders) else
                "NEUTRAL"
            )
        }

