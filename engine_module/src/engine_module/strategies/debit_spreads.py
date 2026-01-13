"""Debit Spread Strategies Implementation.

Debit Spreads are options strategies that pay net premium:
- Bull Call Spread: Buy lower strike call, sell higher strike call
- Bear Put Spread: Buy higher strike put, sell lower strike put

Both strategies profit from directional movement and have limited risk.
"""

import logging
from typing import List, Dict, Optional, Any

from .base_strategy import (
    BaseSpreadStrategy,
    OptionLeg,
    SpreadMetrics,
    OptionType,
    OrderAction
)
from .spread_builder import SpreadBuilder

logger = logging.getLogger(__name__)


class BullCallSpreadStrategy(BaseSpreadStrategy):
    """Bull Call Spread strategy (debit spread).
    
    Buy lower strike call, sell higher strike call.
    - Best for: Bullish markets
    - Maximum profit: Spread width - net debit
    - Maximum loss: Net debit paid
    - Breakeven: Long strike + net debit
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Bull Call Spread strategy.
        
        Args:
            config: Configuration dictionary with:
                - lot_size: Lot size (default: 25)
                - otm_percentage: OTM percentage for short strike (default: 0.02 = 2%)
                - spread_width: Width of spread in percentage (default: 0.01 = 1%)
        """
        super().__init__(config)
        
        self.otm_percentage = config.get('otm_percentage', 0.02) if config else 0.02  # 2% OTM for short
        self.spread_width = config.get('spread_width', 0.01) if config else 0.01  # 1% width
    
    def build_spread(
        self,
        spot_price: float,
        option_chain: Dict[str, Any],
        expiry: Optional[str] = None
    ) -> Optional[List[OptionLeg]]:
        """Build Bull Call Spread.
        
        Structure:
        - Buy lower strike call (ITM or ATM)
        - Sell higher strike call (OTM)
        
        Args:
            spot_price: Current spot price
            option_chain: Options chain data
            expiry: Target expiry date
        
        Returns:
            List of 2 OptionLeg objects if valid spread can be built, None otherwise
        """
        if not option_chain:
            return None
        
        # Calculate strikes (both calls, long strike at/above spot, short strike above)
        long_strike_target = spot_price * (1 - 0.005)  # Slightly ITM or ATM
        short_strike_target = spot_price * (1 + self.otm_percentage)
        
        long_strike = self.find_strike(long_strike_target, option_chain)
        short_strike = self.find_strike(short_strike_target, option_chain)
        
        if not long_strike or not short_strike:
            return None
        
        # Ensure long < short (both calls, lower strike = long, higher = short)
        if long_strike >= short_strike:
            logger.warning(f"Invalid strike ordering: long={long_strike}, short={short_strike}")
            return None
        
        # Get option data
        long_data = self.get_option_data(long_strike, OptionType.CALL, option_chain)
        short_data = self.get_option_data(short_strike, OptionType.CALL, option_chain)
        
        if not long_data or not short_data:
            return None
        
        # Validate liquidity
        long_leg = OptionLeg(long_strike, OptionType.CALL, OrderAction.BUY, 1, 0, expiry or "")
        short_leg = OptionLeg(short_strike, OptionType.CALL, OrderAction.SELL, 1, 0, expiry or "")
        
        if not self.validate_liquidity(long_leg, long_data) or \
           not self.validate_liquidity(short_leg, short_data):
            return None
        
        # Get expiry
        if expiry is None:
            expiry = long_data.get('expiry') or short_data.get('expiry')
            if not expiry:
                for strike_data in option_chain.values():
                    if isinstance(strike_data, dict) and 'CE' in strike_data:
                        expiry = strike_data['CE'].get('expiry')
                        if expiry:
                            break
        
        if not expiry:
            return None
        
        # Extract premiums and Greeks
        long_premium = long_data.get('last_price') or long_data.get('ltp') or long_data.get('premium', 0)
        short_premium = short_data.get('last_price') or short_data.get('ltp') or short_data.get('premium', 0)
        
        # Build legs
        legs = [
            OptionLeg(
                strike=long_strike,
                option_type=OptionType.CALL,
                action=OrderAction.BUY,
                quantity=1,
                premium=long_premium,
                expiry=expiry,
                delta=long_data.get('delta'),
                gamma=long_data.get('gamma'),
                theta=long_data.get('theta'),
                vega=long_data.get('vega'),
                iv=long_data.get('iv') or long_data.get('implied_volatility'),
                volume=long_data.get('volume'),
                oi=long_data.get('oi')
            ),
            OptionLeg(
                strike=short_strike,
                option_type=OptionType.CALL,
                action=OrderAction.SELL,
                quantity=1,
                premium=short_premium,
                expiry=expiry,
                delta=short_data.get('delta'),
                gamma=short_data.get('gamma'),
                theta=short_data.get('theta'),
                vega=short_data.get('vega'),
                iv=short_data.get('iv') or short_data.get('implied_volatility'),
                volume=short_data.get('volume'),
                oi=short_data.get('oi')
            )
        ]
        
        logger.info(f"Bull Call Spread built: Long {long_strike}, Short {short_strike}")
        return legs
    
    def calculate_metrics(self, legs: List[OptionLeg]) -> SpreadMetrics:
        """Calculate Bull Call Spread metrics."""
        return SpreadBuilder.calculate_spread_metrics(legs, self.lot_size)


class BearPutSpreadStrategy(BaseSpreadStrategy):
    """Bear Put Spread strategy (debit spread).
    
    Buy higher strike put, sell lower strike put.
    - Best for: Bearish markets
    - Maximum profit: Spread width - net debit
    - Maximum loss: Net debit paid
    - Breakeven: Long strike - net debit
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Bear Put Spread strategy.
        
        Args:
            config: Configuration dictionary with:
                - lot_size: Lot size (default: 25)
                - otm_percentage: OTM percentage for short strike (default: 0.02 = 2%)
                - spread_width: Width of spread in percentage (default: 0.01 = 1%)
        """
        super().__init__(config)
        
        self.otm_percentage = config.get('otm_percentage', 0.02) if config else 0.02  # 2% OTM for short
        self.spread_width = config.get('spread_width', 0.01) if config else 0.01  # 1% width
    
    def build_spread(
        self,
        spot_price: float,
        option_chain: Dict[str, Any],
        expiry: Optional[str] = None
    ) -> Optional[List[OptionLeg]]:
        """Build Bear Put Spread.
        
        Structure:
        - Buy higher strike put (ITM or ATM)
        - Sell lower strike put (OTM)
        
        Args:
            spot_price: Current spot price
            option_chain: Options chain data
            expiry: Target expiry date
        
        Returns:
            List of 2 OptionLeg objects if valid spread can be built, None otherwise
        """
        if not option_chain:
            return None
        
        # Calculate strikes (both puts, long strike at/below spot, short strike below)
        long_strike_target = spot_price * (1 + 0.005)  # Slightly ITM or ATM
        short_strike_target = spot_price * (1 - self.otm_percentage)
        
        long_strike = self.find_strike(long_strike_target, option_chain)
        short_strike = self.find_strike(short_strike_target, option_chain)
        
        if not long_strike or not short_strike:
            return None
        
        # Ensure long > short (both puts, higher strike = long, lower = short)
        if long_strike <= short_strike:
            logger.warning(f"Invalid strike ordering: long={long_strike}, short={short_strike}")
            return None
        
        # Get option data
        long_data = self.get_option_data(long_strike, OptionType.PUT, option_chain)
        short_data = self.get_option_data(short_strike, OptionType.PUT, option_chain)
        
        if not long_data or not short_data:
            return None
        
        # Validate liquidity
        long_leg = OptionLeg(long_strike, OptionType.PUT, OrderAction.BUY, 1, 0, expiry or "")
        short_leg = OptionLeg(short_strike, OptionType.PUT, OrderAction.SELL, 1, 0, expiry or "")
        
        if not self.validate_liquidity(long_leg, long_data) or \
           not self.validate_liquidity(short_leg, short_data):
            return None
        
        # Get expiry
        if expiry is None:
            expiry = long_data.get('expiry') or short_data.get('expiry')
            if not expiry:
                for strike_data in option_chain.values():
                    if isinstance(strike_data, dict) and 'PE' in strike_data:
                        expiry = strike_data['PE'].get('expiry')
                        if expiry:
                            break
        
        if not expiry:
            return None
        
        # Extract premiums and Greeks
        long_premium = long_data.get('last_price') or long_data.get('ltp') or long_data.get('premium', 0)
        short_premium = short_data.get('last_price') or short_data.get('ltp') or short_data.get('premium', 0)
        
        # Build legs
        legs = [
            OptionLeg(
                strike=long_strike,
                option_type=OptionType.PUT,
                action=OrderAction.BUY,
                quantity=1,
                premium=long_premium,
                expiry=expiry,
                delta=long_data.get('delta'),
                gamma=long_data.get('gamma'),
                theta=long_data.get('theta'),
                vega=long_data.get('vega'),
                iv=long_data.get('iv') or long_data.get('implied_volatility'),
                volume=long_data.get('volume'),
                oi=long_data.get('oi')
            ),
            OptionLeg(
                strike=short_strike,
                option_type=OptionType.PUT,
                action=OrderAction.SELL,
                quantity=1,
                premium=short_premium,
                expiry=expiry,
                delta=short_data.get('delta'),
                gamma=short_data.get('gamma'),
                theta=short_data.get('theta'),
                vega=short_data.get('vega'),
                iv=short_data.get('iv') or short_data.get('implied_volatility'),
                volume=short_data.get('volume'),
                oi=short_data.get('oi')
            )
        ]
        
        logger.info(f"Bear Put Spread built: Long {long_strike}, Short {short_strike}")
        return legs
    
    def calculate_metrics(self, legs: List[OptionLeg]) -> SpreadMetrics:
        """Calculate Bear Put Spread metrics."""
        return SpreadBuilder.calculate_spread_metrics(legs, self.lot_size)
