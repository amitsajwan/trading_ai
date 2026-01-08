"""MongoDB storage implementation for news data."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from ..contracts import NewsItem, NewsStorage, NewsSentimentSummary

logger = logging.getLogger(__name__)


class MongoNewsStorage(NewsStorage):
    """MongoDB-backed storage for news data."""

    def __init__(self, collection: Collection):
        """Initialize with MongoDB collection.

        Args:
            collection: MongoDB collection for news storage
        """
        self.collection = collection
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create necessary indexes for efficient queries."""
        try:
            # Index for instrument-based queries
            self.collection.create_index([("instruments", 1), ("published_at", -1)])

            # Index for sentiment queries
            self.collection.create_index([("sentiment_score", 1), ("published_at", -1)])

            # Index for time-based queries
            self.collection.create_index([("published_at", -1)])

            # Index for source-based queries
            self.collection.create_index([("source", 1), ("published_at", -1)])

            # Compound index for efficient filtering
            self.collection.create_index([
                ("instruments", 1),
                ("sentiment_score", 1),
                ("published_at", -1)
            ])

            logger.info("News storage indexes created successfully")

        except PyMongoError as e:
            logger.warning(f"Failed to create indexes: {e}")

    async def store_news_item(self, news_item: NewsItem) -> bool:
        """Store a single news item."""
        try:
            doc = {
                "title": news_item.title,
                "content": news_item.content,
                "summary": news_item.summary,
                "source": news_item.source,
                "url": news_item.url,
                "published_at": news_item.published_at,
                "sentiment_score": news_item.sentiment_score,
                "relevance_score": news_item.relevance_score,
                "instruments": news_item.instruments,
                "tags": news_item.tags,
                "author": news_item.author,
                "language": news_item.language,
                "stored_at": datetime.now()
            }

            result = self.collection.insert_one(doc)
            logger.debug(f"Stored news item: {news_item.title[:50]}...")
            return result.acknowledged

        except PyMongoError as e:
            logger.error(f"Failed to store news item: {e}")
            return False

    async def store_news_batch(self, news_items: List[NewsItem]) -> int:
        """Store multiple news items. Returns count successfully stored."""
        if not news_items:
            return 0

        try:
            docs = []
            for item in news_items:
                doc = {
                    "title": item.title,
                    "content": item.content,
                    "summary": item.summary,
                    "source": item.source,
                    "url": item.url,
                    "published_at": item.published_at,
                    "sentiment_score": item.sentiment_score,
                    "relevance_score": item.relevance_score,
                    "instruments": item.instruments,
                    "tags": item.tags,
                    "author": item.author,
                    "language": item.language,
                    "stored_at": datetime.now()
                }
                docs.append(doc)

            result = self.collection.insert_many(docs)
            stored_count = len(result.inserted_ids)
            logger.info(f"Stored {stored_count} news items")
            return stored_count

        except PyMongoError as e:
            logger.error(f"Failed to store news batch: {e}")
            return 0

    async def get_news_for_instrument(self, instrument: str, limit: int = 50,
                                    hours_back: int = 24) -> List[NewsItem]:
        """Retrieve news for a specific instrument."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)

            query = {
                "instruments": instrument,
                "published_at": {"$gte": cutoff_time}
            }

            cursor = self.collection.find(query).sort("published_at", -1).limit(limit)
            docs = list(cursor)

            news_items = []
            for doc in docs:
                item = NewsItem(
                    title=doc.get("title", ""),
                    content=doc.get("content", ""),
                    summary=doc.get("summary"),
                    source=doc.get("source", "unknown"),
                    url=doc.get("url"),
                    published_at=doc.get("published_at", datetime.now()),
                    sentiment_score=doc.get("sentiment_score"),
                    relevance_score=doc.get("relevance_score"),
                    instruments=doc.get("instruments", []),
                    tags=doc.get("tags", []),
                    author=doc.get("author"),
                    language=doc.get("language", "en")
                )
                news_items.append(item)

            logger.debug(f"Retrieved {len(news_items)} news items for {instrument}")
            return news_items

        except PyMongoError as e:
            logger.error(f"Failed to retrieve news for {instrument}: {e}")
            return []

    async def get_news_by_sentiment(self, instrument: str, min_sentiment: float = None,
                                  max_sentiment: float = None, limit: int = 50) -> List[NewsItem]:
        """Retrieve news filtered by sentiment range."""
        try:
            query = {"instruments": instrument}

            if min_sentiment is not None or max_sentiment is not None:
                sentiment_query = {}
                if min_sentiment is not None:
                    sentiment_query["$gte"] = min_sentiment
                if max_sentiment is not None:
                    sentiment_query["$lte"] = max_sentiment
                query["sentiment_score"] = sentiment_query

            cursor = self.collection.find(query).sort("published_at", -1).limit(limit)
            docs = list(cursor)

            news_items = []
            for doc in docs:
                item = NewsItem(
                    title=doc.get("title", ""),
                    content=doc.get("content", ""),
                    summary=doc.get("summary"),
                    source=doc.get("source", "unknown"),
                    url=doc.get("url"),
                    published_at=doc.get("published_at", datetime.now()),
                    sentiment_score=doc.get("sentiment_score"),
                    relevance_score=doc.get("relevance_score"),
                    instruments=doc.get("instruments", []),
                    tags=doc.get("tags", []),
                    author=doc.get("author"),
                    language=doc.get("language", "en")
                )
                news_items.append(item)

            return news_items

        except PyMongoError as e:
            logger.error(f"Failed to retrieve news by sentiment: {e}")
            return []