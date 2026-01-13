"""Market Regime Detection for Trading Strategy Selection.

This module detects current market regime (trending, ranging, high volatility, breakout)
based on technical indicators and helps select appropriate trading strategies.
"""

import logging
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime types."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    BREAKOUT_UP = "breakout_up"
    BREAKOUT_DOWN = "breakout_down"


class RegimeDetector:
    """Detect current market regime for strategy selection.
    
    Uses multiple technical indicators to identify market regime:
    - ADX: Trend strength
    - IV Percentile: Volatility regime
    - Volume Ratio: Volume confirmation
    - Bollinger Bands: Price position relative to volatility
    - Moving Averages: Trend direction
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize regime detector.
        
        Args:
            config: Configuration dictionary with thresholds:
                - adx_trending: ADX threshold for trending (default: 25)
                - iv_high_percentile: IV percentile for high volatility (default: 80)
                - iv_low_percentile: IV percentile for low volatility (default: 20)
                - volume_spike_threshold: Volume ratio for breakout (default: 2.0)
                - bb_percentile_upper: Upper Bollinger Band percentile for breakout (default: 0.95)
                - bb_percentile_lower: Lower Bollinger Band percentile for breakout (default: 0.05)
        """
        config = config or {}
        
        self.adx_trending_threshold = config.get('adx_trending', 25)
        self.iv_high_threshold = config.get('iv_high_percentile', 80)
        self.iv_low_threshold = config.get('iv_low_percentile', 20)
        self.volume_spike_threshold = config.get('volume_spike_threshold', 2.0)
        self.bb_upper_percentile = config.get('bb_percentile_upper', 0.95)
        self.bb_lower_percentile = config.get('bb_percentile_lower', 0.05)
        
        logger.info(f"RegimeDetector initialized with thresholds: ADX={self.adx_trending_threshold}, IV_high={self.iv_high_threshold}")
    
    def detect(self, market_data: Dict[str, Any]) -> MarketRegime:
        """Detect market regime using multiple indicators.
        
        Args:
            market_data: Dictionary with technical indicators:
                - close: Current close price
                - sma_20: 20-period SMA
                - ema_50: 50-period EMA
                - adx: ADX value (trend strength)
                - iv_percentile: Implied volatility percentile (0-100)
                - volume_ratio: Volume ratio (current / average)
                - bollinger_upper: Upper Bollinger Band
                - bollinger_lower: Lower Bollinger Band
                - bollinger_percent_b: Price position in Bollinger Bands (0-1)
        
        Returns:
            Detected MarketRegime
        """
        close = market_data.get('close', 0) or market_data.get('current_price', 0)
        sma_20 = market_data.get('sma_20', 0) or 0
        ema_50 = market_data.get('ema_50', 0) or 0
        adx = market_data.get('adx', 0) or market_data.get('adx_14', 0) or 0
        iv_percentile = market_data.get('iv_percentile', 50) or 50
        volume_ratio = market_data.get('volume_ratio', 1.0) or 1.0
        bb_upper = market_data.get('bollinger_upper', 0) or 0
        bb_lower = market_data.get('bollinger_lower', 0) or 0
        bb_percent_b = market_data.get('bollinger_percent_b', 0.5) or 0.5
        
        if not close or close <= 0:
            logger.warning("Invalid market data: missing or invalid close price")
            return MarketRegime.RANGING
        
        # 1. High Volatility Regime (check first as it overrides other regimes)
        if iv_percentile > self.iv_high_threshold:
            logger.debug(f"High volatility regime detected: IV percentile={iv_percentile}")
            return MarketRegime.HIGH_VOLATILITY
        
        # 2. Breakout Detection (volume spike + price near bands)
        if volume_ratio >= self.volume_spike_threshold:
            if bb_percent_b >= self.bb_upper_percentile and close > sma_20:
                logger.debug(f"Breakout up detected: volume_ratio={volume_ratio}, bb_percent_b={bb_percent_b}")
                return MarketRegime.BREAKOUT_UP
            elif bb_percent_b <= self.bb_lower_percentile and close < sma_20:
                logger.debug(f"Breakout down detected: volume_ratio={volume_ratio}, bb_percent_b={bb_percent_b}")
                return MarketRegime.BREAKOUT_DOWN
        
        # 3. Trending Regime (strong ADX indicates trend)
        if adx > self.adx_trending_threshold:
            if close > sma_20 and close > ema_50:
                logger.debug(f"Trending up detected: ADX={adx}, price above SMAs")
                return MarketRegime.TRENDING_UP
            elif close < sma_20 and close < ema_50:
                logger.debug(f"Trending down detected: ADX={adx}, price below SMAs")
                return MarketRegime.TRENDING_DOWN
        
        # 4. Default: Ranging Market
        logger.debug("Ranging market detected (default)")
        return MarketRegime.RANGING
    
    def get_suitable_strategies(self, regime: MarketRegime) -> List[str]:
        """Return suitable trading strategies for detected regime.
        
        Args:
            regime: Detected market regime
        
        Returns:
            List of strategy names suitable for the regime
        """
        strategy_map = {
            MarketRegime.RANGING: [
                'iron_condor',
                'butterfly',
                'short_strangle',
                'calendar_spread'
            ],
            MarketRegime.TRENDING_UP: [
                'bull_call_spread',
                'long_call',
                'call_backspread',
                'ratio_call_spread'
            ],
            MarketRegime.TRENDING_DOWN: [
                'bear_put_spread',
                'long_put',
                'put_backspread',
                'ratio_put_spread'
            ],
            MarketRegime.HIGH_VOLATILITY: [
                'iron_condor',
                'calendar_spread',
                'short_straddle',
                'short_strangle'
            ],
            MarketRegime.BREAKOUT_UP: [
                'long_call',
                'bull_call_spread',
                'call_backspread'
            ],
            MarketRegime.BREAKOUT_DOWN: [
                'long_put',
                'bear_put_spread',
                'put_backspread'
            ]
        }
        
        return strategy_map.get(regime, ['iron_condor'])
    
    def detect_with_confidence(
        self, 
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Detect regime with confidence score.
        
        Args:
            market_data: Market data dictionary (same as detect())
        
        Returns:
            Dictionary with:
                - regime: MarketRegime enum
                - confidence: Confidence score (0-1)
                - indicators: Dictionary of indicator values used
                - strategies: List of suitable strategies
        """
        regime = self.detect(market_data)
        
        # Calculate confidence based on how strongly indicators agree
        close = market_data.get('close', 0) or market_data.get('current_price', 0)
        sma_20 = market_data.get('sma_20', 0) or 0
        ema_50 = market_data.get('ema_50', 0) or 0
        adx = market_data.get('adx', 0) or market_data.get('adx_14', 0) or 0
        iv_percentile = market_data.get('iv_percentile', 50) or 50
        volume_ratio = market_data.get('volume_ratio', 1.0) or 1.0
        
        confidence = 0.5  # Base confidence
        
        # Increase confidence if multiple indicators agree
        if regime == MarketRegime.TRENDING_UP or regime == MarketRegime.TRENDING_DOWN:
            # Higher ADX = stronger trend = higher confidence
            adx_strength = min(1.0, adx / 50.0)  # Normalize ADX to 0-1
            ma_alignment = 1.0 if (close > sma_20 > ema_50) or (close < sma_20 < ema_50) else 0.5
            confidence = 0.3 + (adx_strength * 0.4) + (ma_alignment * 0.3)
        
        elif regime == MarketRegime.BREAKOUT_UP or regime == MarketRegime.BREAKOUT_DOWN:
            # Volume spike strength increases confidence
            volume_strength = min(1.0, volume_ratio / 3.0)  # Normalize to 0-1
            confidence = 0.4 + (volume_strength * 0.4)
        
        elif regime == MarketRegime.HIGH_VOLATILITY:
            # Higher IV percentile = more confident
            iv_strength = (iv_percentile - 50) / 50.0  # Normalize to 0-1
            confidence = 0.5 + (iv_strength * 0.3)
        
        else:  # RANGING
            # Low ADX indicates ranging
            adx_low = max(0, (self.adx_trending_threshold - adx) / self.adx_trending_threshold)
            confidence = 0.4 + (adx_low * 0.3)
        
        confidence = max(0.0, min(1.0, confidence))  # Clamp to 0-1
        
        return {
            'regime': regime,
            'regime_value': regime.value,
            'confidence': confidence,
            'indicators': {
                'adx': adx,
                'iv_percentile': iv_percentile,
                'volume_ratio': volume_ratio,
                'close': close,
                'sma_20': sma_20,
                'ema_50': ema_50
            },
            'strategies': self.get_suitable_strategies(regime)
        }
