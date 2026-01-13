"""Base Strategy Framework for Spread-Based Options Trading.

This module provides the foundation for all spread strategies, including:
- OptionLeg dataclass for individual option positions
- SpreadMetrics dataclass for strategy performance metrics
- BaseSpreadStrategy abstract base class
- Validation methods for liquidity and spread criteria
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime, date

logger = logging.getLogger(__name__)


class OptionType(Enum):
    """Option type enumeration."""
    CALL = "CE"
    PUT = "PE"


class OrderAction(Enum):
    """Order action enumeration."""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class OptionLeg:
    """Individual option leg in a spread strategy.
    
    Attributes:
        strike: Strike price of the option
        option_type: CALL or PUT
        action: BUY or SELL
        quantity: Number of contracts (in lots)
        premium: Option premium per contract
        expiry: Expiry date (ISO format: YYYY-MM-DD)
        delta: Option delta (price sensitivity)
        gamma: Option gamma (delta sensitivity)
        theta: Option theta (time decay per day)
        vega: Option vega (volatility sensitivity per 1%)
        rho: Option rho (interest rate sensitivity per 1%)
        iv: Implied volatility (as decimal, e.g., 0.20 for 20%)
        volume: Trading volume for this option
        oi: Open interest for this option
    """
    strike: float
    option_type: OptionType
    action: OrderAction
    quantity: int
    premium: float
    expiry: str
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
    iv: Optional[float] = None
    volume: Optional[int] = None
    oi: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "strike": self.strike,
            "option_type": self.option_type.value,
            "action": self.action.value,
            "quantity": self.quantity,
            "premium": self.premium,
            "expiry": self.expiry,
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
            "iv": self.iv,
            "volume": self.volume,
            "oi": self.oi
        }


@dataclass
class SpreadMetrics:
    """Performance metrics for a spread strategy.
    
    Attributes:
        max_profit: Maximum profit potential (in currency units)
        max_loss: Maximum loss potential (in currency units)
        breakeven_points: List of breakeven price levels
        net_premium: Net premium received/paid (positive = credit, negative = debit)
        margin_required: Margin required for the strategy (in currency units)
        risk_reward_ratio: Risk-to-reward ratio (max_profit / max_loss)
        probability_of_profit: Estimated probability of profit (0.0 to 1.0)
        net_delta: Net delta of the spread
        net_gamma: Net gamma of the spread
        net_theta: Net theta of the spread (per day)
        net_vega: Net vega of the spread (per 1% IV change)
        net_rho: Net rho of the spread (per 1% rate change)
    """
    max_profit: float
    max_loss: float
    breakeven_points: List[float] = field(default_factory=list)
    net_premium: float = 0.0
    margin_required: float = 0.0
    risk_reward_ratio: float = 0.0
    probability_of_profit: float = 0.0
    net_delta: float = 0.0
    net_gamma: float = 0.0
    net_theta: float = 0.0
    net_vega: float = 0.0
    net_rho: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "max_profit": self.max_profit,
            "max_loss": self.max_loss,
            "breakeven_points": self.breakeven_points,
            "net_premium": self.net_premium,
            "margin_required": self.margin_required,
            "risk_reward_ratio": self.risk_reward_ratio,
            "probability_of_profit": self.probability_of_profit,
            "net_delta": self.net_delta,
            "net_gamma": self.net_gamma,
            "net_theta": self.net_theta,
            "net_vega": self.net_vega,
            "net_rho": self.net_rho
        }


class BaseSpreadStrategy(ABC):
    """Base class for all spread strategies.
    
    This abstract base class defines the interface and common functionality
    for all spread-based options trading strategies.
    
    Subclasses must implement:
    - build_spread(): Build the strategy legs
    - calculate_metrics(): Calculate strategy metrics
    
    Common functionality provided:
    - Liquidity validation
    - Spread validation (risk/reward, PoP, net delta)
    - Configuration management
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize base spread strategy.
        
        Args:
            config: Configuration dictionary with:
                - lot_size: Lot size for the instrument (default: 25 for Bank Nifty)
                - min_option_volume: Minimum volume requirement (default: 100)
                - min_option_oi: Minimum open interest requirement (default: 500)
                - min_risk_reward: Minimum risk/reward ratio (default: 0.3)
                - min_probability_of_profit: Minimum PoP (default: 0.50)
                - max_net_delta: Maximum net delta for neutrality (default: 0.2)
        """
        config = config or {}
        self.config = config
        self.lot_size = config.get('lot_size', 25)  # Bank Nifty default
        self.min_option_volume = config.get('min_option_volume', 100)
        self.min_option_oi = config.get('min_option_oi', 500)
        self.min_risk_reward = config.get('min_risk_reward', 0.3)
        self.min_probability_of_profit = config.get('min_probability_of_profit', 0.50)
        self.max_net_delta = config.get('max_net_delta', 0.2)
        
        logger.debug(f"{self.__class__.__name__} initialized with lot_size={self.lot_size}")
    
    @abstractmethod
    def build_spread(
        self,
        spot_price: float,
        option_chain: Dict[str, Any],
        expiry: Optional[str] = None
    ) -> Optional[List[OptionLeg]]:
        """Build spread legs based on strategy rules.
        
        Args:
            spot_price: Current spot price of the underlying
            option_chain: Options chain data (dict with strike keys and CE/PE data)
            expiry: Target expiry date (ISO format: YYYY-MM-DD), None for nearest expiry
        
        Returns:
            List of OptionLeg objects if valid spread can be built, None otherwise
        """
        pass
    
    @abstractmethod
    def calculate_metrics(self, legs: List[OptionLeg]) -> SpreadMetrics:
        """Calculate spread metrics including P&L, Greeks, and risk measures.
        
        Args:
            legs: List of OptionLeg objects forming the spread
        
        Returns:
            SpreadMetrics object with calculated metrics
        """
        pass
    
    def validate_liquidity(self, leg: OptionLeg, option_data: Dict[str, Any]) -> bool:
        """Check if option has sufficient liquidity.
        
        Args:
            leg: OptionLeg to validate
            option_data: Option chain data for this strike/type
        
        Returns:
            True if option meets liquidity requirements, False otherwise
        """
        volume = option_data.get('volume', 0) or option_data.get('ce_volume' if leg.option_type == OptionType.CALL else 'pe_volume', 0)
        oi = option_data.get('oi', 0) or option_data.get('ce_oi' if leg.option_type == OptionType.CALL else 'pe_oi', 0)
        
        # Check volume
        if volume < self.min_option_volume:
            logger.debug(f"Leg {leg.strike} {leg.option_type.value} failed volume check: {volume} < {self.min_option_volume}")
            return False
        
        # Check open interest
        if oi < self.min_option_oi:
            logger.debug(f"Leg {leg.strike} {leg.option_type.value} failed OI check: {oi} < {self.min_option_oi}")
            return False
        
        return True
    
    def validate_spread(
        self,
        legs: List[OptionLeg],
        metrics: SpreadMetrics
    ) -> bool:
        """Validate if spread meets all criteria.
        
        Args:
            legs: List of OptionLeg objects
            metrics: Calculated SpreadMetrics
        
        Returns:
            True if spread meets all criteria, False otherwise
        """
        # Check risk/reward ratio
        if metrics.max_loss > 0 and metrics.risk_reward_ratio < self.min_risk_reward:
            logger.debug(f"Spread failed R:R check: {metrics.risk_reward_ratio} < {self.min_risk_reward}")
            return False
        
        # Check probability of profit
        if metrics.probability_of_profit < self.min_probability_of_profit:
            logger.debug(f"Spread failed PoP check: {metrics.probability_of_profit} < {self.min_probability_of_profit}")
            return False
        
        # Check net delta for near-neutrality (for strategies that require it)
        if abs(metrics.net_delta) > self.max_net_delta:
            logger.debug(f"Spread failed delta neutrality check: |{metrics.net_delta}| > {self.max_net_delta}")
            return False
        
        return True
    
    def find_strike(
        self,
        target_price: float,
        option_chain: Dict[str, Any]
    ) -> Optional[float]:
        """Find closest strike to target price.
        
        Args:
            target_price: Target strike price
            option_chain: Options chain data (dict with numeric strike keys)
        
        Returns:
            Closest strike price, or None if chain is empty
        """
        # Extract strike prices from chain keys
        strikes = []
        for key in option_chain.keys():
            try:
                strike = float(key)
                strikes.append(strike)
            except (ValueError, TypeError):
                continue
        
        if not strikes:
            return None
        
        # Find closest strike
        closest_strike = min(strikes, key=lambda x: abs(x - target_price))
        return closest_strike
    
    def get_option_data(
        self,
        strike: float,
        option_type: OptionType,
        option_chain: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get option data for a specific strike and type.
        
        Args:
            strike: Strike price (float, e.g., 44100.0)
            option_type: CALL or PUT
            option_chain: Options chain data (with string keys like "44100")
        
        Returns:
            Option data dictionary or None if not found
        """
        # Convert strike to string, handling both int and float formats
        # Try both "44100.0" and "44100" formats
        strike_key_int = str(int(strike))
        strike_key_float = str(strike)
        
        # Try integer format first (most common in option chains)
        strike_key = strike_key_int if strike_key_int in option_chain else strike_key_float
        if strike_key not in option_chain:
            # If exact match not found, try to find any key that matches when converted to float
            for key in option_chain.keys():
                try:
                    if abs(float(key) - strike) < 0.01:  # Close enough match
                        strike_key = key
                        break
                except (ValueError, TypeError):
                    continue
            else:
                return None
        
        strike_data = option_chain[strike_key]
        option_key = 'CE' if option_type == OptionType.CALL else 'PE'
        
        option_data = strike_data.get(option_key)
        if not option_data:
            return None
        
        return option_data
