"""News data adapter using the legacy NewsCollector.

This adapter provides news and sentiment data access for trading agents.
"""
import logging
from datetime import datetime
from typing import Optional

from ..contracts import NewsData, NewsItem

logger = logging.getLogger(__name__)


class NewsDataAdapter(NewsData):
    """Adapter that wraps NewsCollector for NewsData protocol.

    Provides access to financial news and sentiment data collected
    from various sources (Finnhub, RSS feeds, etc.).
    """

    def __init__(self, market_memory):
        """Initialize with market memory dependency.

        Args:
            market_memory: MarketMemory instance for caching
        """
        self.market_memory = market_memory
        self.news_collector = None

    async def get_latest_news(self, instrument: str, limit: int = 10) -> list[NewsItem]:
        """Get latest news articles for an instrument.

        Args:
            instrument: Instrument symbol (e.g., "NIFTY", "BANKNIFTY")
            limit: Maximum number of articles to return

        Returns:
            List of NewsItem objects with sentiment scores
        """
        # Get news data (using mock data for offline testing)
        try:
            raw_news = await self._get_news_from_collector(instrument, limit)

            news_items = []
            for item in raw_news:
                news_item = NewsItem(
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    source=item.get("source", "unknown"),
                    published_at=item.get("published_at", datetime.now()) if isinstance(item.get("published_at"), str) else item.get("published_at", datetime.now()),
                    sentiment_score=item.get("sentiment_score"),
                    relevance_score=item.get("relevance_score")
                )
                news_items.append(news_item)

            return news_items

        except Exception as e:
            logger.error(f"Error fetching news for {instrument}: {e}")
            return []

    async def get_sentiment_summary(self, instrument: str, hours: int = 24) -> dict:
        """Get sentiment summary for an instrument over time period.

        Args:
            instrument: Instrument symbol
            hours: Time period in hours

        Returns:
            Dictionary with sentiment statistics
        """
        try:
            # Get sentiment data from collector
            # This would need to be implemented based on NewsCollector's API
            sentiment_data = await self._get_sentiment_from_collector(instrument, hours)

            return {
                "average_sentiment": sentiment_data.get("average", 0.0),
                "sentiment_trend": sentiment_data.get("trend", "neutral"),
                "article_count": sentiment_data.get("count", 0),
                "time_period_hours": hours
            }

        except Exception as e:
            logger.error(f"Error getting sentiment summary for {instrument}: {e}")
            return {
                "average_sentiment": 0.0,
                "sentiment_trend": "neutral",
                "article_count": 0,
                "time_period_hours": hours
            }

    async def _get_news_from_collector(self, instrument: str, limit: int):
        """Internal method to get news from NewsCollector."""
        # Use mock data for offline testing
        # TODO: Integrate with actual NewsCollector when available
        return self._get_mock_news(instrument, limit)

    async def _get_sentiment_from_collector(self, instrument: str, hours: int):
        """Internal method to get sentiment from NewsCollector."""
        # Use mock data for offline testing
        # TODO: Integrate with actual NewsCollector when available
        return self._get_mock_sentiment(instrument, hours)

    def _get_mock_news(self, instrument: str, limit: int):
        """Return mock news data for testing."""
        return [
            {
                "title": f"Mock news for {instrument}",
                "content": "Mock content for testing",
                "source": "Mock Source",
                "published_at": datetime.now().isoformat(),
                "sentiment_score": 0.5,
                "relevance_score": 0.8
            }
        ][:limit]

    def _get_mock_sentiment(self, instrument: str, hours: int):
        """Return mock sentiment data for testing."""
        return {"average": 0.5, "trend": "neutral", "count": 1}

    async def _get_real_news(self, instrument: str, limit: int):
        """Get news from real NewsCollector (placeholder)."""
        # This would implement the actual NewsCollector integration
        return self._get_mock_news(instrument, limit)

    async def _get_real_sentiment(self, instrument: str, hours: int):
        """Get sentiment from real NewsCollector (placeholder)."""
        # This would implement the actual NewsCollector integration
        return self._get_mock_sentiment(instrument, hours)
