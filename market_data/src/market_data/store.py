"""In-memory implementation of the MarketStore contract."""
from collections import defaultdict, deque
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

