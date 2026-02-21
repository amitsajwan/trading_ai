"""In-memory implementation of the MarketStore contract."""
from collections import defaultdict, deque
from datetime import timedelta
from typing import Deque, Dict, Iterable, List, Optional

from .contracts import MarketStore, MarketTick, OHLCBar


class InMemoryMarketStore(MarketStore):
    """Lightweight store for ticks and OHLC bars (test-friendly)."""

    def __init__(self, max_bars: int = 1000):
        self._ticks: Dict[str, MarketTick] = {}
        self._ohlc: Dict[str, Dict[str, Deque[OHLCBar]]] = defaultdict(lambda: defaultdict(deque))
        self._max_bars = max_bars

    def store_tick(self, tick: MarketTick) -> None:
        self._ticks[tick.instrument] = tick

        # Keep a lightweight 1-minute OHLC stream for test/offline parity with
        # RedisMarketStore, which builds candles from ticks.
        bucket_start = tick.timestamp.replace(second=0, microsecond=0)
        bucket_end = bucket_start + timedelta(minutes=1)
        tf = "1min"

        series = self._ohlc[tick.instrument][tf]
        if series and series[-1].start_at == bucket_start:
            bar = series[-1]
            bar.high = max(bar.high, tick.last_price)
            bar.low = min(bar.low, tick.last_price)
            bar.close = tick.last_price
            bar.volume = (bar.volume or 0) + (tick.volume or 0)
            if tick.open_interest is not None:
                bar.open_interest = tick.open_interest
        else:
            series.append(
                OHLCBar(
                    instrument=tick.instrument,
                    timeframe=tf,
                    open=tick.last_price,
                    high=tick.last_price,
                    low=tick.last_price,
                    close=tick.last_price,
                    volume=tick.volume or 0,
                    start_at=bucket_start,
                    end_at=bucket_end,
                    open_interest=tick.open_interest,
                )
            )
            if len(series) > self._max_bars:
                series.popleft()

    def get_latest_tick(self, instrument: str) -> Optional[MarketTick]:
        return self._ticks.get(instrument)

    def store_ohlc(self, bar: OHLCBar) -> None:
        series = self._ohlc[bar.instrument][bar.timeframe]
        series.append(bar)
        if len(series) > self._max_bars:
            series.popleft()

    def get_ohlc(self, instrument: str, timeframe: str, limit: int = 100) -> Iterable[OHLCBar]:
        series = self._ohlc.get(instrument, {}).get(timeframe)
        if not series:
            return []
        if limit <= 0:
            return list(series)
        return list(series)[-limit:]

