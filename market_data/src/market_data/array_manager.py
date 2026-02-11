"""Array manager for time series and technical indicators (inspired by VN.py).

Provides:
- Rolling window time series storage using numpy arrays
- Efficient indicator calculation using TA-Lib
- Clean interface for strategy development

Usage:
    am = ArrayManager(size=100)
    
    # Update with bars
    am.update_bar(bar)
    
    # Calculate indicators
    if am.inited:
        sma = am.sma(20)
        rsi = am.rsi(14)
        mom = am.mom(10)
"""

import logging
from typing import Optional, overload, Literal
import numpy as np

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    talib = None

from .contracts import OHLCBar

logger = logging.getLogger(__name__)


class ArrayManager:
    """Time series container for bar data with indicator calculation.
    
    Based on VN.py's ArrayManager:
    - Stores last N bars in numpy arrays
    - Provides efficient vectorized calculations
    - Integrates with TA-Lib for indicators
    - Rolling window automatically manages memory
    
    Example:
        am = ArrayManager(size=100)
        
        for bar in bars:
            am.update_bar(bar)
        
        if am.inited:
            # Calculate indicators
            ma20 = am.sma(20)
            rsi14 = am.rsi(14)
            momentum = am.mom(10)
            
            # Get time series
            closes = am.close  # Last 100 close prices
            highs = am.high
    """
    
    def __init__(self, size: int = 100):
        """Initialize array manager.
        
        Args:
            size: Number of bars to store (default: 100)
        """
        self.count = 0
        self.size = size
        self.inited = False
        
        # Initialize numpy arrays for OHLCV data
        self.open_array: np.ndarray = np.zeros(size)
        self.high_array: np.ndarray = np.zeros(size)
        self.low_array: np.ndarray = np.zeros(size)
        self.close_array: np.ndarray = np.zeros(size)
        self.volume_array: np.ndarray = np.zeros(size)
        
        if not TALIB_AVAILABLE:
            logger.warning("TA-Lib not available - indicator calculations will fail")
    
    def update_bar(self, bar: OHLCBar):
        """Update new bar data into array manager.
        
        Uses rolling window: oldest bar is dropped, newest added.
        
        Args:
            bar: OHLC bar to add
        """
        self.count += 1
        if not self.inited and self.count >= self.size:
            self.inited = True
        
        # Shift arrays left (remove oldest)
        self.open_array[:-1] = self.open_array[1:]
        self.high_array[:-1] = self.high_array[1:]
        self.low_array[:-1] = self.low_array[1:]
        self.close_array[:-1] = self.close_array[1:]
        self.volume_array[:-1] = self.volume_array[1:]
        
        # Add new bar at end
        self.open_array[-1] = bar.open
        self.high_array[-1] = bar.high
        self.low_array[-1] = bar.low
        self.close_array[-1] = bar.close
        self.volume_array[-1] = bar.volume if bar.volume else 0
    
    @property
    def open(self) -> np.ndarray:
        """Get open price time series."""
        return self.open_array
    
    @property
    def high(self) -> np.ndarray:
        """Get high price time series."""
        return self.high_array
    
    @property
    def low(self) -> np.ndarray:
        """Get low price time series."""
        return self.low_array
    
    @property
    def close(self) -> np.ndarray:
        """Get close price time series."""
        return self.close_array
    
    @property
    def volume(self) -> np.ndarray:
        """Get volume time series."""
        return self.volume_array
    
    # ===================================================================
    # Moving Averages
    # ===================================================================
    
    @overload
    def sma(self, n: int, array: Literal[False] = False) -> float: ...
    @overload
    def sma(self, n: int, array: Literal[True]) -> np.ndarray: ...
    
    def sma(self, n: int, array: bool = False) -> float | np.ndarray:
        """Simple Moving Average.
        
        Args:
            n: Period
            array: If True, return full array; if False, return latest value
            
        Returns:
            SMA value(s)
        """
        if not TALIB_AVAILABLE:
            raise RuntimeError("TA-Lib not available")
        
        result = talib.SMA(self.close, n)
        if array:
            return result
        return result[-1]
    
    @overload
    def ema(self, n: int, array: Literal[False] = False) -> float: ...
    @overload
    def ema(self, n: int, array: Literal[True]) -> np.ndarray: ...
    
    def ema(self, n: int, array: bool = False) -> float | np.ndarray:
        """Exponential Moving Average.
        
        Args:
            n: Period
            array: If True, return full array; if False, return latest value
            
        Returns:
            EMA value(s)
        """
        if not TALIB_AVAILABLE:
            raise RuntimeError("TA-Lib not available")
        
        result = talib.EMA(self.close, n)
        if array:
            return result
        return result[-1]
    
    # ===================================================================
    # Momentum Indicators
    # ===================================================================
    
    @overload
    def mom(self, n: int, array: Literal[False] = False) -> float: ...
    @overload
    def mom(self, n: int, array: Literal[True]) -> np.ndarray: ...
    
    def mom(self, n: int, array: bool = False) -> float | np.ndarray:
        """Momentum indicator.
        
        MOM = Close[today] - Close[n periods ago]
        Measures rate of price change.
        
        Args:
            n: Lookback period
            array: If True, return full array; if False, return latest value
            
        Returns:
            Momentum value(s)
        """
        if not TALIB_AVAILABLE:
            raise RuntimeError("TA-Lib not available")
        
        result = talib.MOM(self.close, n)
        if array:
            return result
        return result[-1]
    
    @overload
    def rsi(self, n: int, array: Literal[False] = False) -> float: ...
    @overload
    def rsi(self, n: int, array: Literal[True]) -> np.ndarray: ...
    
    def rsi(self, n: int, array: bool = False) -> float | np.ndarray:
        """Relative Strength Index.
        
        Momentum oscillator ranging from 0 to 100.
        - > 70: Overbought
        - < 30: Oversold
        
        Args:
            n: Period (typically 14)
            array: If True, return full array; if False, return latest value
            
        Returns:
            RSI value(s)
        """
        if not TALIB_AVAILABLE:
            raise RuntimeError("TA-Lib not available")
        
        result = talib.RSI(self.close, n)
        if array:
            return result
        return result[-1]
    
    @overload
    def cmo(self, n: int, array: Literal[False] = False) -> float: ...
    @overload
    def cmo(self, n: int, array: Literal[True]) -> np.ndarray: ...
    
    def cmo(self, n: int, array: bool = False) -> float | np.ndarray:
        """Chande Momentum Oscillator.
        
        Momentum indicator ranging from -100 to +100.
        
        Args:
            n: Period
            array: If True, return full array; if False, return latest value
            
        Returns:
            CMO value(s)
        """
        if not TALIB_AVAILABLE:
            raise RuntimeError("TA-Lib not available")
        
        result = talib.CMO(self.close, n)
        if array:
            return result
        return result[-1]
    
    @overload
    def roc(self, n: int, array: Literal[False] = False) -> float: ...
    @overload
    def roc(self, n: int, array: Literal[True]) -> np.ndarray: ...
    
    def roc(self, n: int, array: bool = False) -> float | np.ndarray:
        """Rate of Change.
        
        ROC = ((Close - Close[n]) / Close[n]) * 100
        
        Args:
            n: Lookback period
            array: If True, return full array; if False, return latest value
            
        Returns:
            ROC value(s)
        """
        if not TALIB_AVAILABLE:
            raise RuntimeError("TA-Lib not available")
        
        result = talib.ROC(self.close, n)
        if array:
            return result
        return result[-1]
    
    # ===================================================================
    # MACD
    # ===================================================================
    
    def macd(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        array: bool = False
    ) -> tuple[float | np.ndarray, float | np.ndarray, float | np.ndarray]:
        """Moving Average Convergence Divergence.
        
        Returns three values:
        - MACD line: EMA(fast) - EMA(slow)
        - Signal line: EMA of MACD line
        - Histogram: MACD - Signal
        
        Args:
            fast_period: Fast EMA period (default: 12)
            slow_period: Slow EMA period (default: 26)
            signal_period: Signal line period (default: 9)
            array: If True, return full arrays; if False, return latest values
            
        Returns:
            Tuple of (macd, signal, histogram)
        """
        if not TALIB_AVAILABLE:
            raise RuntimeError("TA-Lib not available")
        
        macd, signal, hist = talib.MACD(
            self.close,
            fast_period,
            slow_period,
            signal_period
        )
        
        if array:
            return macd, signal, hist
        return macd[-1], signal[-1], hist[-1]
    
    # ===================================================================
    # Bollinger Bands
    # ===================================================================
    
    def boll(
        self,
        n: int = 20,
        dev: float = 2.0,
        array: bool = False
    ) -> tuple[float | np.ndarray, float | np.ndarray, float | np.ndarray]:
        """Bollinger Bands.
        
        Returns three values:
        - Upper band: SMA + (dev * stddev)
        - Middle band: SMA
        - Lower band: SMA - (dev * stddev)
        
        Args:
            n: Period (default: 20)
            dev: Standard deviation multiplier (default: 2.0)
            array: If True, return full arrays; if False, return latest values
            
        Returns:
            Tuple of (upper, middle, lower)
        """
        if not TALIB_AVAILABLE:
            raise RuntimeError("TA-Lib not available")
        
        upper, middle, lower = talib.BBANDS(
            self.close,
            n,
            dev,
            dev,
            0
        )
        
        if array:
            return upper, middle, lower
        return upper[-1], middle[-1], lower[-1]
    
    # ===================================================================
    # Volatility Indicators
    # ===================================================================
    
    @overload
    def atr(self, n: int, array: Literal[False] = False) -> float: ...
    @overload
    def atr(self, n: int, array: Literal[True]) -> np.ndarray: ...
    
    def atr(self, n: int, array: bool = False) -> float | np.ndarray:
        """Average True Range.
        
        Measures market volatility.
        
        Args:
            n: Period (typically 14)
            array: If True, return full array; if False, return latest value
            
        Returns:
            ATR value(s)
        """
        if not TALIB_AVAILABLE:
            raise RuntimeError("TA-Lib not available")
        
        result = talib.ATR(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]
    
    # ===================================================================
    # Trend Indicators
    # ===================================================================
    
    @overload
    def cci(self, n: int, array: Literal[False] = False) -> float: ...
    @overload
    def cci(self, n: int, array: Literal[True]) -> np.ndarray: ...
    
    def cci(self, n: int, array: bool = False) -> float | np.ndarray:
        """Commodity Channel Index.
        
        Momentum-based oscillator.
        - > +100: Overbought
        - < -100: Oversold
        
        Args:
            n: Period
            array: If True, return full array; if False, return latest value
            
        Returns:
            CCI value(s)
        """
        if not TALIB_AVAILABLE:
            raise RuntimeError("TA-Lib not available")
        
        result = talib.CCI(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]
    
    @overload
    def adx(self, n: int, array: Literal[False] = False) -> float: ...
    @overload
    def adx(self, n: int, array: Literal[True]) -> np.ndarray: ...
    
    def adx(self, n: int, array: bool = False) -> float | np.ndarray:
        """Average Directional Index.
        
        Measures trend strength (not direction).
        - < 25: Weak/no trend
        - > 50: Strong trend
        
        Args:
            n: Period (typically 14)
            array: If True, return full array; if False, return latest value
            
        Returns:
            ADX value(s)
        """
        if not TALIB_AVAILABLE:
            raise RuntimeError("TA-Lib not available")
        
        result = talib.ADX(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]
    
    # ===================================================================
    # Helper Methods
    # ===================================================================
    
    def __repr__(self) -> str:
        return f"ArrayManager(size={self.size}, count={self.count}, inited={self.inited})"
