"""Spread Builder Utilities for Calculating Spread Metrics.

This module provides utilities for calculating spread strategy metrics:
- Max profit and max loss
- Breakeven points
- Net Greeks (delta, gamma, theta, vega, rho)
- Risk/reward ratio
- Probability of profit
- Margin requirements
"""

import logging
import math
from typing import List, Tuple
from .base_strategy import OptionLeg, SpreadMetrics, OrderAction, OptionType

logger = logging.getLogger(__name__)


class SpreadBuilder:
    """Utility class for building and calculating spread metrics.
    
    This class provides static methods for calculating all spread metrics
    including P&L profiles, Greeks aggregation, and risk measures.
    """
    
    @staticmethod
    def calculate_spread_metrics(
        legs: List[OptionLeg],
        lot_size: int = 25
    ) -> SpreadMetrics:
        """Calculate all spread metrics.
        
        Args:
            legs: List of OptionLeg objects forming the spread
            lot_size: Lot size for the instrument (default: 25 for Bank Nifty)
        
        Returns:
            SpreadMetrics object with calculated metrics
        """
        if not legs:
            logger.warning("Empty legs list, returning zero metrics")
            return SpreadMetrics(
                max_profit=0.0,
                max_loss=0.0,
                net_premium=0.0,
                margin_required=0.0,
                risk_reward_ratio=0.0,
                probability_of_profit=0.5
            )
        
        # Calculate net premium (credit positive, debit negative)
        net_premium = SpreadBuilder._calculate_net_premium(legs)
        
        # Calculate net Greeks
        net_delta, net_gamma, net_theta, net_vega, net_rho = \
            SpreadBuilder._calculate_net_greeks(legs)
        
        # Calculate P&L range
        max_profit, max_loss = SpreadBuilder._calculate_pnl_range(
            legs, net_premium, lot_size
        )
        
        # Calculate breakeven points
        breakevens = SpreadBuilder._calculate_breakevens(legs, net_premium)
        
        # Estimate margin
        margin = SpreadBuilder._estimate_margin(
            legs, net_premium, max_loss, lot_size
        )
        
        # Calculate risk/reward ratio
        rr_ratio = SpreadBuilder._calculate_risk_reward_ratio(
            max_profit, max_loss
        )
        
        # Estimate probability of profit
        pop = SpreadBuilder._estimate_pop(legs, breakevens, net_delta)
        
        return SpreadMetrics(
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven_points=breakevens,
            net_premium=net_premium * lot_size,
            margin_required=margin,
            risk_reward_ratio=rr_ratio,
            probability_of_profit=pop,
            net_delta=net_delta,
            net_theta=net_theta * lot_size,  # Per day for entire position
            net_vega=net_vega * lot_size,  # Per 1% IV change for entire position
            net_gamma=net_gamma * lot_size,
            net_rho=net_rho * lot_size
        )
    
    @staticmethod
    def _calculate_net_premium(legs: List[OptionLeg]) -> float:
        """Calculate net premium (credit positive, debit negative).
        
        Credit spread: net_premium > 0 (receive premium)
        Debit spread: net_premium < 0 (pay premium)
        """
        net = 0.0
        for leg in legs:
            if leg.action == OrderAction.SELL:
                net += leg.premium * leg.quantity  # Receive premium
            else:  # BUY
                net -= leg.premium * leg.quantity  # Pay premium
        
        return net
    
    @staticmethod
    def _calculate_net_greeks(legs: List[OptionLeg]) -> Tuple[float, float, float, float, float]:
        """Calculate net Greeks across all legs.
        
        Returns:
            Tuple of (net_delta, net_gamma, net_theta, net_vega, net_rho)
        """
        net_delta = 0.0
        net_gamma = 0.0
        net_theta = 0.0
        net_vega = 0.0
        net_rho = 0.0
        
        for leg in legs:
            multiplier = leg.quantity
            if leg.action == OrderAction.BUY:
                # Buying adds to position
                greek_multiplier = multiplier
            else:  # SELL
                # Selling reduces position
                greek_multiplier = -multiplier
            
            if leg.delta is not None:
                net_delta += leg.delta * greek_multiplier
            if leg.gamma is not None:
                net_gamma += leg.gamma * greek_multiplier
            if leg.theta is not None:
                net_theta += leg.theta * greek_multiplier
            if leg.vega is not None:
                net_vega += leg.vega * greek_multiplier
            if leg.rho is not None:
                net_rho += leg.rho * greek_multiplier
        
        return (net_delta, net_gamma, net_theta, net_vega, net_rho)
    
    @staticmethod
    def _calculate_pnl_range(
        legs: List[OptionLeg],
        net_premium: float,
        lot_size: int
    ) -> Tuple[float, float]:
        """Calculate max profit and max loss.
        
        This is a simplified calculation. For complex spreads like iron condors,
        the P&L profile needs to be calculated across different price levels.
        
        Args:
            legs: List of OptionLeg objects
            net_premium: Net premium per lot
            lot_size: Lot size
        
        Returns:
            Tuple of (max_profit, max_loss) in currency units
        """
        if not legs:
            return (0.0, 0.0)
        
        # Get all strikes
        strikes = sorted(set([leg.strike for leg in legs]))
        
        if len(strikes) < 2:
            # Single-leg position (not a true spread)
            # Max profit = premium received (if credit) or unlimited (if debit)
            # Max loss = premium paid (if debit) or unlimited (if credit)
            net_premium_total = net_premium * lot_size
            
            # Check if this is a credit or debit spread
            sells = [l for l in legs if l.action == OrderAction.SELL]
            buys = [l for l in legs if l.action == OrderAction.BUY]
            
            if len(sells) > len(buys):
                # Net credit - max profit = credit, max loss = spread width - credit
                max_profit = net_premium_total
                max_loss = abs(net_premium_total) * 10  # Simplified - assume 10x risk
            else:
                # Net debit - max loss = debit, max profit = spread width - debit
                max_loss = abs(net_premium_total)
                max_profit = abs(net_premium_total) * 2  # Simplified - assume 2x profit potential
            
            return (max_profit, max_loss)
        
        # Multi-leg spread
        min_strike = min(strikes)
        max_strike = max(strikes)
        spread_width = max_strike - min_strike
        
        net_premium_total = net_premium * lot_size
        
        # Determine if credit or debit spread
        # Credit spread: net_premium > 0 (sell high, buy low)
        # Debit spread: net_premium < 0 (buy low, sell high)
        
        if net_premium > 0:
            # Credit spread
            # Max profit = net credit received
            # Max loss = spread width - net credit
            max_profit = net_premium_total
            max_loss = (spread_width * lot_size) - max_profit
        else:
            # Debit spread
            # Max loss = net debit paid
            # Max profit = spread width - net debit
            max_loss = abs(net_premium_total)
            max_profit = (spread_width * lot_size) - max_loss
        
        # For complex spreads (iron condor, butterfly), need more sophisticated calculation
        # This is handled in the specific strategy classes
        
        return (max_profit, max_loss)
    
    @staticmethod
    def _calculate_breakevens(
        legs: List[OptionLeg],
        net_premium: float
    ) -> List[float]:
        """Calculate breakeven points.
        
        Args:
            legs: List of OptionLeg objects
            net_premium: Net premium per lot
        
        Returns:
            List of breakeven price levels
        """
        breakevens = []
        
        if not legs:
            return breakevens
        
        # Separate calls and puts
        calls = [leg for leg in legs if leg.option_type == OptionType.CALL]
        puts = [leg for leg in legs if leg.option_type == OptionType.PUT]
        
        # For credit spreads:
        if net_premium > 0:
            # Call credit spread: Breakeven = short_strike + premium
            if calls:
                call_strikes = sorted([leg.strike for leg in calls])
                # Assume short strike is lower, long strike is higher
                if len(call_strikes) >= 2:
                    short_strike = min(call_strikes)
                    breakevens.append(short_strike + net_premium)
                elif len(call_strikes) == 1:
                    breakevens.append(call_strikes[0] + net_premium)
            
            # Put credit spread: Breakeven = short_strike - premium
            if puts:
                put_strikes = sorted([leg.strike for leg in puts])
                if len(put_strikes) >= 2:
                    short_strike = max(put_strikes)
                    breakevens.append(short_strike - net_premium)
                elif len(put_strikes) == 1:
                    breakevens.append(put_strikes[0] - net_premium)
        
        # For debit spreads:
        else:
            # Call debit spread: Breakeven = long_strike + premium
            if calls:
                call_strikes = sorted([leg.strike for leg in calls])
                if len(call_strikes) >= 2:
                    long_strike = min(call_strikes)
                    breakevens.append(long_strike + abs(net_premium))
                elif len(call_strikes) == 1:
                    breakevens.append(call_strikes[0] + abs(net_premium))
            
            # Put debit spread: Breakeven = long_strike - premium
            if puts:
                put_strikes = sorted([leg.strike for leg in puts])
                if len(put_strikes) >= 2:
                    long_strike = max(put_strikes)
                    breakevens.append(long_strike - abs(net_premium))
                elif len(put_strikes) == 1:
                    breakevens.append(put_strikes[0] - abs(net_premium))
        
        # Remove duplicates and sort
        breakevens = sorted(list(set(breakevens)))
        
        return breakevens
    
    @staticmethod
    def _estimate_margin(
        legs: List[OptionLeg],
        net_premium: float,
        max_loss: float,
        lot_size: int
    ) -> float:
        """Estimate margin required for the spread.
        
        Simplified margin calculation. Real margin depends on broker rules.
        
        For credit spreads:
        - Margin = spread width - credit received
        
        For debit spreads:
        - Margin = debit paid (no additional margin typically required)
        
        Args:
            legs: List of OptionLeg objects
            net_premium: Net premium per lot
            max_loss: Maximum loss
            lot_size: Lot size
        
        Returns:
            Estimated margin required in currency units
        """
        if net_premium > 0:
            # Credit spread: margin = max loss
            return max_loss
        else:
            # Debit spread: margin = premium paid
            return abs(net_premium) * lot_size
    
    @staticmethod
    def _calculate_risk_reward_ratio(
        max_profit: float,
        max_loss: float
    ) -> float:
        """Calculate risk/reward ratio.
        
        Args:
            max_profit: Maximum profit
            max_loss: Maximum loss
        
        Returns:
            Risk/reward ratio (max_profit / max_loss), or 0 if max_loss <= 0
        """
        if max_loss <= 0:
            return 0.0
        
        return max_profit / max_loss
    
    @staticmethod
    def _estimate_pop(
        legs: List[OptionLeg],
        breakevens: List[float],
        net_delta: float
    ) -> float:
        """Estimate probability of profit.
        
        Uses net delta as a proxy for probability of profit.
        For credit spreads, typically 60-70% PoP.
        For debit spreads, typically 30-40% PoP.
        
        Args:
            legs: List of OptionLeg objects
            breakevens: List of breakeven points
            net_delta: Net delta of the spread
        
        Returns:
            Estimated probability of profit (0.0 to 1.0)
        """
        # Check if credit or debit spread
        sells = [leg for leg in legs if leg.action == OrderAction.SELL]
        buys = [leg for leg in legs if leg.action == OrderAction.BUY]
        
        # Base PoP depends on spread type
        if len(sells) > len(buys):
            # Credit spread - typically higher PoP
            base_pop = 0.65
        else:
            # Debit spread - typically lower PoP
            base_pop = 0.35
        
        # Adjust based on net delta (directional bias)
        # Net delta > 0 (bullish) in a bullish market = higher PoP
        # Net delta < 0 (bearish) in a bearish market = higher PoP
        # For now, we use a simple adjustment
        delta_adjustment = abs(net_delta) * 0.1
        
        # Final PoP
        pop = base_pop + delta_adjustment
        
        # Clamp between 0.0 and 1.0
        return max(0.0, min(1.0, pop))
