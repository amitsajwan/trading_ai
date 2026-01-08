"""Contracts for news data handling and processing."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, List


@dataclass
class NewsItem:
    """Individual news article with metadata and sentiment."""

    title: str
    content: str
    source: str
    published_at: datetime
    summary: Optional[str] = None
    url: Optional[str] = None
    sentiment_score: Optional[float] = None  # -1.0 to 1.0
    relevance_score: Optional[float] = None  # 0.0 to 1.0
    instruments: List[str] = None  # Related instruments/symbols
    tags: List[str] = None  # Category tags
    author: Optional[str] = None
    language: str = "en"

    def __post_init__(self):
        if self.instruments is None:
            self.instruments = []
        if self.tags is None:
            self.tags = []


@dataclass
class NewsSentimentSummary:
    """Aggregated sentiment analysis for a time period."""

    instrument: str
    time_period_hours: int
    average_sentiment: float
    sentiment_trend: str  # "bullish", "bearish", "neutral"
    article_count: int
    positive_count: int
    negative_count: int
    neutral_count: int
    top_positive_headlines: List[str]
    top_negative_headlines: List[str]


class NewsCollector(Protocol):
    """Protocol for news data collection."""

    async def collect_news(self, sources: List[str] = None, limit: int = 100) -> List[NewsItem]:
        """Collect news from specified sources."""
        ...

    async def collect_news_for_instrument(self, instrument: str, limit: int = 50) -> List[NewsItem]:
        """Collect news specifically related to an instrument."""
        ...


class NewsStorage(Protocol):
    """Protocol for news data persistence."""

    async def store_news_item(self, news_item: NewsItem) -> bool:
        """Store a single news item."""
        ...

    async def store_news_batch(self, news_items: List[NewsItem]) -> int:
        """Store multiple news items. Returns count stored."""
        ...

    async def get_news_for_instrument(self, instrument: str, limit: int = 50,
                                    hours_back: int = 24) -> List[NewsItem]:
        """Retrieve news for a specific instrument."""
        ...

    async def get_news_by_sentiment(self, instrument: str, min_sentiment: float = None,
                                  max_sentiment: float = None, limit: int = 50) -> List[NewsItem]:
        """Retrieve news filtered by sentiment range."""
        ...


class SentimentAnalyzer(Protocol):
    """Protocol for sentiment analysis of news content."""

    async def analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment of text. Returns score from -1.0 (negative) to 1.0 (positive)."""
        ...

    async def analyze_news_item(self, news_item: NewsItem) -> NewsItem:
        """Analyze sentiment of a news item and update its sentiment_score."""
        ...


class NewsData(Protocol):
    """Main protocol for news data access and processing."""

    async def get_latest_news(self, instrument: str = None, limit: int = 10) -> List[NewsItem]:
        """Get latest news, optionally filtered by instrument."""
        ...

    async def get_sentiment_summary(self, instrument: str, hours: int = 24) -> NewsSentimentSummary:
        """Get sentiment summary for an instrument over time period."""
        ...

    async def search_news(self, query: str, instrument: str = None, limit: int = 20) -> List[NewsItem]:
        """Search news by text query."""
        ...


@dataclass
class NewsSource:
    """Configuration for a news source."""

    name: str
    url: str
    type: str  # "rss", "api", "scraper"
    update_interval_minutes: int = 15
    enabled: bool = True
    categories: List[str] = None

    def __post_init__(self):
        if self.categories is None:
            self.categories = []


@dataclass
class NewsCollectionConfig:
    """Configuration for news collection system."""

    sources: List[NewsSource]
    max_articles_per_source: int = 100
    sentiment_analysis_enabled: bool = True
    storage_retention_days: int = 30
    collection_interval_minutes: int = 10