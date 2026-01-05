"""Liquidity filtering using Kite's top 5 market depth."""

import logging
from typing import Dict, Any, Optional, Tuple
from data.market_memory import MarketMemory

logger = logging.getLogger(__name__)


class LiquidityFilter:
    """
    Filter trades based on market depth liquidity.
    
    Uses Kite's top 5 bid/ask levels to ensure:
    1. Sufficient depth to absorb order (avoid slippage)
    2. Tight bid-ask spread (avoid wide markets)
    3. Depth imbalance detection (institutional flow)
    """
    
    def __init__(self, market_memory: MarketMemory):
        self.market_memory = market_memory
    
    def can_trade(
        self, 
        instrument: str, 
        side: str, 
        quantity: int,
        min_depth_multiplier: float = 3.0,
        max_spread_pct: float = 0.05
    ) -> Tuple[bool, str]:
        """
        Check if trade passes liquidity filters.
        
        Args:
            instrument: Instrument symbol
            side: "BUY" or "SELL"
            quantity: Order quantity (lots)
            min_depth_multiplier: Minimum depth = qty * multiplier (default: 3x)
            max_spread_pct: Maximum bid-ask spread % (default: 0.05%)
        
        Returns:
            (can_trade: bool, reason: str)
        """
        try:
            # Get latest tick with depth
            instrument_key = instrument.replace("-", "").replace(" ", "").upper()
            tick = self.market_memory.get_latest_tick(instrument_key)
            
            if not tick:
                return False, "NO_TICK_DATA"
            
            # Extract depth data
            depth_buy = tick.get("depth_buy", [])
            depth_sell = tick.get("depth_sell", [])
            total_bid_qty = tick.get("total_bid_quantity", 0)
            total_ask_qty = tick.get("total_ask_quantity", 0)
            best_bid = tick.get("best_bid_price")
            best_ask = tick.get("best_ask_price")
            
            if not depth_buy or not depth_sell:
                return False, "NO_DEPTH_DATA"
            
            # Check 1: Sufficient depth to absorb order
            min_required_depth = quantity * min_depth_multiplier
            
            if side == "BUY":
                available_depth = total_ask_qty
                if available_depth < min_required_depth:
                    return False, f"INSUFFICIENT_ASK_DEPTH ({available_depth} < {min_required_depth})"
            else:  # SELL
                available_depth = total_bid_qty
                if available_depth < min_required_depth:
                    return False, f"INSUFFICIENT_BID_DEPTH ({available_depth} < {min_required_depth})"
            
            # Check 2: Spread not too wide
            if best_bid and best_ask:
                spread = best_ask - best_bid
                mid_price = (best_bid + best_ask) / 2
                spread_pct = (spread / mid_price) * 100 if mid_price > 0 else 0
                
                if spread_pct > max_spread_pct:
                    return False, f"WIDE_SPREAD ({spread_pct:.3f}% > {max_spread_pct}%)"
            
            return True, "LIQUIDITY_OK"
            
        except Exception as exc:
            logger.error(f"Liquidity filter error: {exc}")
            return False, f"ERROR: {exc}"
    
    def estimate_slippage(
        self, 
        instrument: str, 
        side: str, 
        quantity: int
    ) -> Optional[float]:
        """
        Estimate slippage using weighted average depth price.
        
        Args:
            instrument: Instrument symbol
            side: "BUY" or "SELL"
            quantity: Order quantity
        
        Returns:
            Estimated slippage per unit (None if insufficient depth)
        """
        try:
            instrument_key = instrument.replace("-", "").replace(" ", "").upper()
            tick = self.market_memory.get_latest_tick(instrument_key)
            
            if not tick:
                return None
            
            depth = tick.get("depth_sell" if side == "BUY" else "depth_buy", [])
            best_price = tick.get("best_ask_price" if side == "BUY" else "best_bid_price")
            
            if not depth or not best_price:
                return None
            
            # Calculate weighted average fill price
            remaining_qty = quantity
            total_cost = 0.0
            
            for level in depth[:5]:  # Top 5 levels from Kite
                level_price = level.get("price", 0)
                level_qty = level.get("quantity", 0)
                
                if remaining_qty <= 0:
                    break
                
                fill_qty = min(remaining_qty, level_qty)
                total_cost += fill_qty * level_price
                remaining_qty -= fill_qty
            
            if remaining_qty > 0:
                # Not enough depth to fill order
                return None
            
            avg_fill_price = total_cost / quantity
            slippage = abs(avg_fill_price - best_price)
            
            return slippage
            
        except Exception as exc:
            logger.error(f"Slippage estimation error: {exc}")
            return None
    
    def get_depth_imbalance_signal(self, instrument: str) -> Dict[str, Any]:
        """
        Analyze depth imbalance for directional bias.
        
        Large bid depth = buying pressure
        Large ask depth = selling pressure
        
        Returns:
            {
                "imbalance_ratio": float (0-1, 0.5 = balanced),
                "signal": "BUY_PRESSURE" | "SELL_PRESSURE" | "BALANCED",
                "total_bid_qty": int,
                "total_ask_qty": int
            }
        """
        try:
            instrument_key = instrument.replace("-", "").replace(" ", "").upper()
            tick = self.market_memory.get_latest_tick(instrument_key)
            
            if not tick:
                return {"signal": "NO_DATA"}
            
            total_bid = tick.get("total_bid_quantity", 0)
            total_ask = tick.get("total_ask_quantity", 0)
            imbalance = tick.get("depth_imbalance", 0.5)
            
            # Determine signal
            if imbalance > 0.6:
                signal = "BUY_PRESSURE"
            elif imbalance < 0.4:
                signal = "SELL_PRESSURE"
            else:
                signal = "BALANCED"
            
            return {
                "imbalance_ratio": imbalance,
                "signal": signal,
                "total_bid_qty": total_bid,
                "total_ask_qty": total_ask,
                "confidence": abs(imbalance - 0.5) * 2  # 0 = no confidence, 1 = max
            }
            
        except Exception as exc:
            logger.error(f"Depth imbalance error: {exc}")
            return {"signal": "ERROR", "error": str(exc)}
