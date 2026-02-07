"""Mock/synthetic replay source wrapper."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from market_data.adapters.unified_replayer import UnifiedHistoricalReplayer
from market_data.contracts import MarketStore


class MockSource(UnifiedHistoricalReplayer):
    """Alias for UnifiedHistoricalReplayer with synthetic source."""


def build_mock_source(
    store: MarketStore,
    instrument_symbol: str = "NIFTY BANK",
    speed: float = 1.0,
    rebase: bool = True,
    rebase_to: Optional[datetime] = None,
) -> MockSource:
    return MockSource(
        store=store,
        data_source="synthetic",
        instrument_symbol=instrument_symbol,
        speed=speed,
        rebase=rebase,
        rebase_to=rebase_to,
    )
