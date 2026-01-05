"""Macro data adapter using legacy macro data fetchers.

This adapter provides macroeconomic data access for trading agents.
"""
import logging
from datetime import datetime
from typing import Optional

from ..contracts import MacroData, MacroIndicator

logger = logging.getLogger(__name__)


class MacroDataAdapter(MacroData):
    """Adapter that wraps macro data fetchers for MacroData protocol.

    Provides access to macroeconomic indicators like inflation,
    RBI data, and other economic metrics.
    """

    def __init__(self):
        """Initialize macro data adapter."""
        self.macro_fetcher = None

    async def get_inflation_data(self, months: int = 12) -> list[MacroIndicator]:
        """Get inflation data for the specified period.

        Args:
            months: Number of months of data to retrieve

        Returns:
            List of MacroIndicator objects for inflation data
        """
        # Use mock data for offline testing
        # TODO: Integrate with actual macro data fetcher when available

        try:
            # Get inflation data from the fetcher
            raw_data = await self._get_inflation_from_fetcher(months)

            indicators = []
            for item in raw_data:
                indicator = MacroIndicator(
                    name="CPI Inflation",
                    value=item.get("value", 0.0),
                    unit="percent",
                    timestamp=item.get("date", datetime.now()),
                    source="RBI/Ministry of Commerce"
                )
                indicators.append(indicator)

            return indicators

        except Exception as e:
            logger.error(f"Error fetching inflation data: {e}")
            return []

    async def get_rbi_data(self, indicator: str, days: int = 30) -> list[MacroIndicator]:
        """Get RBI indicator data for the specified period.

        Args:
            indicator: Name of the RBI indicator (e.g., "repo_rate", "crR")
            days: Number of days of data to retrieve

        Returns:
            List of MacroIndicator objects for the requested indicator
        """
        try:
            # Get RBI data from the appropriate scraper
            raw_data = await self._get_rbi_from_scraper(indicator, days)

            indicators = []
            for item in raw_data:
                indicator_obj = MacroIndicator(
                    name=indicator.replace("_", " ").title(),
                    value=item.get("value", 0.0),
                    unit=item.get("unit", "unit"),
                    timestamp=item.get("date", datetime.now()),
                    source="RBI"
                )
                indicators.append(indicator_obj)

            return indicators

        except Exception as e:
            logger.error(f"Error fetching RBI data for {indicator}: {e}")
            return []

    async def _get_inflation_from_fetcher(self, months: int):
        """Internal method to get inflation data."""
        # Use mock data for offline testing
        # TODO: Integrate with actual macro data fetcher when available
        return self._get_mock_inflation(months)

    async def _get_rbi_from_scraper(self, indicator: str, days: int):
        """Internal method to get RBI data."""
        # Use mock data for offline testing
        # TODO: Integrate with actual RBI scraper when available
        return self._get_mock_rbi(indicator, days)

    def _get_mock_inflation(self, months: int):
        """Return mock inflation data for testing."""
        return [
            {"value": 5.2, "date": "2024-01-01T00:00:00"},
            {"value": 5.1, "date": "2024-02-01T00:00:00"},
            {"value": 5.0, "date": "2024-03-01T00:00:00"}
        ][:months//4 + 1]

    def _get_mock_rbi(self, indicator: str, days: int):
        """Return mock RBI data for testing."""
        return [
            {"value": 6.5, "date": "2024-01-15T00:00:00", "unit": "percent"},
            {"value": 6.75, "date": "2024-02-15T00:00:00", "unit": "percent"}
        ][:days//30 + 1]

    async def _get_real_inflation(self, months: int):
        """Get inflation from real MacroDataFetcher (placeholder)."""
        # This would implement the actual macro data fetcher integration
        return self._get_mock_inflation(months)

    async def _get_real_rbi(self, indicator: str, days: int):
        """Get RBI data from real scraper (placeholder)."""
        # This would implement the actual RBI scraper integration
        return self._get_mock_rbi(indicator, days)
