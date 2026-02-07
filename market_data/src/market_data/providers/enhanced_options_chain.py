"""Enhanced Options Chain Provider with IV, Greeks, validation, and normalization.

This module extends the basic options chain provider to include:
- Implied volatility (IV) calculation placeholders
- Greeks fields (delta, gamma, theta, vega)
- Data validation
- Data normalization
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, date
import pandas as pd

from ..adapters.zerodha_options_chain import ZerodhaOptionsChainAdapter
from ..contracts import OptionsData

logger = logging.getLogger(__name__)


class EnhancedOptionsChainAdapter(ZerodhaOptionsChainAdapter):
    """Enhanced options chain adapter with IV, Greeks, validation, and normalization.
    
    Extends ZerodhaOptionsChainAdapter to add:
    - Implied volatility fields (ce_iv, pe_iv)
    - Greeks fields (ce_delta, pe_delta, ce_gamma, pe_gamma, etc.)
    - Data validation
    - Data normalization
    """
    
    def __init__(
        self, 
        kite=None, 
        instrument_symbol: str = "BANKNIFTY", 
        use_live_quotes: bool = False,
        enable_greeks: bool = True
    ):
        """Initialize enhanced options chain adapter.
        
        Args:
            kite: KiteConnect instance
            instrument_symbol: Underlying symbol (e.g., "BANKNIFTY", "NIFTY")
            use_live_quotes: If True, use kite.quote() for real-time bid/ask
            enable_greeks: If True, include Greeks fields (requires Greeks calculator)
        """
        super().__init__(kite, instrument_symbol, use_live_quotes)
        self.enable_greeks = enable_greeks
        self._greeks_calculator = None
        
        if self.enable_greeks:
            try:
                # Lazy import to avoid circular dependencies
                from ..analytics.greeks_calculator import GreeksCalculator
                self._greeks_calculator = GreeksCalculator()
                logger.info("Greeks calculator initialized for enhanced options chain")
            except ImportError:
                logger.warning("Greeks calculator not available - Greeks will not be calculated")
                self._greeks_calculator = None
    
    def _calculate_implied_volatility(
        self,
        option_data: Dict[str, Any],
        underlying_price: float,
        strike: float,
        time_to_expiry: float,
        option_type: str = "CE"
    ) -> Optional[float]:
        """Calculate implied volatility for an option using Black-Scholes inversion.
        
        Uses Newton-Raphson method with bisection fallback for robust IV calculation.
        
        Args:
            option_data: Option data dict (must contain 'last_price' or 'ltp')
            underlying_price: Current underlying price
            strike: Option strike price
            time_to_expiry: Time to expiry in years
            option_type: 'CE' for Call, 'PE' for Put
        
        Returns:
            Implied volatility as percentage (e.g., 20.5 for 20.5%) or None if calculation fails
        """
        # Get market price (prefer last_price, fallback to ltp)
        market_price = option_data.get('last_price') or option_data.get('ltp') or option_data.get('price')
        
        if not market_price or market_price <= 0:
            logger.debug(f"No valid market price for IV calculation: {option_data.get('tradingsymbol', 'unknown')}")
            return None
        
        # Use GreeksCalculator to calculate IV
        if not self._greeks_calculator:
            logger.debug("GreeksCalculator not available for IV calculation")
            return None
        
        try:
            # Calculate IV (returns as decimal, e.g., 0.20 for 20%)
            iv_decimal = self._greeks_calculator.calculate_implied_volatility(
                market_price=market_price,
                spot_price=underlying_price,
                strike=strike,
                time_to_expiry=time_to_expiry,
                risk_free_rate=0.07,  # 7% for India
                option_type=option_type,
                initial_guess=0.20  # 20% initial guess
            )
            
            if iv_decimal is None:
                logger.debug(f"IV calculation failed for {option_data.get('tradingsymbol', 'unknown')}")
                return None
            
            # Convert to percentage (e.g., 0.20 -> 20.0)
            iv_percentage = iv_decimal * 100.0
            return iv_percentage
            
        except Exception as e:
            logger.warning(f"Error calculating IV for {option_data.get('tradingsymbol', 'unknown')}: {e}")
            return None
    
    def _calculate_greeks(
        self,
        option_data: Dict[str, Any],
        underlying_price: float,
        strike: float,
        time_to_expiry: float,
        implied_vol: Optional[float],
        option_type: str  # "CE" or "PE"
    ) -> Dict[str, Optional[float]]:
        """Calculate Greeks for an option.
        
        Args:
            option_data: Option data dict
            underlying_price: Current underlying price
            strike: Option strike price
            time_to_expiry: Time to expiry in years
            implied_vol: Implied volatility (if available)
            option_type: "CE" or "PE"
        
        Returns:
            Dictionary with delta, gamma, theta, vega, rho
        """
        if not self._greeks_calculator or not implied_vol:
            return {
                "delta": None,
                "gamma": None,
                "theta": None,
                "vega": None,
                "rho": None
            }
        
        try:
            greeks = self._greeks_calculator.calculate_greeks(
                spot_price=underlying_price,
                strike=strike,
                time_to_expiry=time_to_expiry,
                volatility=implied_vol / 100.0,  # Convert percentage to decimal
                risk_free_rate=0.07,  # 7% for India
                option_type=option_type
            )
            return greeks
        except Exception as e:
            logger.debug(f"Failed to calculate Greeks: {e}")
            return {
                "delta": None,
                "gamma": None,
                "theta": None,
                "vega": None,
                "rho": None
            }
    
    def _validate_option_data(self, option_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate option data.
        
        Args:
            option_data: Option data dict to validate
        
        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        required_fields = ["tradingsymbol", "instrument_token", "strike", "expiry"]
        
        for field in required_fields:
            if field not in option_data:
                return False, f"Missing required field: {field}"
        
        # Validate numeric fields
        try:
            strike = float(option_data.get("strike", 0))
            if strike <= 0:
                return False, f"Invalid strike price: {strike}"
        except (ValueError, TypeError):
            return False, f"Invalid strike price: {option_data.get('strike')}"
        
        # Validate expiry
        expiry = option_data.get("expiry")
        if not expiry:
            return False, "Missing expiry date"
        
        return True, None
    
    def _normalize_option_data(self, option_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize option data to standard format.
        
        Args:
            option_data: Raw option data dict
        
        Returns:
            Normalized option data dict
        """
        normalized = {}
        
        # Standard fields
        normalized["tradingsymbol"] = str(option_data.get("tradingsymbol", ""))
        normalized["instrument_token"] = int(option_data.get("instrument_token", 0))
        normalized["strike"] = float(option_data.get("strike", 0))
        normalized["expiry"] = option_data.get("expiry")
        normalized["option_type"] = option_data.get("instrument_type", "CE")
        
        # Price fields
        normalized["last_price"] = float(option_data.get("last_price", 0))
        normalized["bid"] = float(option_data.get("bid", 0))
        normalized["ask"] = float(option_data.get("ask", 0))
        
        # Volume and OI
        normalized["volume"] = int(option_data.get("volume", 0))
        normalized["oi"] = int(option_data.get("oi", 0))
        
        # IV and Greeks (will be populated by _enhance_option_data)
        normalized["iv"] = option_data.get("iv")
        normalized["delta"] = option_data.get("delta")
        normalized["gamma"] = option_data.get("gamma")
        normalized["theta"] = option_data.get("theta")
        normalized["vega"] = option_data.get("vega")
        
        # Timestamp
        normalized["timestamp"] = option_data.get("timestamp", datetime.now().isoformat())
        
        return normalized
    
    def _enhance_option_data(
        self,
        option_data: Dict[str, Any],
        underlying_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Enhance option data with IV and Greeks.
        
        Args:
            option_data: Normalized option data
            underlying_price: Current underlying price (optional)
        
        Returns:
            Enhanced option data with IV and Greeks
        """
        if not underlying_price:
            # Try to get from option data or use last_price as proxy
            underlying_price = option_data.get("underlying_price")
            if not underlying_price:
                # Cannot calculate without underlying price
                return option_data
        
        strike = option_data.get("strike", 0)
        expiry = option_data.get("expiry")
        option_type = option_data.get("option_type", "CE")
        
        # Calculate time to expiry
        if expiry:
            if isinstance(expiry, str):
                from dateutil import parser
                expiry_date = parser.parse(expiry).date()
            elif isinstance(expiry, date):
                expiry_date = expiry
            else:
                expiry_date = expiry
            
            time_to_expiry = (expiry_date - date.today()).days / 365.0
            if time_to_expiry <= 0:
                time_to_expiry = 0.001  # Minimum 1 day
            
            # Calculate IV using Black-Scholes inversion
            iv = self._calculate_implied_volatility(
                option_data, underlying_price, strike, time_to_expiry, option_type
            )
            option_data["iv"] = iv
            
            # Calculate Greeks if IV available
            if iv is not None:
                greeks = self._calculate_greeks(
                    option_data, underlying_price, strike, time_to_expiry, iv, option_type
                )
                option_data.update(greeks)
        
        return option_data
    
    def _organize_by_strikes(
        self,
        options_df: pd.DataFrame,
        price_data: Dict[str, Dict],
        underlying_price: Optional[float] = None
    ) -> List[Dict]:
        """Organize options data by strike prices with enhanced fields.
        
        Overrides parent method to add IV and Greeks.
        """
        strikes_data = []
        # If underlying price provided by caller, use it. Otherwise, attempt to fetch from kite.
        if underlying_price is None:
            try:
                if self.kite:
                    # Try to get futures price first
                    month_names = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                                  'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
                    now = datetime.now()
                    month_str = month_names[now.month - 1]
                    year_str = str(now.year)[-2:]
                    fut_symbol = f"{self.instrument_symbol}{year_str}{month_str}FUT"
                    
                    try:
                        fut_quote = self.kite.quote([f"NFO:{fut_symbol}"])
                        if fut_quote:
                            fut_data = list(fut_quote.values())[0]
                            if hasattr(fut_data, 'to_dict'):
                                fut_data = fut_data.to_dict()
                            underlying_price = fut_data.get('last_price') or fut_data.get('ohlc', {}).get('close')
                    except Exception:
                        # Try underlying spot
                        try:
                            spot_quote = self.kite.quote([f"NSE:{self.instrument_symbol}"])
                            if spot_quote:
                                spot_data = list(spot_quote.values())[0]
                                if hasattr(spot_data, 'to_dict'):
                                    spot_data = spot_data.to_dict()
                                underlying_price = spot_data.get('last_price') or spot_data.get('ohlc', {}).get('close')
                        except Exception:
                            pass
            except Exception:
                pass
        
        # Group by strike
        for strike in sorted(options_df['strike'].unique()):
            strike_options = options_df[options_df['strike'] == strike]
            
            strike_data = {
                "strike": int(strike),
                "CE": None,
                "PE": None,
                # Enhanced fields
                "ce_ltp": None,
                "pe_ltp": None,
                "ce_volume": None,
                "pe_volume": None,
                "ce_oi": None,
                "pe_oi": None,
                "ce_iv": None,
                "pe_iv": None,
                "ce_delta": None,
                "pe_delta": None,
                "ce_gamma": None,
                "pe_gamma": None,
                "ce_theta": None,
                "pe_theta": None,
                "ce_vega": None,
                "pe_vega": None,
            }
            
            for _, option in strike_options.iterrows():
                token = str(option['instrument_token'])
                option_type = option['instrument_type']
                
                if token in price_data:
                    price_info = price_data[token]
                    
                    # Build option data
                    option_data = {
                        "tradingsymbol": option['tradingsymbol'],
                        "instrument_token": option['instrument_token'],
                        "expiry": option['expiry'],
                        "strike": int(strike),
                        "option_type": option_type,
                        "last_price": price_info.get('last_price', 0),
                        "volume": price_info.get('volume', 0),
                        "oi": price_info.get('oi', 0),
                        "bid": price_info.get('bid', 0),
                        "ask": price_info.get('ask', 0),
                        "timestamp": price_info.get('timestamp', datetime.now().isoformat()),
                        "underlying_price": underlying_price
                    }
                    
                    # Validate data
                    is_valid, error = self._validate_option_data(option_data)
                    if not is_valid:
                        logger.warning(f"Invalid option data for {option_data['tradingsymbol']}: {error}")
                        continue
                    
                    # Normalize data
                    option_data = self._normalize_option_data(option_data)
                    
                    # Enhance with IV and Greeks
                    option_data = self._enhance_option_data(option_data, underlying_price)
                    
                    # Store in strike data
                    strike_data[option_type] = option_data
                    
                    # Also populate flat fields for easy access (engine module expects these)
                    if option_type == "CE":
                        strike_data["ce_ltp"] = option_data.get("last_price")
                        strike_data["ce_volume"] = option_data.get("volume")
                        strike_data["ce_oi"] = option_data.get("oi")
                        strike_data["ce_iv"] = option_data.get("iv")
                        strike_data["ce_delta"] = option_data.get("delta")
                        strike_data["ce_gamma"] = option_data.get("gamma")
                        strike_data["ce_theta"] = option_data.get("theta")
                        strike_data["ce_vega"] = option_data.get("vega")
                    elif option_type == "PE":
                        strike_data["pe_ltp"] = option_data.get("last_price")
                        strike_data["pe_volume"] = option_data.get("volume")
                        strike_data["pe_oi"] = option_data.get("oi")
                        strike_data["pe_iv"] = option_data.get("iv")
                        strike_data["pe_delta"] = option_data.get("delta")
                        strike_data["pe_gamma"] = option_data.get("gamma")
                        strike_data["pe_theta"] = option_data.get("theta")
                        strike_data["pe_vega"] = option_data.get("vega")
            
            # Only include strikes that have at least one option
            if strike_data["CE"] or strike_data["PE"]:
                strikes_data.append(strike_data)
        
        return strikes_data
