"""Minimal automatic trading service placeholder.

This keeps the container healthy while integrating with future
trade-execution logic. It wires expected async methods used by the
runner, logging heartbeats instead of placing trades.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AutomaticTradingService:
    def __init__(self, user_id: str = "paper_trader_user_id", instrument: str = "BANKNIFTY") -> None:
        self.user_id = user_id
        self.instrument = instrument

    async def initialize(self) -> None:
        logger.info("AutomaticTradingService initialized for user=%s instrument=%s", self.user_id, self.instrument)

    async def start_automatic_trading(self) -> None:
        logger.info("AutomaticTradingService started (no-op placeholder)")
        while True:
            await asyncio.sleep(30)
            logger.info("Heartbeat: automatic trading placeholder active for %s", self.instrument)


async def _main() -> None:  # pragma: no cover
    service = AutomaticTradingService()
    await service.initialize()
    await service.start_automatic_trading()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_main())
