"""Bar generator for tick-to-bar aggregation (inspired by VN.py).

Converts streaming tick data into OHLC bars with support for:
- 1-minute bar generation from ticks
- Multi-timeframe bar generation (X-minute, X-hour from 1-minute bars)
- Callback-based architecture for clean separation

Usage:
    # Simple: 1-minute bars only
    bg = BarGenerator(on_bar_callback)
    bg.update_tick(tick)
    
    # Multi-timeframe: 1-min → 15-min bars
    bg = BarGenerator(
        on_bar=on_1min_bar,
        window=15,
        on_window_bar=on_15min_bar
    )
"""

import logging
from datetime import datetime, time, timedelta
from typing import Optional, Callable
from enum import Enum

from .contracts import MarketTick, OHLCBar

logger = logging.getLogger(__name__)


class Interval(Enum):
    """Time interval enumeration."""
    MINUTE = "1m"
    HOUR = "1h"
    DAILY = "1d"


class BarGenerator:
    """Generate OHLC bars from tick data.
    
    Based on VN.py's BarGenerator with enhancements:
    1. Generates 1-minute bars from tick data
    2. Generates X-minute bars from 1-minute bars (2, 3, 5, 6, 10, 15, 20, 30)
    3. Generates X-hour bars from 1-minute bars (any X)
    4. Clean callback architecture
    
    Requirements:
    - X-minute bars: X must divide 60 evenly (2, 3, 5, 6, 10, 15, 20, 30)
    - X-hour bars: any X is supported
    
    Example:
        # 1-minute bars only
        bg = BarGenerator(on_bar)
        
        # 15-minute bars from 1-minute bars
        bg = BarGenerator(on_bar, window=15, on_window_bar=on_15min_bar)
        
        # 2-hour bars
        bg = BarGenerator(
            on_bar,
            window=2,
            on_window_bar=on_2hour_bar,
            interval=Interval.HOUR
        )
    """
    
    def __init__(
        self,
        on_bar: Callable[[OHLCBar], None],
        window: int = 0,
        on_window_bar: Optional[Callable[[OHLCBar], None]] = None,
        interval: Interval = Interval.MINUTE,
    ):
        """Initialize bar generator.
        
        Args:
            on_bar: Callback for 1-minute bars
            window: Window size for aggregation (0 = no windowing)
            on_window_bar: Callback for window bars (X-minute or X-hour)
            interval: Window interval type (MINUTE or HOUR)
        """
        self.on_bar = on_bar
        self.window = window
        self.on_window_bar = on_window_bar
        self.interval = interval
        
        # Current 1-minute bar being built
        self.bar: Optional[OHLCBar] = None
        
        # Last tick for volume differencing
        self.last_tick: Optional[MarketTick] = None
        
        # Window bar for X-minute aggregation
        self.window_bar: Optional[OHLCBar] = None
        
        # Hour bar for hour-based aggregation
        self.hour_bar: Optional[OHLCBar] = None
        
        # Interval counter for multi-hour bars
        self.interval_count = 0
        
        logger.info(
            f"BarGenerator initialized: window={window}, interval={interval.value if window else 'N/A'}"
        )
    
    def update_tick(self, tick: MarketTick):
        """Update tick data into bar generator.
        
        This is the main entry point for live tick data.
        Automatically creates/closes 1-minute bars as needed.
        
        Args:
            tick: Market tick data
        """
        new_minute = False
        
        # Filter ticks with zero last price
        if not tick.last_price or tick.last_price <= 0:
            return
        
        logger.info(f"BarGenerator: Processing tick {tick.instrument} @ {tick.timestamp} (price: {tick.last_price})")
        
        # Check if we need to create a new bar
        if not self.bar:
            new_minute = True
            logger.info("BarGenerator: No current bar, creating new one")
        elif self._is_new_minute(tick.timestamp):
            # Close existing bar
            self.bar.end_at = tick.timestamp
            logger.info(f"BarGenerator: Closing bar at {tick.timestamp}, calling on_bar")
            self.on_bar(self.bar)
            new_minute = True
        
        # Create new bar
        if new_minute:
            self.bar = OHLCBar(
                instrument=tick.instrument,
                timeframe="1m",
                open=tick.last_price,
                high=tick.last_price,
                low=tick.last_price,
                close=tick.last_price,
                volume=0,
                open_interest=tick.open_interest,
                start_at=self._floor_to_minute(tick.timestamp),
                end_at=tick.timestamp
            )
            logger.info(f"BarGenerator: Created new bar starting at {self.bar.start_at}")
        # Update existing bar
        elif self.bar:
            self.bar.high = max(self.bar.high, tick.last_price)
            self.bar.low = min(self.bar.low, tick.last_price)
            self.bar.close = tick.last_price
            self.bar.end_at = tick.timestamp
            if tick.open_interest is not None:
                self.bar.open_interest = tick.open_interest
            logger.info(f"BarGenerator: Updated existing bar, close={self.bar.close}")
        
        # Update volume (handle cumulative volume from exchange)
        if self.last_tick and self.bar:
            volume_change = tick.volume - self.last_tick.volume
            if volume_change > 0:
                self.bar.volume += volume_change

        # Always keep latest open interest on the bar
        if self.bar and tick.open_interest is not None:
            self.bar.open_interest = tick.open_interest
        
        self.last_tick = tick
    
    def update_bar(self, bar: OHLCBar):
        """Update 1-minute bar into window generator.
        
        Use this to generate X-minute or X-hour bars from 1-minute bars.
        
        Args:
            bar: 1-minute OHLC bar
        """
        if self.window == 0:
            return
        
        if self.interval == Interval.MINUTE:
            self.update_bar_minute_window(bar)
        elif self.interval == Interval.HOUR:
            self.update_bar_hour_window(bar)
    
    def update_bar_minute_window(self, bar: OHLCBar):
        """Generate X-minute bars from 1-minute bars.
        
        Args:
            bar: 1-minute bar
        """
        # Create window bar if needed
        if not self.window_bar:
            dt = bar.start_at.replace(second=0, microsecond=0)
            self.window_bar = OHLCBar(
                instrument=bar.instrument,
                timeframe=f"{self.window}m",
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                open_interest=bar.open_interest,
                start_at=dt,
                end_at=bar.end_at
            )
        # Update existing window bar
        else:
            self.window_bar.high = max(self.window_bar.high, bar.high)
            self.window_bar.low = min(self.window_bar.low, bar.low)
            self.window_bar.close = bar.close
            self.window_bar.volume += bar.volume
            self.window_bar.end_at = bar.end_at
            if bar.open_interest is not None:
                self.window_bar.open_interest = bar.open_interest
        
        # Check if window completed
        if not (bar.start_at.minute + 1) % self.window:
            if self.on_window_bar:
                self.on_window_bar(self.window_bar)
            self.window_bar = None
    
    def update_bar_hour_window(self, bar: OHLCBar):
        """Generate X-hour bars from 1-minute bars.
        
        Args:
            bar: 1-minute bar
        """
        # Create hour bar if needed
        if not self.hour_bar:
            dt = bar.start_at.replace(minute=0, second=0, microsecond=0)
            self.hour_bar = OHLCBar(
                instrument=bar.instrument,
                timeframe=f"{self.window}h",
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                open_interest=bar.open_interest,
                start_at=dt,
                end_at=bar.end_at
            )
            return
        
        finished_bar: Optional[OHLCBar] = None
        
        # Check if hour completed (minute == 59)
        if bar.start_at.minute == 59:
            self.hour_bar.high = max(self.hour_bar.high, bar.high)
            self.hour_bar.low = min(self.hour_bar.low, bar.low)
            self.hour_bar.close = bar.close
            self.hour_bar.volume += bar.volume
            self.hour_bar.end_at = bar.end_at
            if bar.open_interest is not None:
                self.hour_bar.open_interest = bar.open_interest
            
            finished_bar = self.hour_bar
            self.hour_bar = None
        
        # Check if new hour started
        elif bar.start_at.hour != self.hour_bar.start_at.hour:
            finished_bar = self.hour_bar
            
            dt = bar.start_at.replace(minute=0, second=0, microsecond=0)
            self.hour_bar = OHLCBar(
                instrument=bar.instrument,
                timeframe=f"{self.window}h",
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                open_interest=bar.open_interest,
                start_at=dt,
                end_at=bar.end_at
            )
        
        # Update current hour bar
        else:
            self.hour_bar.high = max(self.hour_bar.high, bar.high)
            self.hour_bar.low = min(self.hour_bar.low, bar.low)
            self.hour_bar.close = bar.close
            self.hour_bar.volume += bar.volume
            self.hour_bar.end_at = bar.end_at
        
        # Emit finished bar
        if finished_bar:
            self._on_hour_bar(finished_bar)
    
    def _on_hour_bar(self, bar: OHLCBar):
        """Handle hour bar completion."""
        if self.window == 1:
            # Single hour bar, emit directly
            if self.on_window_bar:
                self.on_window_bar(bar)
        else:
            # Multi-hour aggregation
            if not self.window_bar:
                self.window_bar = OHLCBar(
                    instrument=bar.instrument,
                    timeframe=f"{self.window}h",
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    start_at=bar.start_at,
                    end_at=bar.end_at
                )
            else:
                self.window_bar.high = max(self.window_bar.high, bar.high)
                self.window_bar.low = min(self.window_bar.low, bar.low)
                self.window_bar.close = bar.close
                self.window_bar.volume += bar.volume
                self.window_bar.end_at = bar.end_at
            
            self.interval_count += 1
            if not self.interval_count % self.window:
                if self.on_window_bar:
                    self.on_window_bar(self.window_bar)
                
                self.interval_count = 0
                self.window_bar = None
    
    def generate(self) -> Optional[OHLCBar]:
        """Force generate current bar.
        
        Useful for end-of-day processing or testing.
        
        Returns:
            Current bar if exists, None otherwise
        """
        bar = self.bar
        
        if bar:
            bar.end_at = bar.end_at.replace(second=0, microsecond=0)
            self.on_bar(bar)
            self.bar = None
        
        return bar
    
    def _is_new_minute(self, timestamp: datetime) -> bool:
        """Check if timestamp represents a new minute.
        
        Args:
            timestamp: Current timestamp
            
        Returns:
            True if new minute started
        """
        if not self.bar:
            return True
        
        return (
            self.bar.start_at.minute != timestamp.minute or
            self.bar.start_at.hour != timestamp.hour
        )
    
    def _floor_to_minute(self, timestamp: datetime) -> datetime:
        """Floor timestamp to minute boundary.
        
        Args:
            timestamp: Timestamp to floor
            
        Returns:
            Timestamp floored to minute
        """
        return timestamp.replace(second=0, microsecond=0)
