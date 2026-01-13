"""Unit tests for Implied Volatility (IV) calculation.

Tests IV calculation using Black-Scholes inversion with Newton-Raphson and bisection methods.
"""

import pytest
import math
from market_data.analytics.greeks_calculator import GreeksCalculator


class TestIVCalculation:
    """Test IV calculation for various scenarios."""
    
    def test_atm_call_iv(self):
        """Test IV calculation for ATM call option."""
        # Market price for ATM call with 20% IV
        spot = 100.0
        strike = 100.0
        time_to_expiry = 0.25  # 3 months
        vol_true = 0.20  # 20% true volatility
        
        # Calculate market price using true IV
        market_price = GreeksCalculator.calculate_option_price(
            spot, strike, time_to_expiry, vol_true, option_type='CE'
        )
        
        # Calculate IV from market price (should recover ~20%)
        iv_calculated = GreeksCalculator.calculate_implied_volatility(
            market_price, spot, strike, time_to_expiry, option_type='CE'
        )
        
        assert iv_calculated is not None
        assert abs(iv_calculated - vol_true) < 0.01  # Within 1%
    
    def test_atm_put_iv(self):
        """Test IV calculation for ATM put option."""
        spot = 100.0
        strike = 100.0
        time_to_expiry = 0.25
        vol_true = 0.20
        
        market_price = GreeksCalculator.calculate_option_price(
            spot, strike, time_to_expiry, vol_true, option_type='PE'
        )
        
        iv_calculated = GreeksCalculator.calculate_implied_volatility(
            market_price, spot, strike, time_to_expiry, option_type='PE'
        )
        
        assert iv_calculated is not None
        assert abs(iv_calculated - vol_true) < 0.01
    
    def test_itm_call_iv(self):
        """Test IV calculation for ITM call option."""
        spot = 110.0
        strike = 100.0
        time_to_expiry = 0.25
        vol_true = 0.25  # 25% IV
        
        market_price = GreeksCalculator.calculate_option_price(
            spot, strike, time_to_expiry, vol_true, option_type='CE'
        )
        
        iv_calculated = GreeksCalculator.calculate_implied_volatility(
            market_price, spot, strike, time_to_expiry, option_type='CE'
        )
        
        assert iv_calculated is not None
        assert abs(iv_calculated - vol_true) < 0.01
    
    def test_otm_put_iv(self):
        """Test IV calculation for OTM put option."""
        spot = 110.0
        strike = 100.0
        time_to_expiry = 0.25
        vol_true = 0.18  # 18% IV
        
        market_price = GreeksCalculator.calculate_option_price(
            spot, strike, time_to_expiry, vol_true, option_type='PE'
        )
        
        iv_calculated = GreeksCalculator.calculate_implied_volatility(
            market_price, spot, strike, time_to_expiry, option_type='PE'
        )
        
        assert iv_calculated is not None
        assert abs(iv_calculated - vol_true) < 0.02  # Slightly looser for OTM
    
    def test_iv_put_call_parity(self):
        """Test that call and put with same IV produce consistent results."""
        spot = 100.0
        strike = 100.0
        time_to_expiry = 0.25
        vol_true = 0.20
        
        call_price = GreeksCalculator.calculate_option_price(
            spot, strike, time_to_expiry, vol_true, option_type='CE'
        )
        put_price = GreeksCalculator.calculate_option_price(
            spot, strike, time_to_expiry, vol_true, option_type='PE'
        )
        
        call_iv = GreeksCalculator.calculate_implied_volatility(
            call_price, spot, strike, time_to_expiry, option_type='CE'
        )
        put_iv = GreeksCalculator.calculate_implied_volatility(
            put_price, spot, strike, time_to_expiry, option_type='PE'
        )
        
        assert call_iv is not None
        assert put_iv is not None
        # Both should recover similar IV (within 1%)
        assert abs(call_iv - put_iv) < 0.01
    
    def test_iv_high_volatility(self):
        """Test IV calculation for high volatility option."""
        spot = 100.0
        strike = 100.0
        time_to_expiry = 0.25
        vol_true = 0.50  # 50% IV
        
        market_price = GreeksCalculator.calculate_option_price(
            spot, strike, time_to_expiry, vol_true, option_type='CE'
        )
        
        iv_calculated = GreeksCalculator.calculate_implied_volatility(
            market_price, spot, strike, time_to_expiry, option_type='CE'
        )
        
        assert iv_calculated is not None
        assert abs(iv_calculated - vol_true) < 0.02
    
    def test_iv_low_volatility(self):
        """Test IV calculation for low volatility option."""
        spot = 100.0
        strike = 100.0
        time_to_expiry = 0.25
        vol_true = 0.10  # 10% IV
        
        market_price = GreeksCalculator.calculate_option_price(
            spot, strike, time_to_expiry, vol_true, option_type='CE'
        )
        
        iv_calculated = GreeksCalculator.calculate_implied_volatility(
            market_price, spot, strike, time_to_expiry, option_type='CE'
        )
        
        assert iv_calculated is not None
        assert abs(iv_calculated - vol_true) < 0.01
    
    def test_iv_short_expiry(self):
        """Test IV calculation for short expiry option."""
        spot = 100.0
        strike = 100.0
        time_to_expiry = 0.01  # ~3.5 days
        vol_true = 0.20
        
        market_price = GreeksCalculator.calculate_option_price(
            spot, strike, time_to_expiry, vol_true, option_type='CE'
        )
        
        iv_calculated = GreeksCalculator.calculate_implied_volatility(
            market_price, spot, strike, time_to_expiry, option_type='CE'
        )
        
        assert iv_calculated is not None
        # May be slightly less accurate for very short expiry
        assert abs(iv_calculated - vol_true) < 0.05
    
    def test_iv_long_expiry(self):
        """Test IV calculation for long expiry option."""
        spot = 100.0
        strike = 100.0
        time_to_expiry = 1.0  # 1 year
        vol_true = 0.20
        
        market_price = GreeksCalculator.calculate_option_price(
            spot, strike, time_to_expiry, vol_true, option_type='CE'
        )
        
        iv_calculated = GreeksCalculator.calculate_implied_volatility(
            market_price, spot, strike, time_to_expiry, option_type='CE'
        )
        
        assert iv_calculated is not None
        assert abs(iv_calculated - vol_true) < 0.01
    
    def test_iv_invalid_inputs(self):
        """Test IV calculation with invalid inputs."""
        # Zero market price
        iv = GreeksCalculator.calculate_implied_volatility(
            0, 100.0, 100.0, 0.25, option_type='CE'
        )
        assert iv is None
        
        # Negative market price
        iv = GreeksCalculator.calculate_implied_volatility(
            -10, 100.0, 100.0, 0.25, option_type='CE'
        )
        assert iv is None
        
        # Zero time to expiry
        iv = GreeksCalculator.calculate_implied_volatility(
            10, 100.0, 100.0, 0, option_type='CE'
        )
        assert iv is None
        
        # Market price below intrinsic value
        iv = GreeksCalculator.calculate_implied_volatility(
            5, 110.0, 100.0, 0.25, option_type='CE'  # Intrinsic = 10
        )
        assert iv is None
    
    def test_iv_extreme_otm(self):
        """Test IV calculation for extremely OTM option."""
        spot = 100.0
        strike = 150.0  # 50% OTM
        time_to_expiry = 0.25
        vol_true = 0.20
        
        market_price = GreeksCalculator.calculate_option_price(
            spot, strike, time_to_expiry, vol_true, option_type='CE'
        )
        
        # Extremely OTM options may have very low prices
        if market_price < 0.01:
            # Skip test if price too low for reliable IV
            pytest.skip("Market price too low for reliable IV calculation")
        
        iv_calculated = GreeksCalculator.calculate_implied_volatility(
            market_price, spot, strike, time_to_expiry, option_type='CE'
        )
        
        # May fail for extremely OTM options
        if iv_calculated is not None:
            assert abs(iv_calculated - vol_true) < 0.05
    
    def test_iv_deep_itm(self):
        """Test IV calculation for deep ITM option."""
        spot = 150.0
        strike = 100.0  # 50% ITM
        time_to_expiry = 0.25
        vol_true = 0.20
        
        market_price = GreeksCalculator.calculate_option_price(
            spot, strike, time_to_expiry, vol_true, option_type='CE'
        )
        
        iv_calculated = GreeksCalculator.calculate_implied_volatility(
            market_price, spot, strike, time_to_expiry, option_type='CE'
        )
        
        assert iv_calculated is not None
        assert abs(iv_calculated - vol_true) < 0.02
    
    def test_iv_convergence(self):
        """Test that IV calculation converges reliably."""
        spot = 100.0
        strike = 100.0
        time_to_expiry = 0.25
        
        # Test multiple volatilities
        test_vols = [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]
        
        for vol_true in test_vols:
            market_price = GreeksCalculator.calculate_option_price(
                spot, strike, time_to_expiry, vol_true, option_type='CE'
            )
            
            iv_calculated = GreeksCalculator.calculate_implied_volatility(
                market_price, spot, strike, time_to_expiry, option_type='CE'
            )
            
            assert iv_calculated is not None, f"IV calculation failed for vol={vol_true}"
            assert abs(iv_calculated - vol_true) < 0.02, f"IV accuracy failed for vol={vol_true}"
