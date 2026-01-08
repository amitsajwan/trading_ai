"""Candle builder that aggregates ticks into OHLC bars.

This is the SAME code used for both live and historical data.
Strategy should NOT know whether ticks come from WebSocket or CSV.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Callable
from collections import defaultdict

from ..contracts import MarketTick, OHLCBar

logger = logging.getLogger(__name__)


class CandleBuilder:
    """Builds OHLC candles from market ticks.
    
    This aggregates ticks into time-based candles (1min, 5min, etc.)
    and emits OHLCBar objects when candles close.
    """
    
    def __init__(
        self,
        timeframe: str = "1min",
        on_candle_close: Optional[Callable[[OHLCBar], None]] = None
    ):
        """Initialize candle builder.
        
        Args:
            timeframe: Candle timeframe ("1min", "5min", "15min", etc.)
            on_candle_close: Callback function called when a candle closes
        """
        self.timeframe = timeframe
        self.on_candle_close = on_candle_close
        
        # Parse timeframe
        self.timeframe_seconds = self._parse_timeframe(timeframe)
        
        # Active candles per instrument: {instrument: {timeframe_key: CandleData}}
        self._active_candles: Dict[str, Dict[str, 'CandleData']] = defaultdict(dict)
        
    def _parse_timeframe(self, timeframe: str) -> int:
        """Parse timeframe string to seconds."""
        timeframe = timeframe.lower()
        
        if timeframe.endswith('min'):
            minutes = int(timeframe[:-3])
            return minutes * 60
        elif timeframe.endswith('h'):
            hours = int(timeframe[:-1])
            return hours * 3600
        elif timeframe.endswith('d'):
            days = int(timeframe[:-1])
            return days * 86400
        else:
            # Default to 1 minute
            return 60
    
    def process_tick(self, tick: MarketTick) -> Optional[OHLCBar]:
        """Process a market tick and update/close candles.
        
        Args:
            tick: MarketTick to process
            
        Returns:
            OHLCBar if a candle closed, None otherwise
        """
        instrument = tick.instrument
        
        # Calculate which candle this tick belongs to
        candle_key = self._get_candle_key(tick.timestamp)
        
        # Get or create active candle
        if candle_key not in self._active_candles[instrument]:
            # Check if we need to close previous candle
            closed_candle = self._check_and_close_candle(instrument, tick.timestamp)
            
            # Create new candle
            self._active_candles[instrument][candle_key] = CandleData(
                instrument=instrument,
                timeframe=self.timeframe,
                start_time=self._get_candle_start_time(tick.timestamp)
            )
        
        # Update active candle with tick
        candle = self._active_candles[instrument][candle_key]
        candle.update(tick)
        
        # Check if candle should close
        if self._should_close_candle(tick.timestamp, candle.start_time):
            return self._close_candle(instrument, candle_key)
        
        return None
    
    def _get_candle_key(self, timestamp: datetime) -> str:
        """Get unique key for candle based on timestamp."""
        start_time = self._get_candle_start_time(timestamp)
        return start_time.isoformat()
    
    def _get_candle_start_time(self, timestamp: datetime) -> datetime:
        """Get the start time of the candle containing this timestamp."""
        # Round down to candle boundary
        total_seconds = int(timestamp.timestamp())
        candle_start_seconds = (total_seconds // self.timeframe_seconds) * self.timeframe_seconds
        return datetime.fromtimestamp(candle_start_seconds, tz=timestamp.tzinfo)
    
    def _should_close_candle(self, current_time: datetime, candle_start: datetime) -> bool:
        """Check if candle should close based on time."""
        elapsed = (current_time - candle_start).total_seconds()
        return elapsed >= self.timeframe_seconds
    
    def _check_and_close_candle(self, instrument: str, new_tick_time: datetime) -> Optional[OHLCBar]:
        """Check if any previous candle should be closed before starting new one."""
        closed = None
        
        # Find candles that should be closed
        to_close = []
        for candle_key, candle in self._active_candles[instrument].items():
            if self._should_close_candle(new_tick_time, candle.start_time):
                to_close.append(candle_key)
        
        # Close them
        for candle_key in to_close:
            closed = self._close_candle(instrument, candle_key)
        
        return closed
    
    def _close_candle(self, instrument: str, candle_key: str) -> OHLCBar:
        """Close a candle and emit OHLCBar."""
        candle = self._active_candles[instrument].pop(candle_key)
        
        ohlc_bar = OHLCBar(
            instrument=candle.instrument,
            timeframe=self.timeframe,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
            start_at=candle.start_time
        )
        
        # Call callback if provided
        if self.on_candle_close:
            try:
                if callable(self.on_candle_close):
                    self.on_candle_close(ohlc_bar)
            except Exception as e:
                logger.error(f"Error in candle close callback: {e}")
        
        logger.debug(f"Closed {self.timeframe} candle for {instrument}: O={ohlc_bar.open} H={ohlc_bar.high} L={ohlc_bar.low} C={ohlc_bar.close}")
        
        return ohlc_bar
    
    def get_active_candle(self, instrument: str) -> Optional['CandleData']:
        """Get current active candle for instrument (for debugging)."""
        candles = self._active_candles.get(instrument, {})
        if candles:
            # Return most recent candle
            return max(candles.values(), key=lambda c: c.start_time)
        return None
    
    def force_close_all(self) -> List[OHLCBar]:
        """Force close all active candles (useful at end of day)."""
        closed = []
        
        for instrument in list(self._active_candles.keys()):
            for candle_key in list(self._active_candles[instrument].keys()):
                ohlc = self._close_candle(instrument, candle_key)
                if ohlc:
                    closed.append(ohlc)
        
        return closed


class CandleData:
    """Internal data structure for building a candle."""
    
    def __init__(self, instrument: str, timeframe: str, start_time: datetime):
        self.instrument = instrument
        self.timeframe = timeframe
        self.start_time = start_time
        
        self.open: Optional[float] = None
        self.high: Optional[float] = None
        self.low: Optional[float] = None
        self.close: Optional[float] = None
        self.volume: int = 0
        self.tick_count: int = 0
    
    def update(self, tick: MarketTick):
        """Update candle with new tick."""
        price = tick.last_price
        
        # Set open on first tick
        if self.open is None:
            self.open = price
            self.high = price
            self.low = price
        
        # Update high/low
        if self.high is None or price > self.high:
            self.high = price
        if self.low is None or price < self.low:
            self.low = price
        
        # Close is always latest price
        self.close = price
        
        # Accumulate volume
        if tick.volume:
            self.volume += tick.volume
        
        self.tick_count += 1


