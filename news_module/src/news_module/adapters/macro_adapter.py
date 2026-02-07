"""Macro data adapter moved to news_module for better separation.

Provides macroeconomic indicators for trading agents and the news module.
"""
import logging
from datetime import datetime
from typing import Optional

from market_data.contracts import MacroData, MacroIndicator
from .real_macro_fetcher import RealMacroDataFetcher

logger = logging.getLogger(__name__)


class MacroDataAdapter(MacroData):
    """Adapter that wraps macro data fetchers for MacroData protocol.

    Provides access to macroeconomic indicators like inflation,
    RBI data, and other economic metrics.
    """

    def __init__(self):
        """Initialize macro data adapter."""
        self.macro_fetcher = RealMacroDataFetcher()

    async def get_inflation_data(self, months: int = 12) -> list[MacroIndicator]:
        """Get inflation data for the specified period.

        Args:
            months: Number of months of data to retrieve

        Returns:
            List of MacroIndicator objects for inflation data
        """
        try:
            async with self.macro_fetcher:
                raw_data = await self.macro_fetcher.get_inflation_data(months)

            indicators = []
            for item in raw_data:
                indicator = MacroIndicator(
                    name="CPI Inflation",
                    value=item.get("value", 0.0),
                    unit="percent",
                    timestamp=datetime.fromisoformat(item.get("date", datetime.now().isoformat())),
                    source="Ministry of Statistics & Programme Implementation"
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
            async with self.macro_fetcher:
                if indicator == "repo_rate":
                    raw_data = await self.macro_fetcher.get_rbi_repo_rate(days)
                elif indicator == "reverse_repo_rate":
                    raw_data = await self.macro_fetcher.get_rbi_reverse_repo_rate(days)
                elif indicator == "npa_ratio":
                    # Convert days to quarters for NPA data
                    quarters = max(1, days // 90)
                    raw_data = await self.macro_fetcher.get_npa_ratio(quarters)
                elif indicator == "crR":
                    # Convert days to quarters for CRR data
                    quarters = max(1, days // 90)
                    raw_data = await self.macro_fetcher.get_crR_ratio(quarters)
                else:
                    raw_data = await self.macro_fetcher.get_rbi_repo_rate(days)  # Default to repo rate

            indicators = []
            for item in raw_data:
                indicator_obj = MacroIndicator(
                    name=indicator.replace("_", " ").title(),
                    value=item.get("value", 0.0),
                    unit=item.get("unit", "unit"),
                    timestamp=datetime.fromisoformat(item.get("date", datetime.now().isoformat())),
                    source="RBI"
                )
                indicators.append(indicator_obj)

            return indicators

        except Exception as e:
            logger.error(f"Error fetching RBI data for {indicator}: {e}")
            return []

