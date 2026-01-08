"""Tests for news module components."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from news_module.contracts import NewsItem, NewsSentimentSummary
from news_module.adapters.sentiment_analyzer import BasicSentimentAnalyzer
from news_module.adapters.news_data_adapter import NewsDataAdapter


class TestBasicSentimentAnalyzer:
    """Test basic sentiment analysis functionality."""

    @pytest.fixture
    def analyzer(self):
        return BasicSentimentAnalyzer()

    @pytest.mark.asyncio
    async def test_positive_sentiment(self, analyzer):
        """Test positive sentiment detection."""
        text = "NIFTY surges to new highs on strong earnings"
        score = await analyzer.analyze_sentiment(text)
        assert score > 0.1

    @pytest.mark.asyncio
    async def test_negative_sentiment(self, analyzer):
        """Test negative sentiment detection."""
        text = "Market crashes as investors panic sell"
        score = await analyzer.analyze_sentiment(text)
        assert score < -0.1

    @pytest.mark.asyncio
    async def test_neutral_sentiment(self, analyzer):
        """Test neutral sentiment detection."""
        text = "NIFTY opens at 22000 points"
        score = await analyzer.analyze_sentiment(text)
        assert -0.1 <= score <= 0.1

    @pytest.mark.asyncio
    async def test_intensifiers(self, analyzer):
        """Test intensifier word handling."""
        text = "NIFTY rises very strongly today"
        score = await analyzer.analyze_sentiment(text)
        assert score > 0.3  # Should be higher due to "very strongly"

    @pytest.mark.asyncio
    async def test_analyze_news_item(self, analyzer):
        """Test full news item analysis."""
        news_item = NewsItem(
            title="NIFTY gains 2%",
            content="The index showed strong performance today",
            source="test",
            published_at=datetime.now()
        )

        result = await analyzer.analyze_news_item(news_item)
        assert result.sentiment_score is not None
        assert result.sentiment_score > 0
        assert result.title == news_item.title


class TestNewsDataAdapter:
    """Test news data adapter functionality."""

    @pytest.fixture
    def mock_collector(self):
        collector = MagicMock()
        collector.collect_news = AsyncMock(return_value=[])
        collector.collect_news_for_instrument = AsyncMock(return_value=[])
        return collector

    @pytest.fixture
    def mock_storage(self):
        storage = MagicMock()
        storage.get_news_for_instrument = AsyncMock(return_value=[])
        storage.store_news_batch = AsyncMock(return_value=0)
        return storage

    @pytest.fixture
    def adapter(self, mock_collector, mock_storage):
        return NewsDataAdapter(mock_collector, mock_storage)

    @pytest.mark.asyncio
    async def test_get_latest_news_no_instrument(self, adapter, mock_storage):
        """Test getting latest news without instrument filter."""
        mock_storage.get_news_for_instrument.return_value = [
            NewsItem(
                title="Test News",
                content="Test content",
                source="test",
                published_at=datetime.now(),
                sentiment_score=0.5
            )
        ]

        news = await adapter.get_latest_news(limit=5)
        assert isinstance(news, list)

    @pytest.mark.asyncio
    async def test_get_sentiment_summary_empty(self, adapter, mock_storage):
        """Test sentiment summary with no news."""
        mock_storage.get_news_for_instrument.return_value = []

        summary = await adapter.get_sentiment_summary("NIFTY", hours=24)
        assert isinstance(summary, NewsSentimentSummary)
        assert summary.instrument == "NIFTY"
        assert summary.article_count == 0
        assert summary.average_sentiment == 0.0
        assert summary.sentiment_trend == "neutral"

    @pytest.mark.asyncio
    async def test_get_sentiment_summary_with_data(self, adapter, mock_storage):
        """Test sentiment summary with news data."""
        news_items = [
            NewsItem(
                title="Positive news",
                content="Good content",
                source="test",
                published_at=datetime.now(),
                sentiment_score=0.8
            ),
            NewsItem(
                title="Negative news",
                content="Bad content",
                source="test",
                published_at=datetime.now(),
                sentiment_score=-0.6
            )
        ]

        mock_storage.get_news_for_instrument.return_value = news_items

        summary = await adapter.get_sentiment_summary("NIFTY", hours=24)
        assert summary.article_count == 2
        assert summary.average_sentiment == 0.1  # (0.8 + (-0.6)) / 2
        assert summary.positive_count == 1
        assert summary.negative_count == 1
        assert summary.sentiment_trend == "neutral"  # Close to 0

    @pytest.mark.asyncio
    async def test_search_news(self, adapter, mock_storage):
        """Test news search functionality."""
        news_items = [
            NewsItem(
                title="NIFTY surges",
                content="Market is up",
                source="test",
                published_at=datetime.now(),
                sentiment_score=0.5
            )
        ]

        mock_storage.get_news_for_instrument.return_value = news_items

        results = await adapter.search_news("surges", instrument="NIFTY")
        assert len(results) == 1
        assert "surges" in results[0].title