"""Credit Spread Strategies Implementation.

Credit Spreads are options strategies that receive net premium:
- Bull Put Spread: Sell higher strike put, buy lower strike put
- Bear Call Spread: Sell lower strike call, buy higher strike call

Both strategies profit from time decay and staying within the profit zone.
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
    """Bull Put Spread strategy (also known as Bull Put Credit Spread).
    
    Sell higher strike put, buy lower strike put.
    - Best for: Bullish or neutral-bullish markets
    - Maximum profit: Net credit received
    - Maximum loss: Spread width - net credit
    - Breakeven: Short strike - net credit
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Bull Put Spread strategy.
        
        Args:
            config: Configuration dictionary with:
                - lot_size: Lot size (default: 25)
                - otm_percentage: OTM percentage for short strike (default: 0.01 = 1%)
                - spread_width: Width of spread in percentage (default: 0.005 = 0.5%)
        """
        super().__init__(config)
        
        self.otm_percentage = config.get('otm_percentage', 0.01) if config else 0.01  # 1% OTM
        self.spread_width = config.get('spread_width', 0.005) if config else 0.005  # 0.5% width
    
    def build_spread(
        self,
        spot_price: float,
        option_chain: Dict[str, Any],
        expiry: Optional[str] = None
    ) -> Optional[List[OptionLeg]]:
        """Build Bull Put Spread.
        
        Structure:
        - Sell higher strike put (OTM)
        - Buy lower strike put (further OTM for protection)
        
        Args:
            spot_price: Current spot price
            option_chain: Options chain data
            expiry: Target expiry date
        
        Returns:
            List of 2 OptionLeg objects if valid spread can be built, None otherwise
        """
        if not option_chain:
            return None
        
        # Calculate strikes (both puts, both below spot)
        short_strike_target = spot_price * (1 - self.otm_percentage)
        long_strike_target = spot_price * (1 - self.otm_percentage - self.spread_width)
        
        short_strike = self.find_strike(short_strike_target, option_chain)
        long_strike = self.find_strike(long_strike_target, option_chain)
        
        if not short_strike or not long_strike:
            return None
        
        # Ensure short > long (both puts, higher strike = less OTM)
        if short_strike <= long_strike:
            logger.warning(f"Invalid strike ordering: short={short_strike}, long={long_strike}")
            return None
        
        # Get option data
        short_data = self.get_option_data(short_strike, OptionType.PUT, option_chain)
        long_data = self.get_option_data(long_strike, OptionType.PUT, option_chain)
        
        if not short_data or not long_data:
            return None
        
        # Validate liquidity
        short_leg = OptionLeg(short_strike, OptionType.PUT, OrderAction.SELL, 1, 0, expiry or "")
        long_leg = OptionLeg(long_strike, OptionType.PUT, OrderAction.BUY, 1, 0, expiry or "")
        
        if not self.validate_liquidity(short_leg, short_data) or \
           not self.validate_liquidity(long_leg, long_data):
            return None
        
        # Get expiry
        if expiry is None:
            expiry = short_data.get('expiry') or long_data.get('expiry')
            if not expiry:
                for strike_data in option_chain.values():
                    if isinstance(strike_data, dict) and 'PE' in strike_data:
                        expiry = strike_data['PE'].get('expiry')
                        if expiry:
                            break
        
        if not expiry:
            return None
        
        # Extract premiums and Greeks
        short_premium = short_data.get('last_price') or short_data.get('ltp') or short_data.get('premium', 0)
        long_premium = long_data.get('last_price') or long_data.get('ltp') or long_data.get('premium', 0)
        
        # Build legs
        legs = [
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
            ),
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
            )
        ]
        
        logger.info(f"Bull Put Spread built: Short {short_strike}, Long {long_strike}")
        return legs
    
    def calculate_metrics(self, legs: List[OptionLeg]) -> SpreadMetrics:
        """Calculate Bull Put Spread metrics."""
        return SpreadBuilder.calculate_spread_metrics(legs, self.lot_size)


class BearPutSpreadStrategy(BaseSpreadStrategy):
    """Bear Call Spread strategy (also known as Bear Call Credit Spread).
    
    Sell lower strike call, buy higher strike call.
    - Best for: Bearish or neutral-bearish markets
    - Maximum profit: Net credit received
    - Maximum loss: Spread width - net credit
    - Breakeven: Short strike + net credit
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Bear Call Spread strategy.
        
        Args:
            config: Configuration dictionary with:
                - lot_size: Lot size (default: 25)
                - otm_percentage: OTM percentage for short strike (default: 0.01 = 1%)
                - spread_width: Width of spread in percentage (default: 0.005 = 0.5%)
        """
        super().__init__(config)
        
        self.otm_percentage = config.get('otm_percentage', 0.01) if config else 0.01  # 1% OTM
        self.spread_width = config.get('spread_width', 0.005) if config else 0.005  # 0.5% width
    
    def build_spread(
        self,
        spot_price: float,
        option_chain: Dict[str, Any],
        expiry: Optional[str] = None
    ) -> Optional[List[OptionLeg]]:
        """Build Bear Call Spread.
        
        Structure:
        - Sell lower strike call (OTM)
        - Buy higher strike call (further OTM for protection)
        
        Args:
            spot_price: Current spot price
            option_chain: Options chain data
            expiry: Target expiry date
        
        Returns:
            List of 2 OptionLeg objects if valid spread can be built, None otherwise
        """
        if not option_chain:
            return None
        
        # Calculate strikes (both calls, both above spot)
        short_strike_target = spot_price * (1 + self.otm_percentage)
        long_strike_target = spot_price * (1 + self.otm_percentage + self.spread_width)
        
        short_strike = self.find_strike(short_strike_target, option_chain)
        long_strike = self.find_strike(long_strike_target, option_chain)
        
        if not short_strike or not long_strike:
            return None
        
        # Ensure short < long (both calls, lower strike = less OTM)
        if short_strike >= long_strike:
            logger.warning(f"Invalid strike ordering: short={short_strike}, long={long_strike}")
            return None
        
        # Get option data
        short_data = self.get_option_data(short_strike, OptionType.CALL, option_chain)
        long_data = self.get_option_data(long_strike, OptionType.CALL, option_chain)
        
        if not short_data or not long_data:
            return None
        
        # Validate liquidity
        short_leg = OptionLeg(short_strike, OptionType.CALL, OrderAction.SELL, 1, 0, expiry or "")
        long_leg = OptionLeg(long_strike, OptionType.CALL, OrderAction.BUY, 1, 0, expiry or "")
        
        if not self.validate_liquidity(short_leg, short_data) or \
           not self.validate_liquidity(long_leg, long_data):
            return None
        
        # Get expiry
        if expiry is None:
            expiry = short_data.get('expiry') or long_data.get('expiry')
            if not expiry:
                for strike_data in option_chain.values():
                    if isinstance(strike_data, dict) and 'CE' in strike_data:
                        expiry = strike_data['CE'].get('expiry')
                        if expiry:
                            break
        
        if not expiry:
            return None
        
        # Extract premiums and Greeks
        short_premium = short_data.get('last_price') or short_data.get('ltp') or short_data.get('premium', 0)
        long_premium = long_data.get('last_price') or long_data.get('ltp') or long_data.get('premium', 0)
        
        # Build legs
        legs = [
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
            ),
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
            )
        ]
        
        logger.info(f"Bear Call Spread built: Short {short_strike}, Long {long_strike}")
        return legs
    
    def calculate_metrics(self, legs: List[OptionLeg]) -> SpreadMetrics:
        """Calculate Bear Call Spread metrics."""
        return SpreadBuilder.calculate_spread_metrics(legs, self.lot_size)
