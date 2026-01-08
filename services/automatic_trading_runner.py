"""Container-friendly entrypoint for automatic trading service.

Runs the AutomaticTradingService in a continuous loop, reading basic
configuration from environment variables so it can be orchestrated via
Docker Compose.
"""

from __future__ import annotations

import asyncio
import os

from automatic_trading_service import AutomaticTradingService


async def main() -> None:
    user_id = os.getenv("AUTOTRADE_USER_ID", "paper_trader_user_id")
    instrument = os.getenv("AUTOTRADE_INSTRUMENT", "BANKNIFTY")

    service = AutomaticTradingService(user_id=user_id, instrument=instrument)

    # Initialize components (Mongo, user module, orchestrator, etc.)
    await service.initialize()

    # Run continuous automatic trading until container is stopped
    await service.start_automatic_trading()


if __name__ == "__main__":  # pragma: no cover - container entrypoint
    asyncio.run(main())

