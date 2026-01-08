"""Standalone historical data replay service for Docker.

This wraps the dashboard's `start_historical_replay` helper so that
historical Zerodha/data_niftybank replays can be run as an independent
container when paper_mock mode is active.

Configuration is provided via environment variables:

- HISTORICAL_START_DATE: YYYY-MM-DD (required)
- HISTORICAL_END_DATE:   YYYY-MM-DD (optional, defaults to today)
- HISTORICAL_INTERVAL:   candle interval (default: "minute")

For full Zerodha historical data, ensure Kite authentication is
completed and credentials are available in the container, as described
in the main README.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

from dashboard.app import start_historical_replay


def _parse_date(value: str | None):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


async def main() -> None:
    start_str = os.getenv("HISTORICAL_START_DATE")
    end_str = os.getenv("HISTORICAL_END_DATE")
    interval = os.getenv("HISTORICAL_INTERVAL", "minute")

    if not start_str:
        raise SystemExit("HISTORICAL_START_DATE is required for historical replay service")

    start_date = _parse_date(start_str)
    end_date = _parse_date(end_str)

    # Start the historical replay flow. This function is resilient and
    # will fall back to synthetic data if Zerodha/data_niftybank are not
    # available, but in production you should provide a valid Kite client
    # via credentials inside the container.
    await start_historical_replay(start_date=start_date, end_date=end_date, interval=interval, kite=None)

    # Keep the service alive so the underlying replay flow can continue
    # to push data into Redis/market store.
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":  # pragma: no cover - container entrypoint
    asyncio.run(main())

