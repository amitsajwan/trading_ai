"""Candle builder that aggregates ticks into OHLC bars.

This is the same code used for both live and historical data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Callable
from collections import defaultdict

from market_data.contracts import MarketTick, OHLCBar

logger = logging.getLogger(__name__)


class CandleBuilder:
    """Builds OHLC candles from market ticks.

    Aggregates ticks into time-based candles and emits OHLCBar objects.
    """

    def __init__(
        self,
        timeframe: str = "1min",
        on_candle_close: Optional[Callable[[OHLCBar], None]] = None
    ):
        self.timeframe = timeframe
        self.on_candle_close = on_candle_close
        self.timeframe_seconds = self._parse_timeframe(timeframe)
        self._active_candles: Dict[str, Dict[str, 'CandleData']] = defaultdict(dict)

    def _parse_timeframe(self, timeframe: str) -> int:
        timeframe = timeframe.lower()

        if timeframe.endswith('min'):
            minutes = int(timeframe[:-3])
            return minutes * 60
        if timeframe.endswith('h'):
            hours = int(timeframe[:-1])
            return hours * 3600
        if timeframe.endswith('d'):
            days = int(timeframe[:-1])
            return days * 86400
        return 60

    def process_tick(self, tick: MarketTick) -> Optional[OHLCBar]:
        instrument = tick.instrument
        candle_key = self._get_candle_key(tick.timestamp)

        if candle_key not in self._active_candles[instrument]:
            self._check_and_close_candle(instrument, tick.timestamp)

            start_time = self._get_candle_start_time(tick.timestamp)
            self._active_candles[instrument][candle_key] = CandleData(
                instrument=instrument,
                timeframe=self.timeframe,
                start_time=start_time
            )
            logger.debug(f"Created new candle {candle_key} for {instrument} at {start_time}")

        candle = self._active_candles[instrument][candle_key]
        candle.update(tick)

        if self._should_close_candle(tick.timestamp, candle.start_time):
            logger.debug(
                f"Closing candle {candle_key} for {instrument} due to time: "
                f"{tick.timestamp} - {candle.start_time} = "
                f"{(tick.timestamp - candle.start_time).total_seconds()}s"
            )
            return self._close_candle(instrument, candle_key)

        if (tick.timestamp - candle.start_time).total_seconds() > self.timeframe_seconds * 2:
            logger.debug(
                f"Force closing old candle {candle_key} for {instrument}: "
                f"{tick.timestamp} - {candle.start_time} = "
                f"{(tick.timestamp - candle.start_time).total_seconds()}s"
            )
            return self._close_candle(instrument, candle_key)

        return None

    def _get_candle_key(self, timestamp: datetime) -> str:
        start_time = self._get_candle_start_time(timestamp)
        return start_time.isoformat()

    def _get_candle_start_time(self, timestamp: datetime) -> datetime:
        total_seconds = int(timestamp.timestamp())
        candle_start_seconds = (total_seconds // self.timeframe_seconds) * self.timeframe_seconds
        return datetime.fromtimestamp(candle_start_seconds, tz=timestamp.tzinfo)

    def _should_close_candle(self, current_time: datetime, candle_start: datetime) -> bool:
        elapsed = (current_time - candle_start).total_seconds()
        return elapsed >= self.timeframe_seconds

    def _check_and_close_candle(self, instrument: str, new_tick_time: datetime) -> Optional[OHLCBar]:
        closed = None
        to_close = []
        for candle_key, candle in self._active_candles[instrument].items():
            if self._should_close_candle(new_tick_time, candle.start_time):
                to_close.append(candle_key)

        for candle_key in to_close:
            closed = self._close_candle(instrument, candle_key)

        return closed

    def _close_candle(self, instrument: str, candle_key: str) -> OHLCBar:
        candle = self._active_candles[instrument].pop(candle_key)

        # Calculate end_at as start_time + timeframe
        end_at = candle.start_time + timedelta(seconds=self.timeframe_seconds)

        ohlc_bar = OHLCBar(
            instrument=candle.instrument,
            timeframe=self.timeframe,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
            start_at=candle.start_time,
            end_at=end_at
        )

        if self.on_candle_close:
            try:
                if callable(self.on_candle_close):
                    self.on_candle_close(ohlc_bar)
            except Exception as e:
                logger.error(f"Error in candle close callback: {e}")

        logger.debug(
            f"Closed {self.timeframe} candle for {instrument}: "
            f"O={ohlc_bar.open} H={ohlc_bar.high} L={ohlc_bar.low} C={ohlc_bar.close}"
        )

        return ohlc_bar

    def get_active_candle(self, instrument: str) -> Optional['CandleData']:
        candles = self._active_candles.get(instrument, {})
        if candles:
            return max(candles.values(), key=lambda c: c.start_time)
        return None

    def force_close_all(self) -> List[OHLCBar]:
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
        price = tick.last_price

        if self.open is None:
            self.open = price
            self.high = price
            self.low = price

        if self.high is None or price > self.high:
            self.high = price
        if self.low is None or price < self.low:
            self.low = price

        self.close = price

        if tick.volume:
            self.volume += tick.volume

        self.tick_count += 1


class OHLCBuilder(CandleBuilder):
    """Alias for CandleBuilder."""
