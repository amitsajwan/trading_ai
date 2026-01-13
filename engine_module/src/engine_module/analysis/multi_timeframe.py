"""Multi-Timeframe Analysis for Trading Confluence Detection.

This module analyzes market data across multiple timeframes to identify:
- Trend direction for each timeframe
- Confluence (agreement) across timeframes
- Dominant trend identification
- Trading signal strength based on timeframe alignment

Uses data from market_data module's MultiTimeframeReader and TechnicalIndicatorsService.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class TimeframeTrend(Enum):
    """Trend direction for a single timeframe."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class TimeframeData:
    """Analysis result for a single timeframe."""
    timeframe: str  # '5m', '15m', '1h', 'daily'
    close: float
    sma_20: Optional[float] = None
    ema_50: Optional[float] = None
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    adx: Optional[float] = None
    trend: TimeframeTrend = TimeframeTrend.NEUTRAL
    strength: float = 0.0  # 0-100, trend strength score


@dataclass
class MultiTimeframeAnalysis:
    """Complete multi-timeframe analysis result."""
    timeframe_results: List[TimeframeData]
    is_aligned: bool  # True if all timeframes agree on direction
    dominant_trend: TimeframeTrend  # Overall trend across all timeframes
    confluence_score: float  # 0-100, how well timeframes agree
    bullish_count: int  # Number of bullish timeframes
    bearish_count: int  # Number of bearish timeframes
    neutral_count: int  # Number of neutral timeframes
    average_strength: float  # Average trend strength across timeframes


class MultiTimeframeAnalyzer:
    """Analyze multiple timeframes for confluence and trend identification.
    
    This analyzer takes indicator data from multiple timeframes and:
    1. Determines trend direction for each timeframe
    2. Calculates trend strength for each timeframe
    3. Identifies confluence (agreement) across timeframes
    4. Determines dominant trend
    5. Calculates overall confluence score
    
    Example:
        analyzer = MultiTimeframeAnalyzer(config)
        
        # Get indicators for all timeframes (from TechnicalIndicatorsService)
        indicators_data = {
            '5m': {...indicators...},
            '15m': {...indicators...},
            '1h': {...indicators...},
            'daily': {...indicators...}
        }
        
        analysis = analyzer.analyze(indicators_data)
        print(f"Dominant trend: {analysis.dominant_trend}")
        print(f"Confluence score: {analysis.confluence_score}")
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize multi-timeframe analyzer.
        
        Args:
            config: Configuration dictionary with:
                - timeframes: List of timeframes to analyze (default: ['5m', '15m', '1h', 'daily'])
                - required_alignment: Minimum number of timeframes that must agree (default: 3)
                - rsi_oversold: RSI threshold for oversold (default: 30)
                - rsi_overbought: RSI threshold for overbought (default: 70)
                - adx_trending: ADX threshold for strong trend (default: 25)
                - timeframe_weights: Dict mapping timeframe to weight (higher = more important)
        """
        config = config or {}
        
        self.timeframes = config.get('timeframes', ['5m', '15m', '1h', 'daily'])
        self.required_alignment = config.get('required_alignment', 3)
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.rsi_overbought = config.get('rsi_overbought', 70)
        self.adx_trending = config.get('adx_trending', 25)
        
        # Timeframe weights (higher timeframes more important)
        default_weights = {
            '5m': 1,
            '15m': 2,
            '1h': 3,
            'daily': 4
        }
        self.timeframe_weights = config.get('timeframe_weights', default_weights)
        
        logger.info(f"MultiTimeframeAnalyzer initialized with timeframes: {self.timeframes}")
    
    def analyze(self, data: Dict[str, Dict[str, Any]]) -> MultiTimeframeAnalysis:
        """Analyze multiple timeframes for confluence.
        
        Args:
            data: Dictionary with timeframe as key and indicator data as value.
                Each timeframe dict should contain:
                - close: Current close price
                - sma_20: 20-period SMA
                - ema_50: 50-period EMA
                - rsi: RSI value (or rsi_14)
                - macd: MACD value (or macd_value)
                - macd_signal: MACD signal (or macd_signal)
                - adx: ADX value (or adx_14)
                
                Example:
                {
                    '5m': {
                        'close': 45000,
                        'sma_20': 44800,
                        'ema_50': 44700,
                        'rsi': 55,
                        'macd': 10,
                        'macd_signal': 8,
                        'adx': 30
                    },
                    '15m': {...},
                    ...
                }
        
        Returns:
            MultiTimeframeAnalysis with complete analysis results
        """
        timeframe_results = []
        
        for tf in self.timeframes:
            if tf not in data:
                logger.warning(f"Timeframe {tf} not found in data, skipping")
                continue
            
            tf_data = data[tf]
            trend = self._determine_trend(tf_data)
            strength = self._calculate_strength(tf_data)
            
            # Extract values with fallbacks
            close = tf_data.get('close') or tf_data.get('current_price', 0)
            sma_20 = tf_data.get('sma_20', 0)
            ema_50 = tf_data.get('ema_50', 0)
            rsi = tf_data.get('rsi') or tf_data.get('rsi_14', 50)
            macd = tf_data.get('macd') or tf_data.get('macd_value', 0)
            macd_signal = tf_data.get('macd_signal', 0)
            adx = tf_data.get('adx') or tf_data.get('adx_14', 0)
            
            timeframe_results.append(TimeframeData(
                timeframe=tf,
                close=close,
                sma_20=sma_20,
                ema_50=ema_50,
                rsi=rsi,
                macd=macd,
                macd_signal=macd_signal,
                adx=adx,
                trend=trend,
                strength=strength
            ))
        
        if not timeframe_results:
            logger.warning("No timeframe data available for analysis")
            return MultiTimeframeAnalysis(
                timeframe_results=[],
                is_aligned=False,
                dominant_trend=TimeframeTrend.NEUTRAL,
                confluence_score=0.0,
                bullish_count=0,
                bearish_count=0,
                neutral_count=0,
                average_strength=0.0
            )
        
        # Calculate aggregate metrics
        is_aligned = self._check_alignment(timeframe_results)
        dominant_trend = self._get_dominant_trend(timeframe_results)
        confluence_score = self._calculate_confluence_score(timeframe_results)
        
        bullish_count = sum(1 for tf in timeframe_results if tf.trend == TimeframeTrend.BULLISH)
        bearish_count = sum(1 for tf in timeframe_results if tf.trend == TimeframeTrend.BEARISH)
        neutral_count = sum(1 for tf in timeframe_results if tf.trend == TimeframeTrend.NEUTRAL)
        average_strength = sum(tf.strength for tf in timeframe_results) / len(timeframe_results)
        
        return MultiTimeframeAnalysis(
            timeframe_results=timeframe_results,
            is_aligned=is_aligned,
            dominant_trend=dominant_trend,
            confluence_score=confluence_score,
            bullish_count=bullish_count,
            bearish_count=bearish_count,
            neutral_count=neutral_count,
            average_strength=average_strength
        )
    
    def _determine_trend(self, data: Dict[str, Any]) -> TimeframeTrend:
        """Determine trend for single timeframe.
        
        Uses multiple indicators:
        - Price vs Moving Averages (SMA 20, EMA 50)
        - MACD direction
        - RSI position
        
        Returns:
            TimeframeTrend (BULLISH, BEARISH, or NEUTRAL)
        """
        close = data.get('close') or data.get('current_price', 0)
        sma_20 = data.get('sma_20', 0)
        ema_50 = data.get('ema_50', 0)
        macd = data.get('macd') or data.get('macd_value', 0)
        macd_signal = data.get('macd_signal', 0)
        rsi = data.get('rsi') or data.get('rsi_14', 50)
        
        if not close or close <= 0:
            return TimeframeTrend.NEUTRAL
        
        bullish_signals = 0
        bearish_signals = 0
        
        # Price vs Moving Averages
        if sma_20 > 0:
            if close > sma_20:
                bullish_signals += 1
            else:
                bearish_signals += 1
        
        if ema_50 > 0:
            if close > ema_50:
                bullish_signals += 1
            else:
                bearish_signals += 1
        
        # MACD direction
        if macd and macd_signal:
            if macd > macd_signal:
                bullish_signals += 1
            elif macd < macd_signal:
                bearish_signals += 1
        
        # RSI position (not extreme)
        if 30 < rsi < 70:
            if rsi > 50:
                bullish_signals += 0.5
            else:
                bearish_signals += 0.5
        
        # Determine trend
        if bullish_signals > bearish_signals:
            return TimeframeTrend.BULLISH
        elif bearish_signals > bullish_signals:
            return TimeframeTrend.BEARISH
        else:
            return TimeframeTrend.NEUTRAL
    
    def _calculate_strength(self, data: Dict[str, Any]) -> float:
        """Calculate trend strength (0-100).
        
        Uses:
        - ADX: Trend strength indicator
        - RSI extremes: Strong momentum
        - MACD histogram: Momentum strength
        
        Returns:
            Strength score (0-100)
        """
        adx = data.get('adx') or data.get('adx_14', 0)
        rsi = data.get('rsi') or data.get('rsi_14', 50)
        macd = data.get('macd') or data.get('macd_value', 0)
        macd_signal = data.get('macd_signal', 0)
        macd_histogram = data.get('macd_histogram', 0)
        
        # Base strength from ADX (0-100 scale, ADX typically 0-50)
        strength = min(100, adx * 2) if adx > 0 else 0
        
        # Adjust for RSI extremes (strong momentum)
        if rsi > 70 or rsi < 30:
            strength *= 1.2
            strength = min(100, strength)
        
        # Adjust for MACD histogram (momentum strength)
        if macd_histogram:
            macd_strength = abs(macd_histogram) / max(abs(macd), abs(macd_signal), 1) * 20
            strength += macd_strength
            strength = min(100, strength)
        
        return max(0.0, min(100.0, strength))
    
    def _check_alignment(self, results: List[TimeframeData]) -> bool:
        """Check if all timeframes agree on direction.
        
        Args:
            results: List of TimeframeData for each timeframe
        
        Returns:
            True if all timeframes agree on direction (and not neutral)
        """
        if not results:
            return False
        
        # Filter out neutral timeframes
        non_neutral = [tf for tf in results if tf.trend != TimeframeTrend.NEUTRAL]
        
        if len(non_neutral) < self.required_alignment:
            return False
        
        # Check if all non-neutral timeframes agree
        trends = [tf.trend for tf in non_neutral]
        return len(set(trends)) == 1
    
    def _get_dominant_trend(self, results: List[TimeframeData]) -> TimeframeTrend:
        """Get dominant trend across timeframes (weighted by timeframe importance).
        
        Args:
            results: List of TimeframeData for each timeframe
        
        Returns:
            Dominant TimeframeTrend
        """
        if not results:
            return TimeframeTrend.NEUTRAL
        
        # Weight by timeframe (higher timeframes more important)
        bullish_score = sum(
            self.timeframe_weights.get(tf.timeframe, 1)
            for tf in results
            if tf.trend == TimeframeTrend.BULLISH
        )
        
        bearish_score = sum(
            self.timeframe_weights.get(tf.timeframe, 1)
            for tf in results
            if tf.trend == TimeframeTrend.BEARISH
        )
        
        if bullish_score > bearish_score:
            return TimeframeTrend.BULLISH
        elif bearish_score > bullish_score:
            return TimeframeTrend.BEARISH
        else:
            return TimeframeTrend.NEUTRAL
    
    def _calculate_confluence_score(self, results: List[TimeframeData]) -> float:
        """Calculate confluence score (0-100).
        
        Measures how well timeframes agree on direction and strength.
        
        Args:
            results: List of TimeframeData for each timeframe
        
        Returns:
            Confluence score (0-100)
        """
        if not results:
            return 0.0
        
        # 1. Trend agreement (60% weight)
        trends = [tf.trend for tf in results]
        non_neutral = [t for t in trends if t != TimeframeTrend.NEUTRAL]
        
        if not non_neutral:
            return 0.0
        
        # Calculate agreement percentage
        if len(set(non_neutral)) == 1:
            # All agree
            trend_agreement = 1.0
        else:
            # Calculate majority
            from collections import Counter
            trend_counts = Counter(non_neutral)
            most_common_count = trend_counts.most_common(1)[0][1]
            trend_agreement = most_common_count / len(non_neutral)
        
        # 2. Average strength (40% weight)
        avg_strength = sum(tf.strength for tf in results) / len(results)
        strength_score = avg_strength / 100.0
        
        # Combined score
        confluence_score = (trend_agreement * 0.6 + strength_score * 0.4) * 100
        
        return max(0.0, min(100.0, confluence_score))
    
    def get_trading_signal(self, analysis: MultiTimeframeAnalysis) -> Dict[str, Any]:
        """Get trading signal based on multi-timeframe analysis.
        
        Args:
            analysis: MultiTimeframeAnalysis result
        
        Returns:
            Dictionary with signal information:
            - action: 'BUY', 'SELL', or 'HOLD'
            - confidence: 0-100
            - reason: Human-readable explanation
        """
        if analysis.confluence_score < 50:
            return {
                'action': 'HOLD',
                'confidence': 100 - analysis.confluence_score,
                'reason': f'Low confluence ({analysis.confluence_score:.1f}%) - timeframes disagree'
            }
        
        if not analysis.is_aligned:
            return {
                'action': 'HOLD',
                'confidence': 50,
                'reason': f'Timeframes not aligned ({analysis.bullish_count} bullish, {analysis.bearish_count} bearish)'
            }
        
        if analysis.dominant_trend == TimeframeTrend.BULLISH:
            confidence = min(100, int(analysis.confluence_score * 0.8 + analysis.average_strength * 0.2))
            return {
                'action': 'BUY',
                'confidence': confidence,
                'reason': f'Bullish confluence ({analysis.confluence_score:.1f}%) across {len(analysis.timeframe_results)} timeframes'
            }
        elif analysis.dominant_trend == TimeframeTrend.BEARISH:
            confidence = min(100, int(analysis.confluence_score * 0.8 + analysis.average_strength * 0.2))
            return {
                'action': 'SELL',
                'confidence': confidence,
                'reason': f'Bearish confluence ({analysis.confluence_score:.1f}%) across {len(analysis.timeframe_results)} timeframes'
            }
        else:
            return {
                'action': 'HOLD',
                'confidence': 50,
                'reason': 'Neutral trend - no clear direction'
            }
