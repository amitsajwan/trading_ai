"""Integration tests for EnhancedOptionsChainAdapter."""

import pytest
from datetime import datetime, date
from unittest.mock import Mock

from market_data.providers.enhanced_options_chain import EnhancedOptionsChainAdapter


class MockKite:
    """Mock KiteConnect for testing."""
    
    def __init__(self):
        self.instruments_called = False
        self.quote_called = False
    
    def instruments(self, exchange):
        """Mock instruments method."""
        self.instruments_called = True
        return [
            {
                "instrument_token": 12345,
                "tradingsymbol": "BANKNIFTY24JAN47500CE",
                "name": "BANKNIFTY",
                "instrument_type": "CE",
                "strike": 47500.0,
                "expiry": date(2026, 1, 30),
                "exchange": "NFO"
            },
            {
                "instrument_token": 12346,
                "tradingsymbol": "BANKNIFTY24JAN47500PE",
                "name": "BANKNIFTY",
                "instrument_type": "PE",
                "strike": 47500.0,
                "expiry": date(2026, 1, 30),
                "exchange": "NFO"
            }
        ]
    
    def quote(self, tokens):
        """Mock quote method."""
        self.quote_called = True
        result = {}
        for token in tokens:
            if "FUT" in token:
                # Futures quote
                result[token] = Mock(to_dict=lambda: {
                    "last_price": 47500.0,
                    "ohlc": {"close": 47500.0}
                })
            elif "NSE" in token:
                # Spot quote
                result[token] = Mock(to_dict=lambda: {
                    "last_price": 47500.0,
                    "ohlc": {"close": 47500.0}
                })
            else:
                # Option quote
                result[token] = Mock(to_dict=lambda: {
                    "last_price": 150.5,
                    "volume": 1000,
                    "oi": 50000,
                    "depth": {
                        "buy": [{"price": 149.0, "quantity": 100}],
                        "sell": [{"price": 151.0, "quantity": 100}]
                    },
                    "ohlc": {"close": 150.0}
                })
        return result
    
    def ltp(self, tokens):
        """Mock ltp method."""
        result = {}
        for token in tokens:
            result[token] = {
                "last_price": 150.5,
                "volume": 1000,
                "oi": 50000
            }
        return result


class TestEnhancedOptionsChainIntegration:
    """Integration tests for EnhancedOptionsChainAdapter."""
    
    @pytest.mark.asyncio
    async def test_fetch_chain_with_enhanced_fields(self):
        """Test fetching chain with enhanced fields."""
        mock_kite = MockKite()
        adapter = EnhancedOptionsChainAdapter(
            kite=mock_kite,
            instrument_symbol="BANKNIFTY",
            use_live_quotes=False,
            enable_greeks=False  # Disable Greeks for now (requires calculator)
        )
        
        # Initialize
        await adapter.initialize()
        
        # Fetch chain
        chain = await adapter.fetch_options_chain()
        
        assert chain["available"] is True
        assert len(chain["strikes"]) > 0
        
        # Check first strike has enhanced fields
        first_strike = chain["strikes"][0]
        assert "ce_ltp" in first_strike
        assert "pe_ltp" in first_strike
        assert "ce_volume" in first_strike
        assert "pe_volume" in first_strike
        assert "ce_oi" in first_strike
        assert "pe_oi" in first_strike
        assert "ce_iv" in first_strike
        assert "pe_iv" in first_strike
        assert "ce_delta" in first_strike
        assert "pe_delta" in first_strike
    
    @pytest.mark.asyncio
    async def test_data_validation_in_chain(self):
        """Test that invalid data is filtered out."""
        mock_kite = MockKite()
        adapter = EnhancedOptionsChainAdapter(
            kite=mock_kite,
            instrument_symbol="BANKNIFTY",
            use_live_quotes=False,
            enable_greeks=False
        )
        
        await adapter.initialize()
        chain = await adapter.fetch_options_chain()
        
        # All strikes should have valid data
        for strike_data in chain["strikes"]:
            if strike_data.get("CE"):
                ce = strike_data["CE"]
                assert ce.get("strike") > 0
                assert ce.get("tradingsymbol")
                assert ce.get("instrument_token")
            
            if strike_data.get("PE"):
                pe = strike_data["PE"]
                assert pe.get("strike") > 0
                assert pe.get("tradingsymbol")
                assert pe.get("instrument_token")
    
    @pytest.mark.asyncio
    async def test_data_normalization(self):
        """Test that data is normalized correctly."""
        mock_kite = MockKite()
        adapter = EnhancedOptionsChainAdapter(
            kite=mock_kite,
            instrument_symbol="BANKNIFTY",
            use_live_quotes=False,
            enable_greeks=False
        )
        
        await adapter.initialize()
        chain = await adapter.fetch_options_chain()
        
        # Check data types are correct
        for strike_data in chain["strikes"]:
            assert isinstance(strike_data["strike"], int)
            
            if strike_data.get("CE"):
                ce = strike_data["CE"]
                assert isinstance(ce["last_price"], float)
                assert isinstance(ce["volume"], int)
                assert isinstance(ce["oi"], int)
            
            if strike_data.get("PE"):
                pe = strike_data["PE"]
                assert isinstance(pe["last_price"], float)
                assert isinstance(pe["volume"], int)
                assert isinstance(pe["oi"], int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
