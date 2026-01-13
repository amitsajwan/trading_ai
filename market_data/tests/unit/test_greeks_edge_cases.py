"""Edge case tests for GreeksCalculator."""

import pytest
import math
from market_data.analytics.greeks_calculator import GreeksCalculator


class TestGreeksEdgeCases:
    """Edge case tests for GreeksCalculator."""
    
    def test_very_short_expiry(self):
        """Test with very short time to expiry (1 day)."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=100.0,
            strike=100.0,
            time_to_expiry=1.0 / 365.0,  # 1 day
            volatility=0.20,
            option_type='CE'
        )
        
        # Should still calculate (may have high gamma)
        assert math.isfinite(greeks['delta'])
        assert math.isfinite(greeks['gamma'])
    
    def test_very_long_expiry(self):
        """Test with very long time to expiry (5 years)."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=100.0,
            strike=100.0,
            time_to_expiry=5.0,
            volatility=0.20,
            option_type='CE'
        )
        
        # Should calculate without error
        assert math.isfinite(greeks['delta'])
        assert greeks['delta'] > 0
    
    def test_zero_volatility(self):
        """Test with zero volatility."""
        spot = 100.0
        strike = 100.0
        
        # Should handle gracefully
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=spot,
            strike=strike,
            time_to_expiry=0.25,
            volatility=0.0,
            option_type='CE'
        )
        
        # Delta should be 0 or 1 based on moneyness
        assert 0.0 <= greeks['delta'] <= 1.0
    
    def test_very_high_volatility(self):
        """Test with very high volatility (100%)."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=100.0,
            strike=100.0,
            time_to_expiry=0.25,
            volatility=1.0,  # 100%
            option_type='CE'
        )
        
        # Should calculate (high vega expected)
        assert math.isfinite(greeks['vega'])
        assert greeks['vega'] > 0
    
    def test_deep_itm_call(self):
        """Test deep ITM call (spot >> strike)."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=150.0,
            strike=100.0,
            time_to_expiry=0.25,
            volatility=0.20,
            option_type='CE'
        )
        
        # Deep ITM should have delta close to 1
        assert greeks['delta'] > 0.9
    
    def test_deep_otm_call(self):
        """Test deep OTM call (spot << strike)."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=50.0,
            strike=100.0,
            time_to_expiry=0.25,
            volatility=0.20,
            option_type='CE'
        )
        
        # Deep OTM should have delta close to 0
        assert greeks['delta'] < 0.1
    
    def test_deep_itm_put(self):
        """Test deep ITM put (spot << strike)."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=50.0,
            strike=100.0,
            time_to_expiry=0.25,
            volatility=0.20,
            option_type='PE'
        )
        
        # Deep ITM put should have delta close to -1
        assert greeks['delta'] < -0.9
    
    def test_deep_otm_put(self):
        """Test deep OTM put (spot >> strike)."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=150.0,
            strike=100.0,
            time_to_expiry=0.25,
            volatility=0.20,
            option_type='PE'
        )
        
        # Deep OTM put should have delta close to 0
        assert abs(greeks['delta']) < 0.1
    
    def test_extreme_strike_price_ratio(self):
        """Test with extreme strike/spot ratio."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=100.0,
            strike=10000.0,  # 100x spot
            time_to_expiry=0.25,
            volatility=0.20,
            option_type='CE'
        )
        
        # Should handle without overflow
        assert math.isfinite(greeks['delta'])
    
    def test_very_small_spot_price(self):
        """Test with very small spot price."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=1.0,
            strike=1.0,
            time_to_expiry=0.25,
            volatility=0.20,
            option_type='CE'
        )
        
        # Should calculate
        assert math.isfinite(greeks['delta'])
    
    def test_very_large_spot_price(self):
        """Test with very large spot price."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=100000.0,
            strike=100000.0,
            time_to_expiry=0.25,
            volatility=0.20,
            option_type='CE'
        )
        
        # Should calculate
        assert math.isfinite(greeks['delta'])
    
    def test_gamma_maximum_at_atm(self):
        """Test that gamma is maximum at-the-money."""
        spot = 100.0
        
        # ATM
        atm_greeks = GreeksCalculator.calculate_greeks(
            spot, 100.0, 0.25, 0.20, option_type='CE'
        )
        
        # ITM
        itm_greeks = GreeksCalculator.calculate_greeks(
            spot, 90.0, 0.25, 0.20, option_type='CE'
        )
        
        # OTM
        otm_greeks = GreeksCalculator.calculate_greeks(
            spot, 110.0, 0.25, 0.20, option_type='CE'
        )
        
        # ATM should have highest gamma
        assert atm_greeks['gamma'] > itm_greeks['gamma']
        assert atm_greeks['gamma'] > otm_greeks['gamma']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
