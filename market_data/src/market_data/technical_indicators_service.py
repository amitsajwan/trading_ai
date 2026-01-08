"""Real-time Technical Indicators Service using Pandas.

This service calculates comprehensive technical indicators using pandas and pandas-ta
on historical OHLC data. Provides real-time indicators that traders actually use.

Architecture:
    OHLC Candles → Pandas DataFrame → Technical Calculations → Store in Redis
    Agent Analysis → get_indicators() → Read latest indicators

Indicators calculated:
    - Moving Averages: SMA, EMA, WMA
    - Momentum: RSI, MACD, Stochastic
    - Volatility: Bollinger Bands, ATR
    - Trend: ADX, Ichimoku
    - Volume: OBV, Volume RSI
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from collections import deque
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
import redis

logger = logging.getLogger(__name__)


@dataclass
class TechnicalIndicators:
    """Comprehensive technical indicators used by professional traders."""

    # Metadata
    timestamp: str
    instrument: str
    current_price: float
    timeframe: str = "1min"

    # === TREND INDICATORS ===
    # Moving Averages
    sma_10: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_10: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    wma_20: Optional[float] = None

    # === MOMENTUM INDICATORS ===
    rsi_14: Optional[float] = None
    rsi_9: Optional[float] = None  # Shorter RSI for scalping
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    williams_r: Optional[float] = None

    # MACD
    macd_value: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None

    # === VOLATILITY INDICATORS ===
    # Bollinger Bands
    bollinger_upper: Optional[float] = None
    bollinger_middle: Optional[float] = None
    bollinger_lower: Optional[float] = None
    bollinger_width: Optional[float] = None
    bollinger_percent_b: Optional[float] = None

    # ATR (Average True Range)
    atr_14: Optional[float] = None
    atr_20: Optional[float] = None

    # === TREND STRENGTH ===
    adx_14: Optional[float] = None
    di_plus: Optional[float] = None
    di_minus: Optional[float] = None

    # Ichimoku Cloud
    ichimoku_tenkan: Optional[float] = None
    ichimoku_kijun: Optional[float] = None
    ichimoku_senkou_a: Optional[float] = None
    ichimoku_senkou_b: Optional[float] = None

    # === VOLUME INDICATORS ===
    obv: Optional[float] = None
    volume_sma_20: Optional[float] = None
    volume_rsi_14: Optional[float] = None
    cmf_20: Optional[float] = None  # Chaikin Money Flow

    # === OSCILLATORS ===
    cci_20: Optional[float] = None  # Commodity Channel Index
    mfi_14: Optional[float] = None  # Money Flow Index
    roc_12: Optional[float] = None  # Rate of Change
    momentum_10: Optional[float] = None

    # === SUPPORT/RESISTANCE ===
    pivot_point: Optional[float] = None
    pivot_r1: Optional[float] = None
    pivot_r2: Optional[float] = None
    pivot_s1: Optional[float] = None
    pivot_s2: Optional[float] = None

    # === PRICE ACTION ===
    high_20: Optional[float] = None  # 20-period high
    low_20: Optional[float] = None   # 20-period low
    range_20: Optional[float] = None # 20-period range

    # === SIGNAL STRENGTH ===
    signal_strength: Optional[float] = None  # Composite signal (0-100)
    adx_14: Optional[float] = None
    
    # Volume Indicators
    volume_sma_20: Optional[float] = None
    volume_ratio: Optional[float] = None
    
    # Support/Resistance
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    
    # Derived Signals
    trend_direction: str = "SIDEWAYS"  # UP, DOWN, SIDEWAYS
    trend_strength: float = 0.0  # 0-100
    rsi_status: str = "NEUTRAL"  # OVERSOLD, OVERBOUGHT, NEUTRAL
    volatility_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class TechnicalIndicatorsService:
    """Pandas-based technical indicators calculation service for professional traders.

    This service uses pandas and pandas-ta to calculate comprehensive technical indicators
    on OHLC data. Maintains rolling windows of data for real-time indicator calculation.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None, window_size: int = 200):
        """Initialize technical indicators service.

        Args:
            redis_client: Redis client for caching indicators
            window_size: Number of candles to maintain for calculations (default 200 for robust indicators)
        """
        self.redis_client = redis_client
        self.window_size = window_size
        self._ohlc_data: Dict[str, pd.DataFrame] = {}  # instrument -> OHLC DataFrame
        self._data_windows: Dict[str, deque] = {}  # instrument -> deque of ticks (for tick-based updates)
        self._latest_indicators: Dict[str, TechnicalIndicators] = {}
        
    def update_tick(self, instrument: str, tick: Dict[str, Any]) -> TechnicalIndicators:
        """Update indicators based on new market tick.
        
        This should be called on EVERY market tick to keep indicators up-to-date.
        
        Args:
            instrument: Instrument symbol (e.g., "BANKNIFTY")
            tick: Tick data with last_price, volume, timestamp
            
        Returns:
            Updated TechnicalIndicators object
        """
        # Initialize window if needed
        if instrument not in self._data_windows:
            self._data_windows[instrument] = deque(maxlen=self.window_size)
        
        # Add tick to window (will be used for next candle)
        # For real-time, we aggregate ticks into candles
        # For now, assume tick represents a completed candle
        self._data_windows[instrument].append(tick)
        
        # Calculate indicators
        indicators = self._calculate_all_indicators(instrument)
        
        # Store latest
        self._latest_indicators[instrument] = indicators
        
        return indicators
    
    def update_candle(self, instrument: str, candle: Dict[str, Any]) -> TechnicalIndicators:
        """Update indicators based on new OHLC candle using pandas.

        Args:
            instrument: Instrument symbol
            candle: OHLC data with open, high, low, close, volume, timestamp

        Returns:
            Updated TechnicalIndicators object
        """
        # Initialize DataFrame if needed
        if instrument not in self._ohlc_data:
            self._ohlc_data[instrument] = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        # Add new candle to DataFrame
        new_row = {
            'timestamp': pd.to_datetime(candle['start_at']) if isinstance(candle.get('start_at'), str)
                        else pd.to_datetime(candle['timestamp']),
            'open': candle['open'],
            'high': candle['high'],
            'low': candle['low'],
            'close': candle['close'],
            'volume': candle.get('volume', 0)
        }

        # Append to DataFrame and maintain window size
        self._ohlc_data[instrument].loc[len(self._ohlc_data[instrument])] = new_row
        if len(self._ohlc_data[instrument]) > self.window_size:
            self._ohlc_data[instrument] = self._ohlc_data[instrument].tail(self.window_size)

        # Calculate all indicators
        indicators = self._calculate_all_indicators(instrument)

        # Store latest
        self._latest_indicators[instrument] = indicators

        # Cache in Redis if available
        if self.redis_client:
            try:
                indicators_dict = asdict(indicators)
                for key, value in indicators_dict.items():
                    if value is not None:
                        self.redis_client.setex(f"indicators:{instrument}:{key}", 300, str(value))
            except Exception as e:
                logger.warning(f"Failed to cache indicators in Redis: {e}")

        return indicators
    
    def get_indicators(self, instrument: str) -> Optional[TechnicalIndicators]:
        """Get latest pre-calculated indicators for instrument.
        
        This is the API that agents call to get technical indicators.
        
        Args:
            instrument: Instrument symbol
            
        Returns:
            Latest TechnicalIndicators or None if not available
        """
        return self._latest_indicators.get(instrument)
    
    def get_indicators_dict(self, instrument: str) -> Dict[str, Any]:
        """Get latest indicators as dictionary.

        Args:
            instrument: Instrument symbol

        Returns:
            Dictionary of indicators or empty dict
        """
        indicators = self._latest_indicators.get(instrument)
        if not indicators:
            return {}

        # Convert dataclass to dict, filtering out None values
        result = {}
        for key, value in asdict(indicators).items():
            if value is not None:
                result[key] = value
        return result
    
    def _calculate_all_indicators(self, instrument: str) -> TechnicalIndicators:
        """Calculate comprehensive technical indicators using pandas and pandas-ta.

        Args:
            instrument: Instrument symbol

        Returns:
            Complete TechnicalIndicators object with all calculated indicators
        """
        df = self._ohlc_data.get(instrument)
        if df is None or len(df) < 20:  # Minimum data required
            current_price = float(df["close"].iloc[-1]) if df is not None and len(df) > 0 else 0.0
            return TechnicalIndicators(
                timestamp=datetime.now().isoformat(),
                instrument=instrument,
                current_price=current_price
            )

        current_price = float(df["close"].iloc[-1])

        indicators = TechnicalIndicators(
            timestamp=datetime.now().isoformat(),
            instrument=instrument,
            current_price=current_price
        )

        try:
            # === TREND INDICATORS ===
            # Moving Averages
            if len(df) >= 10:
                indicators.sma_10 = self._safe_float(ta.sma(df["close"], length=10))
                indicators.ema_10 = self._safe_float(ta.ema(df["close"], length=10))

            if len(df) >= 20:
                indicators.sma_20 = self._safe_float(ta.sma(df["close"], length=20))
                indicators.ema_20 = self._safe_float(ta.ema(df["close"], length=20))
                indicators.wma_20 = self._safe_float(ta.wma(df["close"], length=20))

            if len(df) >= 50:
                indicators.sma_50 = self._safe_float(ta.sma(df["close"], length=50))
                indicators.ema_50 = self._safe_float(ta.ema(df["close"], length=50))

            # === MOMENTUM INDICATORS ===
            if len(df) >= 14:
                indicators.rsi_14 = self._safe_float(ta.rsi(df["close"], length=14))

            if len(df) >= 9:
                indicators.rsi_9 = self._safe_float(ta.rsi(df["close"], length=9))

            if len(df) >= 14:
                stoch = ta.stoch(df["high"], df["low"], df["close"])
                if stoch is not None and len(stoch.columns) >= 2:
                    indicators.stoch_k = self._safe_float(stoch.iloc[:, 0])  # STOCHk
                    indicators.stoch_d = self._safe_float(stoch.iloc[:, 1])  # STOCHd

                indicators.williams_r = self._safe_float(ta.willr(df["high"], df["low"], df["close"], length=14))

            # MACD
            if len(df) >= 26:
                macd = ta.macd(df["close"])
                if macd is not None and len(macd.columns) >= 3:
                    indicators.macd_value = self._safe_float(macd.iloc[:, 0])    # MACD
                    indicators.macd_signal = self._safe_float(macd.iloc[:, 1])   # MACDh
                    indicators.macd_histogram = self._safe_float(macd.iloc[:, 2]) # MACDs

            # === VOLATILITY INDICATORS ===
            # Bollinger Bands
            if len(df) >= 20:
                bb = ta.bbands(df["close"], length=20)
                if bb is not None and len(bb.columns) >= 3:
                    indicators.bollinger_upper = self._safe_float(bb.iloc[:, 0])   # BBL
                    indicators.bollinger_middle = self._safe_float(bb.iloc[:, 1])  # BBM
                    indicators.bollinger_lower = self._safe_float(bb.iloc[:, 2])   # BBU
                    # Calculate width and %B
                    if indicators.bollinger_upper and indicators.bollinger_lower and indicators.bollinger_middle:
                        indicators.bollinger_width = (indicators.bollinger_upper - indicators.bollinger_lower) / indicators.bollinger_middle
                        indicators.bollinger_percent_b = (current_price - indicators.bollinger_lower) / (indicators.bollinger_upper - indicators.bollinger_lower) if (indicators.bollinger_upper - indicators.bollinger_lower) != 0 else 0

            # ATR
            if len(df) >= 14:
                indicators.atr_14 = self._safe_float(ta.atr(df["high"], df["low"], df["close"], length=14))

            if len(df) >= 20:
                indicators.atr_20 = self._safe_float(ta.atr(df["high"], df["low"], df["close"], length=20))

            # === TREND STRENGTH ===
            if len(df) >= 14:
                adx = ta.adx(df["high"], df["low"], df["close"], length=14)
                if adx is not None and len(adx.columns) >= 3:
                    indicators.adx_14 = self._safe_float(adx.iloc[:, 0])    # ADX
                    indicators.di_plus = self._safe_float(adx.iloc[:, 1])  # DMP
                    indicators.di_minus = self._safe_float(adx.iloc[:, 2]) # DMN

            # Ichimoku Cloud (requires minimum data)
            if len(df) >= 52:
                ichimoku = ta.ichimoku(df["high"], df["low"], df["close"])
                # ichimoku can return a tuple or DataFrame - handle both
                if ichimoku is not None:
                    if isinstance(ichimoku, tuple):
                        # If tuple, skip ichimoku for now
                        pass
                    elif hasattr(ichimoku, 'columns') and len(ichimoku.columns) >= 5:
                        indicators.ichimoku_tenkan = self._safe_float(ichimoku.iloc[:, 0])   # TENKAN
                        indicators.ichimoku_kijun = self._safe_float(ichimoku.iloc[:, 1])    # KIJUN
                        indicators.ichimoku_senkou_a = self._safe_float(ichimoku.iloc[:, 3]) # SENKOU_A
                        indicators.ichimoku_senkou_b = self._safe_float(ichimoku.iloc[:, 4]) # SENKOU_B

            # === VOLUME INDICATORS ===
            if len(df) >= 1:
                indicators.obv = self._safe_float(ta.obv(df["close"], df["volume"]))

            if len(df) >= 20:
                indicators.volume_sma_20 = self._safe_float(ta.sma(df["volume"], length=20))
                indicators.volume_rsi_14 = self._safe_float(ta.rsi(df["volume"], length=14))

            if len(df) >= 20:
                indicators.cmf_20 = self._safe_float(ta.cmf(df["high"], df["low"], df["close"], df["volume"], length=20))

            # === OSCILLATORS ===
            if len(df) >= 20:
                indicators.cci_20 = self._safe_float(ta.cci(df["high"], df["low"], df["close"], length=20))

            if len(df) >= 14:
                indicators.mfi_14 = self._safe_float(ta.mfi(df["high"], df["low"], df["close"], df["volume"], length=14))

            if len(df) >= 12:
                indicators.roc_12 = self._safe_float(ta.roc(df["close"], length=12))

            if len(df) >= 10:
                indicators.momentum_10 = self._safe_float(ta.mom(df["close"], length=10))

            # === SUPPORT/RESISTANCE ===
            if len(df) >= 1:
                # Use previous day's OHLC for pivot points (simplified)
                prev_day = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
                pivot_base = (prev_day["high"] + prev_day["low"] + prev_day["close"]) / 3
                indicators.pivot_point = pivot_base
                indicators.pivot_r1 = 2 * pivot_base - prev_day["low"]
                indicators.pivot_r2 = pivot_base + (prev_day["high"] - prev_day["low"])
                indicators.pivot_s1 = 2 * pivot_base - prev_day["high"]
                indicators.pivot_s2 = pivot_base - (prev_day["high"] - prev_day["low"])

            # === PRICE ACTION ===
            if len(df) >= 20:
                indicators.high_20 = float(df["high"].tail(20).max())
                indicators.low_20 = float(df["low"].tail(20).min())
                indicators.range_20 = indicators.high_20 - indicators.low_20

            # === SIGNAL STRENGTH ===
            # Composite signal based on multiple indicators (0-100 scale)
            signal_score = 0
            signal_count = 0

            # RSI signals (30-70 range is neutral)
            if indicators.rsi_14:
                signal_count += 1
                if indicators.rsi_14 < 30:
                    signal_score += 100  # Oversold
                elif indicators.rsi_14 > 70:
                    signal_score += 0    # Overbought
                else:
                    signal_score += 50   # Neutral

            # MACD signals
            if indicators.macd_histogram:
                signal_count += 1
                if indicators.macd_histogram > 0:
                    signal_score += 75  # Bullish momentum
                else:
                    signal_score += 25  # Bearish momentum

            # Bollinger Band position
            if indicators.bollinger_percent_b:
                signal_count += 1
                if indicators.bollinger_percent_b < 0.2:
                    signal_score += 100  # Near lower band (potential bounce)
                elif indicators.bollinger_percent_b > 0.8:
                    signal_score += 0    # Near upper band (potential reversal)
                else:
                    signal_score += 50   # Middle range

            # ADX trend strength
            if indicators.adx_14:
                signal_count += 1
                if indicators.adx_14 > 25:
                    signal_score += 80  # Strong trend
                else:
                    signal_score += 30  # Weak trend

            indicators.signal_strength = signal_score / max(signal_count, 1)

        except Exception as e:
            logger.error(f"Error calculating indicators for {instrument}: {e}", exc_info=True)

        return indicators

    def _safe_float(self, series_or_value) -> Optional[float]:
        """Safely extract float value from pandas Series or return None."""
        try:
            if hasattr(series_or_value, 'iloc'):
                # It's a Series
                if not series_or_value.empty:
                    value = series_or_value.iloc[-1]
                    return float(value) if pd.notna(value) else None
            else:
                # It's a scalar
                return float(series_or_value) if series_or_value is not None and pd.notna(series_or_value) else None
        except (ValueError, TypeError, IndexError):
            return None
            if macd is not None and not macd.empty:
                indicators.macd_value = float(macd["MACD_12_26_9"].iloc[-1]) if pd.notna(macd["MACD_12_26_9"].iloc[-1]) else None
                indicators.macd_signal = float(macd["MACDs_12_26_9"].iloc[-1]) if pd.notna(macd["MACDs_12_26_9"].iloc[-1]) else None
                indicators.macd_histogram = float(macd["MACDh_12_26_9"].iloc[-1]) if pd.notna(macd["MACDh_12_26_9"].iloc[-1]) else None
            
            # === VOLATILITY INDICATORS ===
            atr = ta.atr(df["high"], df["low"], df["close"], length=14)
            if not atr.empty and pd.notna(atr.iloc[-1]):
                indicators.atr_14 = float(atr.iloc[-1])
                
                # Volatility level
                atr_pct = (indicators.atr_14 / current_price) * 100
                if atr_pct < 1.0:
                    indicators.volatility_level = "LOW"
                elif atr_pct > 2.5:
                    indicators.volatility_level = "HIGH"
                else:
                    indicators.volatility_level = "MEDIUM"
            
            # Bollinger Bands
            bbands = ta.bbands(df["close"], length=20, std=2)
            if bbands is not None and not bbands.empty:
                # Handle different column naming (BBU_20_2.0 or similar)
                cols = bbands.columns
                upper_col = [c for c in cols if 'BBU' in c][0] if any('BBU' in c for c in cols) else None
                middle_col = [c for c in cols if 'BBM' in c][0] if any('BBM' in c for c in cols) else None
                lower_col = [c for c in cols if 'BBL' in c][0] if any('BBL' in c for c in cols) else None
                
                if upper_col and pd.notna(bbands[upper_col].iloc[-1]):
                    indicators.bollinger_upper = float(bbands[upper_col].iloc[-1])
                if middle_col and pd.notna(bbands[middle_col].iloc[-1]):
                    indicators.bollinger_middle = float(bbands[middle_col].iloc[-1])
                if lower_col and pd.notna(bbands[lower_col].iloc[-1]):
                    indicators.bollinger_lower = float(bbands[lower_col].iloc[-1])
            
            # === TREND STRENGTH ===
            adx_result = ta.adx(df["high"], df["low"], df["close"], length=14)
            if adx_result is not None and not adx_result.empty and "ADX_14" in adx_result.columns:
                indicators.adx_14 = float(adx_result["ADX_14"].iloc[-1]) if pd.notna(adx_result["ADX_14"].iloc[-1]) else None
            
            # === VOLUME INDICATORS ===
            if "volume" in df.columns:
                vol_sma = ta.sma(df["volume"], length=20)
                if not vol_sma.empty and pd.notna(vol_sma.iloc[-1]):
                    indicators.volume_sma_20 = float(vol_sma.iloc[-1])
                    current_vol = float(df["volume"].iloc[-1])
                    indicators.volume_ratio = current_vol / indicators.volume_sma_20 if indicators.volume_sma_20 > 0 else 1.0
            
            # === SUPPORT/RESISTANCE ===
            lookback = min(20, len(df))
            indicators.support_level = float(df["low"].tail(lookback).min())
            indicators.resistance_level = float(df["high"].tail(lookback).max())
            
            # === TREND DIRECTION ===
            if indicators.sma_20 is not None:
                if current_price > indicators.sma_20 * 1.005:  # 0.5% above
                    indicators.trend_direction = "UP"
                    indicators.trend_strength = min(100, ((current_price - indicators.sma_20) / indicators.sma_20 * 100) * 10)
                elif current_price < indicators.sma_20 * 0.995:  # 0.5% below
                    indicators.trend_direction = "DOWN"
                    indicators.trend_strength = min(100, ((indicators.sma_20 - current_price) / current_price * 100) * 10)
                else:
                    indicators.trend_direction = "SIDEWAYS"
                    indicators.trend_strength = 30.0
            
        except Exception as e:
            logger.warning(f"Error calculating indicators for {instrument}: {e}")
        
        return indicators
    
    def get_indicators_dict(self, instrument: str) -> Dict[str, Any]:
        """Get latest indicators as dictionary for specified instrument.
        
        This is a convenience method for agents that prefer dict format.
        
        Args:
            instrument: Instrument symbol
            
        Returns:
            Dictionary of technical indicators or empty dict if not available
        """
        indicators = self.get_indicators(instrument)
        return indicators.to_dict() if indicators else {}
    
    def get_raw_data(self, instrument: str, periods: int = 50) -> List[Dict[str, Any]]:
        """Get raw OHLCV data for instrument.
        
        Args:
            instrument: Instrument symbol
            periods: Number of periods to return
            
        Returns:
            List of OHLCV dictionaries
        """
        window = self._data_windows.get(instrument, deque())
        return list(window)[-periods:]


# Singleton instance for global access
_technical_service: Optional[TechnicalIndicatorsService] = None


def get_technical_service() -> TechnicalIndicatorsService:
    """Get global technical indicators service instance.
    
    Returns:
        Singleton TechnicalIndicatorsService instance
    """
    global _technical_service
    if _technical_service is None:
        _technical_service = TechnicalIndicatorsService()
    return _technical_service

