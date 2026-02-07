"""Historical replay source wrapper."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Callable, Any

from market_data.adapters.unified_replayer import UnifiedHistoricalReplayer
from market_data.contracts import MarketStore, MarketTick


class HistoricalSource(UnifiedHistoricalReplayer):
    """Alias for UnifiedHistoricalReplayer."""


def build_historical_source(
    store: MarketStore,
    data_source: str,
    speed: float = 0.0,
    on_tick_callback: Optional[Callable[[MarketTick], None]] = None,
    on_candle_callback: Optional[Callable[[Any], None]] = None,
    kite=None,
    instrument_symbol: str = "NIFTY BANK",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    interval: str = "minute",
    rebase: bool = False,
    rebase_to: Optional[datetime] = None,
    loop: bool = False,
    start_date: Optional[datetime] = None,
) -> HistoricalSource:
    return HistoricalSource(
        store=store,
        data_source=data_source,
        speed=speed,
        on_tick_callback=on_tick_callback,
        on_candle_callback=on_candle_callback,
        kite=kite,
        instrument_symbol=instrument_symbol,
        from_date=from_date,
        to_date=to_date,
        interval=interval,
        rebase=rebase,
        rebase_to=rebase_to,
        loop=loop,
        start_date=start_date,
    )
