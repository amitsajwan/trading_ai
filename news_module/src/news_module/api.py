"""Public API for news module."""

from typing import Optional
from pymongo.collection import Collection

from .contracts import NewsData, NewsSource, NewsCollectionConfig
from .store import MongoNewsStorage
from .collectors import RSSNewsCollector
from .adapters import NewsDataAdapter, BasicSentimentAnalyzer

try:
    from .collectors.yfinance_collector import YFinanceNewsCollector
    YFINANCE_AVAILABLE = True
except ImportError:
    YFinanceNewsCollector = None
    YFINANCE_AVAILABLE = False


def build_news_collector(sources: Optional[list] = None) -> RSSNewsCollector:
    """Build RSS news collector with default sources.

    Args:
        sources: List of NewsSource objects. Uses defaults if None.

    Returns:
        RSSNewsCollector instance
    """
    if sources is None:
        sources = get_default_news_sources()
    return RSSNewsCollector(sources)


def build_news_storage(mongo_collection: Collection) -> MongoNewsStorage:
    """Build MongoDB-backed news storage.

    Args:
        mongo_collection: MongoDB collection for news storage

    Returns:
        MongoNewsStorage instance

    Example:
        from core_kernel.mongodb_schema import get_mongo_client, get_collection

        client = get_mongo_client()
        db = client["zerodha_trading"]
        collection = get_collection(db, "news")
        storage = build_news_storage(collection)
    """
    return MongoNewsStorage(mongo_collection)


def build_news_collector(sources: Optional[list] = None) -> RSSNewsCollector:
    """Build RSS news collector with default sources.

    Args:
        sources: Optional list of NewsSource objects. Uses defaults if None.

    Returns:
        RSSNewsCollector instance

    Example:
        collector = build_news_collector()
        async with collector:
            news = await collector.collect_news()
    """
    if sources is None:
        sources = get_default_news_sources()

    return RSSNewsCollector(sources)


def build_sentiment_analyzer(provider: str = "basic", api_key: Optional[str] = None):
    """Build sentiment analyzer.

    Args:
        provider: "basic" for rule-based, "openai" or "anthropic" for AI-powered
        api_key: API key for external providers

    Returns:
        SentimentAnalyzer instance
    """
    if provider == "basic":
        return BasicSentimentAnalyzer()
    elif provider in ["openai", "anthropic"]:
        from .adapters import AdvancedSentimentAnalyzer
        return AdvancedSentimentAnalyzer(api_key=api_key, provider=provider)
    else:
        raise ValueError(f"Unknown sentiment provider: {provider}")


def build_news_service(mongo_collection: Collection,
                      sentiment_provider: str = "basic",
                      api_key: Optional[str] = None,
                      use_yfinance: bool = True) -> NewsData:
    """Build complete news service with all components.

    Args:
        mongo_collection: MongoDB collection for storage
        sentiment_provider: Sentiment analysis provider
        api_key: API key for external sentiment providers
        use_yfinance: Whether to use yfinance collector (default: True)

    Returns:
        NewsData instance ready for use

    Example:
        from core_kernel.mongodb_schema import get_mongo_client, get_collection

        client = get_mongo_client()
        db = client["zerodha_trading"]
        collection = get_collection(db, "news")

        news_service = build_news_service(collection)

        # Get latest news
        news = await news_service.get_latest_news("NIFTY")

        # Get sentiment summary
        sentiment = await news_service.get_sentiment_summary("NIFTY")
    """
    # Build components
    storage = build_news_storage(mongo_collection)
    
    # Use yfinance collector if available, otherwise RSS
    if use_yfinance and YFINANCE_AVAILABLE and YFinanceNewsCollector is not None:
        collector = YFinanceNewsCollector()
    else:
        collector = build_news_collector()
    
    sentiment_analyzer = build_sentiment_analyzer(sentiment_provider, api_key)

    # Combine into main adapter
    return NewsDataAdapter(collector, storage, sentiment_analyzer)


def get_default_news_sources() -> list:
    """Get default news sources configuration.

    Returns:
        List of NewsSource objects for major Indian financial news
    """
    return [
        NewsSource(
            name="moneycontrol-rss",
            url="https://www.moneycontrol.com/rss/latestnews.xml",
            type="rss",
            update_interval_minutes=15,
            categories=["markets", "economy", "companies"]
        ),
        NewsSource(
            name="economictimes-rss",
            url="https://economictimes.indiatimes.com/rssfeedsdefault.cms",
            type="rss",
            update_interval_minutes=15,
            categories=["markets", "economy", "companies"]
        ),
        NewsSource(
            name="business-standard-rss",
            url="https://www.business-standard.com/rss/home_page_top_stories.rss",
            type="rss",
            update_interval_minutes=15,
            categories=["markets", "economy", "companies"]
        )
    ]


async def collect_and_store_news(news_service: NewsData, instruments: Optional[list] = None):
    """Convenience function to collect and store news for instruments.

    Args:
        news_service: NewsData service instance
        instruments: List of instruments to collect news for. Uses major indices if None.
    """
    if instruments is None:
        instruments = ["NIFTY", "BANKNIFTY", "RELIANCE", "TCS", "INFY", "HDFC", "ICICI"]

    async with news_service:  # Ensure proper initialization/cleanup
        for instrument in instruments:
            try:
                # Get latest news (this will trigger collection if needed)
                news = await news_service.get_latest_news(instrument, limit=10)
                print(f"Collected {len(news)} news items for {instrument}")

                # Calculate sentiment summary
                sentiment = await news_service.get_sentiment_summary(instrument, hours=24)
                print(f"Sentiment for {instrument}: {sentiment.average_sentiment:.3f} ({sentiment.sentiment_trend})")

            except Exception as e:
                print(f"Failed to collect news for {instrument}: {e}")