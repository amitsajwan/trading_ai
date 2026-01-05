"""Zerodha options chain adapter using the legacy OptionsChainFetcher.

This wrapper keeps dependencies injected so the data_niftybank module stays independent.
"""
import logging
from typing import Optional

from ..aliases import normalize_instrument
from ..contracts import OptionsData

logger = logging.getLogger(__name__)


class ZerodhaOptionsChainAdapter(OptionsData):
    """Adapter that delegates to the existing OptionsChainFetcher."""

    def __init__(self, fetcher, instrument_symbol: str = "NIFTY BANK"):
        # Instrument is normalized to canonical form, but the legacy fetcher
        # handles BANKNIFTY/NIFTY prefixes internally.
        self.instrument_symbol = normalize_instrument(instrument_symbol)
        self.fetcher = fetcher
        # Ensure fetcher sees a consistent symbol string
        try:
            setattr(self.fetcher, "instrument_symbol", self.instrument_symbol)
        except Exception:  # noqa: BLE001
            pass

    async def initialize(self) -> None:
        try:
            await self.fetcher.initialize()
        except Exception as exc:  # noqa: BLE001
            logger.error("OptionsChainFetcher init failed: %s", exc)
            raise

    async def fetch_options_chain(self, strikes: Optional[list[int]] = None) -> dict:
        try:
            return await self.fetcher.fetch_options_chain(strikes=strikes)
        except Exception as exc:  # noqa: BLE001
            logger.error("OptionsChainFetcher fetch failed: %s", exc)
            return {"available": False, "reason": "fetch_error", "error": str(exc)}
