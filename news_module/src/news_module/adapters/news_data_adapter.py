"""Main news data adapter combining collection, analysis, and storage."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from collections import defaultdict

from ..contracts import (
    NewsItem, NewsData, NewsSentimentSummary, NewsCollector,
    SentimentAnalyzer, NewsStorage, NewsSource
)
from .sentiment_analyzer import BasicSentimentAnalyzer

logger = logging.getLogger(__name__)


class NewsDataAdapter(NewsData):
    """Main adapter for news data operations."""

    def __init__(self,
                 collector: NewsCollector,
                 storage: NewsStorage,
                 sentiment_analyzer: Optional[SentimentAnalyzer] = None):
        """Initialize with dependencies.

        Args:
            collector: News collection implementation
            storage: News storage implementation
            sentiment_analyzer: Optional sentiment analysis (uses basic if None)
        """
        self.collector = collector
        self.storage = storage
        self.sentiment_analyzer = sentiment_analyzer or BasicSentimentAnalyzer()
        self._initialized = False

    async def _ensure_collector_initialized(self):
        """Ensure the collector is properly initialized."""
        if not self._initialized and hasattr(self.collector, '__aenter__'):
            await self.collector.__aenter__()
            self._initialized = True

    async def __aenter__(self):
        """Async context manager entry - initialize collector if needed."""
        await self._ensure_collector_initialized()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup collector."""
        if hasattr(self.collector, '__aexit__'):
            await self.collector.__aexit__(exc_type, exc_val, exc_tb)
        self._initialized = False

    async def get_latest_news(self, instrument: str = None, limit: int = 10) -> List[NewsItem]:
        """Get latest news, optionally filtered by instrument."""
        try:
            if instrument:
                # Get news for specific instrument
                news_items = await self.storage.get_news_for_instrument(
                    instrument, limit=limit, hours_back=24
                )

                # If not enough stored news, collect fresh news
                if len(news_items) < limit:
                    await self._ensure_collector_initialized()
                    fresh_news = await self.collector.collect_news_for_instrument(
                        instrument, limit=limit - len(news_items)
                    )

                    # Analyze sentiment and store
                    analyzed_news = []
                    for item in fresh_news:
                        analyzed_item = await self.sentiment_analyzer.analyze_news_item(item)
                        analyzed_news.append(analyzed_item)

                    if analyzed_news:
                        await self.storage.store_news_batch(analyzed_news)
                        news_items.extend(analyzed_news)

                return news_items[:limit]

            else:
                # Get general latest news from all sources
                # This is a simplified implementation - in practice you'd want
                # to collect from all sources and filter
                all_news = []

                # For now, get news for major instruments
                major_instruments = ["NIFTY", "BANKNIFTY", "RELIANCE", "TCS", "INFY"]

                for instr in major_instruments:
                    news = await self.storage.get_news_for_instrument(
                        instr, limit=limit // len(major_instruments), hours_back=24
                    )
                    all_news.extend(news)

                # Sort by published date
                all_news.sort(key=lambda x: x.published_at, reverse=True)
                return all_news[:limit]

        except Exception as e:
            logger.error(f"Failed to get latest news: {e}")
            return []

    async def get_sentiment_summary(self, instrument: str, hours: int = 24) -> NewsSentimentSummary:
        """Get sentiment summary for an instrument over time period."""
        try:
            # Get news for the instrument
            news_items = await self.storage.get_news_for_instrument(
                instrument, limit=1000, hours_back=hours
            )

            if not news_items:
                return NewsSentimentSummary(
                    instrument=instrument,
                    time_period_hours=hours,
                    average_sentiment=0.0,
                    sentiment_trend="neutral",
                    article_count=0,
                    positive_count=0,
                    negative_count=0,
                    neutral_count=0,
                    top_positive_headlines=[],
                    top_negative_headlines=[]
                )

            # Analyze sentiment distribution
            sentiments = [item.sentiment_score for item in news_items if item.sentiment_score is not None]

            if not sentiments:
                average_sentiment = 0.0
            else:
                average_sentiment = sum(sentiments) / len(sentiments)

            # Round for consistent comparison
            average_sentiment = round(average_sentiment, 3)

            # Categorize articles
            positive_count = sum(1 for s in sentiments if s > 0.1)
            negative_count = sum(1 for s in sentiments if s < -0.1)
            neutral_count = len(sentiments) - positive_count - negative_count

            # Determine trend
            if average_sentiment > 0.1:
                trend = "bullish"
            elif average_sentiment < -0.1:
                trend = "bearish"
            else:
                trend = "neutral"

            # Get top headlines
            positive_items = [item for item in news_items if item.sentiment_score and item.sentiment_score > 0.1]
            negative_items = [item for item in news_items if item.sentiment_score and item.sentiment_score < -0.1]

            top_positive = [item.title for item in positive_items[:3]]
            top_negative = [item.title for item in negative_items[:3]]

            return NewsSentimentSummary(
                instrument=instrument,
                time_period_hours=hours,
                average_sentiment=round(average_sentiment, 3),
                sentiment_trend=trend,
                article_count=len(news_items),
                positive_count=positive_count,
                negative_count=negative_count,
                neutral_count=neutral_count,
                top_positive_headlines=top_positive,
                top_negative_headlines=top_negative
            )

        except Exception as e:
            logger.error(f"Failed to get sentiment summary for {instrument}: {e}")
            return NewsSentimentSummary(
                instrument=instrument,
                time_period_hours=hours,
                average_sentiment=0.0,
                sentiment_trend="neutral",
                article_count=0,
                positive_count=0,
                negative_count=0,
                neutral_count=0,
                top_positive_headlines=[],
                top_negative_headlines=[]
            )

    async def search_news(self, query: str, instrument: str = None, limit: int = 20) -> List[NewsItem]:
        """Search news by text query."""
        try:
            # This is a simplified implementation
            # In practice, you'd want full-text search capabilities in MongoDB

            if instrument:
                # Search within instrument-specific news
                all_news = await self.storage.get_news_for_instrument(
                    instrument, limit=100, hours_back=168  # Last week
                )
            else:
                # Search across major instruments
                all_news = []
                major_instruments = ["NIFTY", "BANKNIFTY", "RELIANCE", "TCS", "INFY"]

                for instr in major_instruments:
                    news = await self.storage.get_news_for_instrument(
                        instr, limit=50, hours_back=168
                    )
                    all_news.extend(news)

            # Simple text matching (case-insensitive)
            query_lower = query.lower()
            matching_news = []

            for item in all_news:
                text = f"{item.title} {item.content}".lower()
                if query_lower in text:
                    matching_news.append(item)
                    if len(matching_news) >= limit:
                        break

            return matching_news

        except Exception as e:
            logger.error(f"Failed to search news: {e}")
            return []