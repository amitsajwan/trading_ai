"""Unit tests for EnhancedOptionsChainAdapter."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, MagicMock

from market_data.providers.enhanced_options_chain import EnhancedOptionsChainAdapter


class TestEnhancedOptionsChainAdapter:
    """Tests for EnhancedOptionsChainAdapter."""
    
    def test_initialization(self):
        """Test adapter initialization."""
        adapter = EnhancedOptionsChainAdapter(
            kite=None,
            instrument_symbol="BANKNIFTY",
            use_live_quotes=False,
            enable_greeks=True
        )
        
        assert adapter.instrument_symbol == "BANKNIFTY"
        assert adapter.enable_greeks is True
    
    def test_validate_option_data_valid(self):
        """Test validation with valid option data."""
        adapter = EnhancedOptionsChainAdapter()
        
        option_data = {
            "tradingsymbol": "BANKNIFTY24JAN47500CE",
            "instrument_token": 12345,
            "strike": 47500.0,
            "expiry": date(2026, 1, 30)
        }
        
        is_valid, error = adapter._validate_option_data(option_data)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_option_data_missing_field(self):
        """Test validation with missing required field."""
        adapter = EnhancedOptionsChainAdapter()
        
        option_data = {
            "tradingsymbol": "BANKNIFTY24JAN47500CE",
            # Missing instrument_token
            "strike": 47500.0,
            "expiry": date(2026, 1, 30)
        }
        
        is_valid, error = adapter._validate_option_data(option_data)
        
        assert is_valid is False
        assert "Missing required field" in error
    
    def test_validate_option_data_invalid_strike(self):
        """Test validation with invalid strike price."""
        adapter = EnhancedOptionsChainAdapter()
        
        option_data = {
            "tradingsymbol": "BANKNIFTY24JAN47500CE",
            "instrument_token": 12345,
            "strike": -100.0,  # Invalid
            "expiry": date(2026, 1, 30)
        }
        
        is_valid, error = adapter._validate_option_data(option_data)
        
        assert is_valid is False
        assert "Invalid strike price" in error
    
    def test_normalize_option_data(self):
        """Test data normalization."""
        adapter = EnhancedOptionsChainAdapter()
        
        raw_data = {
            "tradingsymbol": "BANKNIFTY24JAN47500CE",
            "instrument_token": 12345,
            "strike": 47500.0,
            "expiry": date(2026, 1, 30),
            "instrument_type": "CE",
            "last_price": 150.5,
            "bid": 149.0,
            "ask": 151.0,
            "volume": 1000,
            "oi": 50000,
            "timestamp": datetime.now().isoformat()
        }
        
        normalized = adapter._normalize_option_data(raw_data)
        
        assert normalized["tradingsymbol"] == "BANKNIFTY24JAN47500CE"
        assert normalized["instrument_token"] == 12345
        assert normalized["strike"] == 47500.0
        assert normalized["last_price"] == 150.5
        assert normalized["volume"] == 1000
        assert normalized["oi"] == 50000
    
    def test_calculate_greeks_without_calculator(self):
        """Test Greeks calculation without calculator."""
        adapter = EnhancedOptionsChainAdapter(enable_greeks=False)
        
        option_data = {}
        greeks = adapter._calculate_greeks(
            option_data,
            underlying_price=47500.0,
            strike=47500.0,
            time_to_expiry=0.1,
            implied_vol=None,
            option_type="CE"
        )
        
        assert greeks["delta"] is None
        assert greeks["gamma"] is None
        assert greeks["theta"] is None
    
    def test_enhance_option_data(self):
        """Test option data enhancement."""
        adapter = EnhancedOptionsChainAdapter(enable_greeks=False)
        
        option_data = {
            "strike": 47500.0,
            "expiry": date.today() + timedelta(days=30),
            "option_type": "CE",
            "last_price": 150.5
        }
        
        enhanced = adapter._enhance_option_data(option_data, underlying_price=47500.0)
        
        # Should have IV field (even if None)
        assert "iv" in enhanced
    
    def test_organize_by_strikes_enhanced_fields(self):
        """Test that organize_by_strikes includes enhanced fields."""
        adapter = EnhancedOptionsChainAdapter(enable_greeks=False)
        
        # Create mock options DataFrame
        import pandas as pd
        options_df = pd.DataFrame([
            {
                "tradingsymbol": "BANKNIFTY24JAN47500CE",
                "instrument_token": 12345,
                "strike": 47500.0,
                "expiry": date(2026, 1, 30),
                "instrument_type": "CE"
            },
            {
                "tradingsymbol": "BANKNIFTY24JAN47500PE",
                "instrument_token": 12346,
                "strike": 47500.0,
                "expiry": date(2026, 1, 30),
                "instrument_type": "PE"
            }
        ])
        
        # Create mock price data
        price_data = {
            "12345": {
                "last_price": 150.5,
                "volume": 1000,
                "oi": 50000,
                "bid": 149.0,
                "ask": 151.0,
                "timestamp": datetime.now().isoformat()
            },
            "12346": {
                "last_price": 100.5,
                "volume": 800,
                "oi": 45000,
                "bid": 99.0,
                "ask": 101.0,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # Call organize_by_strikes
        strikes_data = adapter._organize_by_strikes(options_df, price_data)
        
        assert len(strikes_data) > 0
        strike_data = strikes_data[0]
        
        # Check enhanced fields are present
        assert "ce_ltp" in strike_data
        assert "pe_ltp" in strike_data
        assert "ce_volume" in strike_data
        assert "pe_volume" in strike_data
        assert "ce_oi" in strike_data
        assert "pe_oi" in strike_data
        assert "ce_iv" in strike_data
        assert "pe_iv" in strike_data
        assert "ce_delta" in strike_data
        assert "pe_delta" in strike_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
