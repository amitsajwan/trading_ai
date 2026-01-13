"""Iron Condor Strategy Implementation.

Iron Condor is a neutral options strategy that profits from low volatility:
- Sell OTM call spread (higher strikes)
- Sell OTM put spread (lower strikes)
- Maximum profit: Net credit received
- Maximum loss: Spread width minus credit
- Best for: Ranging markets with low volatility
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


class IronCondorStrategy(BaseSpreadStrategy):
    """Iron Condor strategy implementation.
    
    Iron Condor: Sell OTM call spread + Sell OTM put spread
    - Best for: Range-bound markets with low volatility
    - Risk: Limited to spread width - net credit
    - Reward: Net credit received
    - Greeks: Nearly delta-neutral, negative theta (time decay works in favor)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Iron Condor strategy.
        
        Args:
            config: Configuration dictionary with:
                - lot_size: Lot size (default: 25)
                - otm_percentage: OTM percentage for short strikes (default: 0.02 = 2%)
                - spread_width: Width of each spread in percentage (default: 0.01 = 1%)
                - All base strategy config options
        """
        super().__init__(config)
        
        self.otm_percentage = config.get('otm_percentage', 0.02) if config else 0.02  # 2% OTM
        self.spread_width = config.get('spread_width', 0.01) if config else 0.01  # 1% width
        
        logger.debug(f"IronCondorStrategy initialized: OTM={self.otm_percentage}, width={self.spread_width}")
    
    def build_spread(
        self,
        spot_price: float,
        option_chain: Dict[str, Any],
        expiry: Optional[str] = None
    ) -> Optional[List[OptionLeg]]:
        """Build Iron Condor spread.
        
        Iron Condor structure:
        - Sell OTM put (lower strike)
        - Buy OTM put (even lower strike)
        - Sell OTM call (higher strike)
        - Buy OTM call (even higher strike)
        
        Args:
            spot_price: Current spot price
            option_chain: Options chain data (dict with strike keys)
            expiry: Target expiry date (uses nearest if None)
        
        Returns:
            List of 4 OptionLeg objects if valid spread can be built, None otherwise
        """
        if not option_chain:
            logger.warning("Empty option chain, cannot build Iron Condor")
            return None
        
        # Calculate strikes
        # Put spread: sell at (1 - otm_percentage), buy at (1 - otm_percentage - spread_width)
        # Call spread: sell at (1 + otm_percentage), buy at (1 + otm_percentage + spread_width)
        
        put_short_strike_target = spot_price * (1 - self.otm_percentage)
        put_long_strike_target = spot_price * (1 - self.otm_percentage - self.spread_width)
        call_short_strike_target = spot_price * (1 + self.otm_percentage)
        call_long_strike_target = spot_price * (1 + self.otm_percentage + self.spread_width)
        
        # Find closest strikes
        put_short_strike = self.find_strike(put_short_strike_target, option_chain)
        put_long_strike = self.find_strike(put_long_strike_target, option_chain)
        call_short_strike = self.find_strike(call_short_strike_target, option_chain)
        call_long_strike = self.find_strike(call_long_strike_target, option_chain)
        
        if not all([put_short_strike, put_long_strike, call_short_strike, call_long_strike]):
            logger.warning("Could not find all strikes for Iron Condor")
            return None
        
        # Ensure strikes are ordered correctly
        if not (put_long_strike < put_short_strike < call_short_strike < call_long_strike):
            logger.warning(f"Invalid strike ordering: {put_long_strike}, {put_short_strike}, {call_short_strike}, {call_long_strike}")
            return None
        
        # Get option data
        put_short_data = self.get_option_data(put_short_strike, OptionType.PUT, option_chain)
        put_long_data = self.get_option_data(put_long_strike, OptionType.PUT, option_chain)
        call_short_data = self.get_option_data(call_short_strike, OptionType.CALL, option_chain)
        call_long_data = self.get_option_data(call_long_strike, OptionType.CALL, option_chain)
        
        if not all([put_short_data, put_long_data, call_short_data, call_long_data]):
            logger.warning("Could not get option data for all strikes")
            return None
        
        # Get expiry (use first available)
        if expiry is None:
            # Extract expiry from option data if available
            expiry = put_short_data.get('expiry') or call_short_data.get('expiry')
            if not expiry:
                # Try to get from chain structure
                for strike_data in option_chain.values():
                    if isinstance(strike_data, dict):
                        if 'CE' in strike_data and strike_data['CE']:
                            expiry = strike_data['CE'].get('expiry')
                        elif 'PE' in strike_data and strike_data['PE']:
                            expiry = strike_data['PE'].get('expiry')
                        if expiry:
                            break
        
        if not expiry:
            logger.warning("Could not determine expiry for Iron Condor")
            return None
        
        # Validate liquidity
        legs_to_validate = [
            (OptionLeg(put_short_strike, OptionType.PUT, OrderAction.SELL, 1, 0, expiry), put_short_data),
            (OptionLeg(put_long_strike, OptionType.PUT, OrderAction.BUY, 1, 0, expiry), put_long_data),
            (OptionLeg(call_short_strike, OptionType.CALL, OrderAction.SELL, 1, 0, expiry), call_short_data),
            (OptionLeg(call_long_strike, OptionType.CALL, OrderAction.BUY, 1, 0, expiry), call_long_data),
        ]
        
        for leg, data in legs_to_validate:
            if not self.validate_liquidity(leg, data):
                logger.warning(f"Liquidity check failed for {leg.strike} {leg.option_type.value}")
                return None
        
        # Extract premiums
        put_short_premium = put_short_data.get('last_price') or put_short_data.get('ltp') or put_short_data.get('premium', 0)
        put_long_premium = put_long_data.get('last_price') or put_long_data.get('ltp') or put_long_data.get('premium', 0)
        call_short_premium = call_short_data.get('last_price') or call_short_data.get('ltp') or call_short_data.get('premium', 0)
        call_long_premium = call_long_data.get('last_price') or call_long_data.get('ltp') or call_long_data.get('premium', 0)
        
        # Extract Greeks if available
        put_short_delta = put_short_data.get('delta')
        put_long_delta = put_long_data.get('delta')
        call_short_delta = call_short_data.get('delta')
        call_long_delta = call_long_data.get('delta')
        
        put_short_gamma = put_short_data.get('gamma')
        put_long_gamma = put_long_data.get('gamma')
        call_short_gamma = call_short_data.get('gamma')
        call_long_gamma = call_long_data.get('gamma')
        
        put_short_theta = put_short_data.get('theta')
        put_long_theta = put_long_data.get('theta')
        call_short_theta = call_short_data.get('theta')
        call_long_theta = call_long_data.get('theta')
        
        put_short_vega = put_short_data.get('vega')
        put_long_vega = put_long_data.get('vega')
        call_short_vega = call_short_data.get('vega')
        call_long_vega = call_long_data.get('vega')
        
        put_short_iv = put_short_data.get('iv') or put_short_data.get('implied_volatility')
        put_long_iv = put_long_data.get('iv') or put_long_data.get('implied_volatility')
        call_short_iv = call_short_data.get('iv') or call_short_data.get('implied_volatility')
        call_long_iv = call_long_data.get('iv') or call_long_data.get('implied_volatility')
        
        # Build legs
        legs = [
            # Put spread (sell higher strike, buy lower strike)
            OptionLeg(
                strike=put_short_strike,
                option_type=OptionType.PUT,
                action=OrderAction.SELL,
                quantity=1,
                premium=put_short_premium,
                expiry=expiry,
                delta=put_short_delta,
                gamma=put_short_gamma,
                theta=put_short_theta,
                vega=put_short_vega,
                iv=put_short_iv,
                volume=put_short_data.get('volume'),
                oi=put_short_data.get('oi')
            ),
            OptionLeg(
                strike=put_long_strike,
                option_type=OptionType.PUT,
                action=OrderAction.BUY,
                quantity=1,
                premium=put_long_premium,
                expiry=expiry,
                delta=put_long_delta,
                gamma=put_long_gamma,
                theta=put_long_theta,
                vega=put_long_vega,
                iv=put_long_iv,
                volume=put_long_data.get('volume'),
                oi=put_long_data.get('oi')
            ),
            # Call spread (sell lower strike, buy higher strike)
            OptionLeg(
                strike=call_short_strike,
                option_type=OptionType.CALL,
                action=OrderAction.SELL,
                quantity=1,
                premium=call_short_premium,
                expiry=expiry,
                delta=call_short_delta,
                gamma=call_short_gamma,
                theta=call_short_theta,
                vega=call_short_vega,
                iv=call_short_iv,
                volume=call_short_data.get('volume'),
                oi=call_short_data.get('oi')
            ),
            OptionLeg(
                strike=call_long_strike,
                option_type=OptionType.CALL,
                action=OrderAction.BUY,
                quantity=1,
                premium=call_long_premium,
                expiry=expiry,
                delta=call_long_delta,
                gamma=call_long_gamma,
                theta=call_long_theta,
                vega=call_long_vega,
                iv=call_long_iv,
                volume=call_long_data.get('volume'),
                oi=call_long_data.get('oi')
            )
        ]
        
        logger.info(f"Iron Condor built: Puts {put_long_strike}/{put_short_strike}, Calls {call_short_strike}/{call_long_strike}")
        return legs
    
    def calculate_metrics(self, legs: List[OptionLeg]) -> SpreadMetrics:
        """Calculate Iron Condor metrics.
        
        For Iron Condor:
        - Max profit = Net credit received
        - Max loss = (Wider spread width) - net credit
        - Breakevens: Short put strike - credit, Short call strike + credit
        
        Args:
            legs: List of 4 OptionLeg objects (put spread + call spread)
        
        Returns:
            SpreadMetrics object
        """
        # Use spread builder for base calculations
        metrics = SpreadBuilder.calculate_spread_metrics(legs, self.lot_size)
        
        # Override for Iron Condor specific logic
        if len(legs) == 4:
            # Separate puts and calls
            puts = [leg for leg in legs if leg.option_type == OptionType.PUT]
            calls = [leg for leg in legs if leg.option_type == OptionType.CALL]
            
            if len(puts) == 2 and len(calls) == 2:
                # Get short strikes
                put_short = [leg for leg in puts if leg.action == OrderAction.SELL][0]
                call_short = [leg for leg in calls if leg.action == OrderAction.SELL][0]
                
                # Get long strikes
                put_long = [leg for leg in puts if leg.action == OrderAction.BUY][0]
                call_long = [leg for leg in calls if leg.action == OrderAction.BUY][0]
                
                # Calculate net premium
                net_premium = (
                    put_short.premium * put_short.quantity -
                    put_long.premium * put_long.quantity +
                    call_short.premium * call_short.quantity -
                    call_long.premium * call_long.quantity
                )
                
                # Calculate spread widths
                put_spread_width = put_short.strike - put_long.strike
                call_spread_width = call_long.strike - call_short.strike
                max_spread_width = max(put_spread_width, call_spread_width)
                
                # Max profit = net credit
                metrics.max_profit = net_premium * self.lot_size
                
                # Max loss = max spread width - net credit
                metrics.max_loss = (max_spread_width * self.lot_size) - metrics.max_profit
                
                # Breakevens
                metrics.breakeven_points = [
                    put_short.strike - net_premium,
                    call_short.strike + net_premium
                ]
                
                # Risk/reward ratio
                if metrics.max_loss > 0:
                    metrics.risk_reward_ratio = metrics.max_profit / metrics.max_loss
        
        return metrics
