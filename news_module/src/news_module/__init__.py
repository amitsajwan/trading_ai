"""News module for financial news collection and sentiment analysis."""

from .contracts import (
    NewsItem, NewsSentimentSummary, NewsSource, NewsCollectionConfig,
    NewsData, NewsCollector, NewsStorage, SentimentAnalyzer
)
from .store import MongoNewsStorage
from .collectors import RSSNewsCollector
from .adapters import BasicSentimentAnalyzer, AdvancedSentimentAnalyzer, NewsDataAdapter
from .api import (
    build_news_storage, build_news_collector, build_sentiment_analyzer,
    build_news_service, get_default_news_sources, collect_and_store_news
)

__version__ = "1.0.0"
__all__ = [
    # Core contracts
    "NewsItem", "NewsSentimentSummary", "NewsSource", "NewsCollectionConfig",
    "NewsData", "NewsCollector", "NewsStorage", "SentimentAnalyzer",

    # Implementations
    "MongoNewsStorage", "RSSNewsCollector",
    "BasicSentimentAnalyzer", "AdvancedSentimentAnalyzer", "NewsDataAdapter",

    # API functions
    "build_news_storage", "build_news_collector", "build_sentiment_analyzer",
    "build_news_service", "get_default_news_sources", "collect_and_store_news"
]