"""Unit tests for Market Regime Detector."""

import pytest
from engine_module.analysis.regime_detector import MarketRegime, RegimeDetector


class TestMarketRegime:
    """Tests for MarketRegime enum."""
    
    def test_regime_values(self):
        """Test that all regimes have values."""
        assert MarketRegime.TRENDING_UP.value == "trending_up"
        assert MarketRegime.TRENDING_DOWN.value == "trending_down"
        assert MarketRegime.RANGING.value == "ranging"
        assert MarketRegime.HIGH_VOLATILITY.value == "high_volatility"
        assert MarketRegime.BREAKOUT_UP.value == "breakout_up"
        assert MarketRegime.BREAKOUT_DOWN.value == "breakout_down"


class TestRegimeDetector:
    """Tests for RegimeDetector."""
    
    def test_initialization(self):
        """Test detector initialization."""
        detector = RegimeDetector()
        
        assert detector.adx_trending_threshold == 25
        assert detector.iv_high_threshold == 80
    
    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        config = {
            'adx_trending': 30,
            'iv_high_percentile': 85
        }
        detector = RegimeDetector(config)
        
        assert detector.adx_trending_threshold == 30
        assert detector.iv_high_threshold == 85
    
    def test_detect_high_volatility(self):
        """Test high volatility regime detection."""
        detector = RegimeDetector()
        
        market_data = {
            'close': 47500.0,
            'iv_percentile': 85,  # High IV
            'adx': 20,
            'volume_ratio': 1.5
        }
        
        regime = detector.detect(market_data)
        assert regime == MarketRegime.HIGH_VOLATILITY
    
    def test_detect_trending_up(self):
        """Test trending up regime detection."""
        detector = RegimeDetector()
        
        market_data = {
            'close': 48000.0,
            'sma_20': 47600.0,
            'ema_50': 47400.0,
            'adx': 30,  # Strong trend
            'iv_percentile': 50,
            'volume_ratio': 1.2
        }
        
        regime = detector.detect(market_data)
        assert regime == MarketRegime.TRENDING_UP
    
    def test_detect_trending_down(self):
        """Test trending down regime detection."""
        detector = RegimeDetector()
        
        market_data = {
            'close': 47000.0,
            'sma_20': 47400.0,
            'ema_50': 47600.0,
            'adx': 28,  # Strong trend
            'iv_percentile': 50,
            'volume_ratio': 1.1
        }
        
        regime = detector.detect(market_data)
        assert regime == MarketRegime.TRENDING_DOWN
    
    def test_detect_breakout_up(self):
        """Test breakout up regime detection."""
        detector = RegimeDetector()
        
        market_data = {
            'close': 48000.0,
            'sma_20': 47600.0,
            'volume_ratio': 2.5,  # Volume spike
            'bollinger_percent_b': 0.97,  # Near upper band
            'iv_percentile': 50,
            'adx': 20
        }
        
        regime = detector.detect(market_data)
        assert regime == MarketRegime.BREAKOUT_UP
    
    def test_detect_breakout_down(self):
        """Test breakout down regime detection."""
        detector = RegimeDetector()
        
        market_data = {
            'close': 47000.0,
            'sma_20': 47400.0,
            'volume_ratio': 2.3,  # Volume spike
            'bollinger_percent_b': 0.03,  # Near lower band
            'iv_percentile': 50,
            'adx': 18
        }
        
        regime = detector.detect(market_data)
        assert regime == MarketRegime.BREAKOUT_DOWN
    
    def test_detect_ranging(self):
        """Test ranging market detection."""
        detector = RegimeDetector()
        
        market_data = {
            'close': 47500.0,
            'sma_20': 47500.0,
            'adx': 18,  # Weak trend
            'iv_percentile': 50,
            'volume_ratio': 1.0
        }
        
        regime = detector.detect(market_data)
        assert regime == MarketRegime.RANGING
    
    def test_get_suitable_strategies(self):
        """Test strategy recommendations for each regime."""
        detector = RegimeDetector()
        
        # Ranging strategies
        strategies = detector.get_suitable_strategies(MarketRegime.RANGING)
        assert 'iron_condor' in strategies
        assert 'butterfly' in strategies
        
        # Trending up strategies
        strategies = detector.get_suitable_strategies(MarketRegime.TRENDING_UP)
        assert 'bull_call_spread' in strategies
        assert 'long_call' in strategies
        
        # Trending down strategies
        strategies = detector.get_suitable_strategies(MarketRegime.TRENDING_DOWN)
        assert 'bear_put_spread' in strategies
        assert 'long_put' in strategies
    
    def test_detect_with_confidence(self):
        """Test regime detection with confidence score."""
        detector = RegimeDetector()
        
        market_data = {
            'close': 48000.0,
            'sma_20': 47600.0,
            'ema_50': 47400.0,
            'adx': 35,  # Strong trend
            'iv_percentile': 50,
            'volume_ratio': 1.2
        }
        
        result = detector.detect_with_confidence(market_data)
        
        assert 'regime' in result
        assert 'confidence' in result
        assert 'indicators' in result
        assert 'strategies' in result
        assert result['regime'] == MarketRegime.TRENDING_UP
        assert 0.0 <= result['confidence'] <= 1.0
        assert len(result['strategies']) > 0
    
    def test_invalid_market_data(self):
        """Test handling of invalid market data."""
        detector = RegimeDetector()
        
        # Missing close price
        market_data = {
            'adx': 25,
            'iv_percentile': 50
        }
        
        regime = detector.detect(market_data)
        # Should default to ranging
        assert regime == MarketRegime.RANGING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
