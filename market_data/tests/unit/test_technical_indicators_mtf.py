"""Unit tests for multi-timeframe technical indicators."""

import pytest
from datetime import datetime, timedelta
from market_data.technical_indicators_service import TechnicalIndicatorsService
from market_data.contracts import OHLCBar


class TestTechnicalIndicatorsMultiTimeframe:
    """Tests for multi-timeframe technical indicators."""
    
    def test_update_candle_mtf(self):
        """Test updating indicators for specific timeframe."""
        service = TechnicalIndicatorsService()
        
        # Create sample candle
        candle = {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000,
            "start_at": datetime.now().isoformat()
        }
        
        # Update for 5m timeframe
        indicators = service.update_candle_mtf("BANKNIFTY", "5m", candle)
        
        assert indicators is not None
        assert indicators.instrument == "BANKNIFTY"
        assert indicators.timeframe == "5m"
    
    def test_get_indicators_mtf(self):
        """Test getting indicators for specific timeframe."""
        service = TechnicalIndicatorsService()
        
        # Add some data
        for i in range(25):
            candle = {
                "open": 100.0 + i * 0.1,
                "high": 101.0 + i * 0.1,
                "low": 99.0 + i * 0.1,
                "close": 100.5 + i * 0.1,
                "volume": 1000,
                "start_at": (datetime.now() - timedelta(minutes=25-i)).isoformat()
            }
            service.update_candle_mtf("BANKNIFTY", "15m", candle)
        
        # Get indicators
        indicators = service.get_indicators_mtf("BANKNIFTY", "15m")
        
        assert indicators is not None
        assert indicators.instrument == "BANKNIFTY"
        assert indicators.timeframe == "15m"
        # Should have some calculated indicators after 25 candles
        assert indicators.current_price > 0
    
    def test_get_all_timeframe_indicators(self):
        """Test getting indicators for multiple timeframes."""
        service = TechnicalIndicatorsService()
        
        # Add data for multiple timeframes
        timeframes = ["5m", "15m", "1h"]
        for tf in timeframes:
            for i in range(25):
                candle = {
                    "open": 100.0 + i * 0.1,
                    "high": 101.0 + i * 0.1,
                    "low": 99.0 + i * 0.1,
                    "close": 100.5 + i * 0.1,
                    "volume": 1000,
                    "start_at": (datetime.now() - timedelta(minutes=25-i)).isoformat()
                }
                service.update_candle_mtf("BANKNIFTY", tf, candle)
        
        # Get all timeframe indicators
        all_indicators = service.get_all_timeframe_indicators("BANKNIFTY", timeframes)
        
        assert len(all_indicators) == len(timeframes)
        for tf in timeframes:
            assert tf in all_indicators
            assert all_indicators[tf].timeframe == tf
    
    def test_calculate_indicators_from_ohlc_bars(self):
        """Test calculating indicators from OHLCBar objects."""
        service = TechnicalIndicatorsService()
        
        # Create sample OHLC bars
        bars = []
        for i in range(25):
            bars.append(OHLCBar(
                instrument="BANKNIFTY",
                timeframe="5m",
                open=100.0 + i * 0.1,
                high=101.0 + i * 0.1,
                low=99.0 + i * 0.1,
                close=100.5 + i * 0.1,
                volume=1000,
                start_at=datetime.now() - timedelta(minutes=25-i)
            ))
        
        # Calculate indicators
        indicators = service.calculate_indicators_from_ohlc_bars(
            "BANKNIFTY", "5m", bars
        )
        
        assert indicators is not None
        assert indicators.instrument == "BANKNIFTY"
        assert indicators.timeframe == "5m"
        assert indicators.current_price > 0
    
    def test_backward_compatibility(self):
        """Test that original single-timeframe methods still work."""
        service = TechnicalIndicatorsService()
        
        # Test original update_candle method
        candle = {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000,
            "start_at": datetime.now().isoformat()
        }
        
        indicators = service.update_candle("BANKNIFTY", candle)
        
        assert indicators is not None
        assert indicators.instrument == "BANKNIFTY"
        
        # Test original get_indicators method
        retrieved = service.get_indicators("BANKNIFTY")
        assert retrieved is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
