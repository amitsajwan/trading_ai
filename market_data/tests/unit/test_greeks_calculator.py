"""Unit tests for GreeksCalculator."""

import pytest
import math
from market_data.analytics.greeks_calculator import GreeksCalculator


class TestGreeksCalculator:
    """Tests for GreeksCalculator."""
    
    def test_calculate_greeks_call_option(self):
        """Test Greeks calculation for call option."""
        spot = 100.0
        strike = 100.0
        time_to_expiry = 0.25  # 3 months
        volatility = 0.20  # 20%
        
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=spot,
            strike=strike,
            time_to_expiry=time_to_expiry,
            volatility=volatility,
            option_type='CE'
        )
        
        # Call option at-the-money should have delta around 0.5
        assert 0.4 < greeks['delta'] < 0.6
        
        # All Greeks should be present
        assert 'delta' in greeks
        assert 'gamma' in greeks
        assert 'theta' in greeks
        assert 'vega' in greeks
        assert 'rho' in greeks
        
        # Values should be finite
        assert math.isfinite(greeks['delta'])
        assert math.isfinite(greeks['gamma'])
        assert math.isfinite(greeks['theta'])
        assert math.isfinite(greeks['vega'])
        assert math.isfinite(greeks['rho'])
    
    def test_calculate_greeks_put_option(self):
        """Test Greeks calculation for put option."""
        spot = 100.0
        strike = 100.0
        time_to_expiry = 0.25
        volatility = 0.20
        
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=spot,
            strike=strike,
            time_to_expiry=time_to_expiry,
            volatility=volatility,
            option_type='PE'
        )
        
        # Put option at-the-money should have delta around -0.5
        assert -0.6 < greeks['delta'] < -0.4
        
        # Gamma should be positive (same for calls and puts)
        assert greeks['gamma'] > 0
    
    def test_call_put_delta_parity(self):
        """Test call-put delta parity: call_delta - put_delta = 1."""
        spot = 100.0
        strike = 105.0
        time_to_expiry = 0.25
        volatility = 0.20
        
        call_greeks = GreeksCalculator.calculate_greeks(
            spot, strike, time_to_expiry, volatility, option_type='CE'
        )
        
        put_greeks = GreeksCalculator.calculate_greeks(
            spot, strike, time_to_expiry, volatility, option_type='PE'
        )
        
        # Call delta - Put delta should be approximately 1
        delta_diff = call_greeks['delta'] - put_greeks['delta']
        assert abs(delta_diff - 1.0) < 0.01
    
    def test_gamma_same_for_calls_and_puts(self):
        """Test that gamma is the same for calls and puts."""
        spot = 100.0
        strike = 100.0
        time_to_expiry = 0.25
        volatility = 0.20
        
        call_greeks = GreeksCalculator.calculate_greeks(
            spot, strike, time_to_expiry, volatility, option_type='CE'
        )
        
        put_greeks = GreeksCalculator.calculate_greeks(
            spot, strike, time_to_expiry, volatility, option_type='PE'
        )
        
        assert abs(call_greeks['gamma'] - put_greeks['gamma']) < 0.0001
    
    def test_vega_same_for_calls_and_puts(self):
        """Test that vega is the same for calls and puts."""
        spot = 100.0
        strike = 100.0
        time_to_expiry = 0.25
        volatility = 0.20
        
        call_greeks = GreeksCalculator.calculate_greeks(
            spot, strike, time_to_expiry, volatility, option_type='CE'
        )
        
        put_greeks = GreeksCalculator.calculate_greeks(
            spot, strike, time_to_expiry, volatility, option_type='PE'
        )
        
        assert abs(call_greeks['vega'] - put_greeks['vega']) < 0.0001
    
    def test_in_the_money_call_delta(self):
        """Test ITM call has high delta."""
        spot = 110.0
        strike = 100.0
        time_to_expiry = 0.25
        volatility = 0.20
        
        greeks = GreeksCalculator.calculate_greeks(
            spot, strike, time_to_expiry, volatility, option_type='CE'
        )
        
        # ITM call should have delta > 0.7
        assert greeks['delta'] > 0.7
    
    def test_out_of_the_money_call_delta(self):
        """Test OTM call has low delta."""
        spot = 90.0
        strike = 100.0
        time_to_expiry = 0.25
        volatility = 0.20
        
        greeks = GreeksCalculator.calculate_greeks(
            spot, strike, time_to_expiry, volatility, option_type='CE'
        )
        
        # OTM call should have delta < 0.3
        assert greeks['delta'] < 0.3
    
    def test_theta_negative(self):
        """Test that theta (time decay) is negative."""
        spot = 100.0
        strike = 100.0
        time_to_expiry = 0.25
        volatility = 0.20
        
        call_greeks = GreeksCalculator.calculate_greeks(
            spot, strike, time_to_expiry, volatility, option_type='CE'
        )
        
        # Theta should be negative (option loses value over time)
        assert call_greeks['theta'] < 0
    
    def test_zero_time_to_expiry(self):
        """Test handling of zero time to expiry."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=100.0,
            strike=100.0,
            time_to_expiry=0.0,
            volatility=0.20,
            option_type='CE'
        )
        
        # Should return zeros without error
        assert greeks['delta'] == 0.0
        assert greeks['gamma'] == 0.0
        assert greeks['theta'] == 0.0
    
    def test_negative_time_to_expiry(self):
        """Test handling of negative time to expiry."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=100.0,
            strike=100.0,
            time_to_expiry=-0.1,
            volatility=0.20,
            option_type='CE'
        )
        
        # Should return zeros without error
        assert greeks['delta'] == 0.0
    
    def test_calculate_delta_only(self):
        """Test calculate_delta convenience method."""
        delta = GreeksCalculator.calculate_delta(
            spot_price=100.0,
            strike=100.0,
            time_to_expiry=0.25,
            volatility=0.20,
            option_type='CE'
        )
        
        assert isinstance(delta, float)
        assert 0.0 <= delta <= 1.0
    
    def test_validate_inputs_valid(self):
        """Test input validation with valid inputs."""
        is_valid, error = GreeksCalculator.validate_inputs(
            spot_price=100.0,
            strike=100.0,
            time_to_expiry=0.25,
            volatility=0.20
        )
        
        assert is_valid is True
        assert error is None
    
    def test_validate_inputs_invalid_spot(self):
        """Test input validation with invalid spot price."""
        is_valid, error = GreeksCalculator.validate_inputs(
            spot_price=-100.0,
            strike=100.0,
            time_to_expiry=0.25,
            volatility=0.20
        )
        
        assert is_valid is False
        assert "Spot price" in error
    
    def test_validate_inputs_invalid_strike(self):
        """Test input validation with invalid strike."""
        is_valid, error = GreeksCalculator.validate_inputs(
            spot_price=100.0,
            strike=-100.0,
            time_to_expiry=0.25,
            volatility=0.20
        )
        
        assert is_valid is False
        assert "Strike price" in error
    
    def test_validate_inputs_invalid_time(self):
        """Test input validation with negative time."""
        is_valid, error = GreeksCalculator.validate_inputs(
            spot_price=100.0,
            strike=100.0,
            time_to_expiry=-0.25,
            volatility=0.20
        )
        
        assert is_valid is False
        assert "Time to expiry" in error
    
    def test_validate_inputs_invalid_volatility(self):
        """Test input validation with negative volatility."""
        is_valid, error = GreeksCalculator.validate_inputs(
            spot_price=100.0,
            strike=100.0,
            time_to_expiry=0.25,
            volatility=-0.20
        )
        
        assert is_valid is False
        assert "Volatility" in error
    
    def test_high_volatility(self):
        """Test Greeks calculation with high volatility."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=100.0,
            strike=100.0,
            time_to_expiry=0.25,
            volatility=0.50,  # 50% volatility
            option_type='CE'
        )
        
        # High volatility should increase vega
        assert greeks['vega'] > 0
        # Gamma should still be positive
        assert greeks['gamma'] > 0
    
    def test_long_time_to_expiry(self):
        """Test Greeks calculation with long expiry."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=100.0,
            strike=100.0,
            time_to_expiry=1.0,  # 1 year
            volatility=0.20,
            option_type='CE'
        )
        
        # Long expiry should have lower theta (less decay per day)
        assert greeks['theta'] < 0
        # But higher absolute value in total decay
    
    def test_custom_risk_free_rate(self):
        """Test Greeks with custom risk-free rate."""
        greeks = GreeksCalculator.calculate_greeks(
            spot_price=100.0,
            strike=100.0,
            time_to_expiry=0.25,
            volatility=0.20,
            risk_free_rate=0.05,  # 5%
            option_type='CE'
        )
        
        # Should calculate without error
        assert 'delta' in greeks
        assert 'rho' in greeks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
