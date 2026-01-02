"""News and sentiment data collection service."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import httpx
from data.market_memory import MarketMemory
from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings

logger = logging.getLogger(__name__)


class NewsCollector:
    """
    Collects financial news and sentiment data from various sources.
    Updates every 5-10 minutes during market hours.
    """
    
    def __init__(self, market_memory: MarketMemory):
        """Initialize news collector."""
        self.market_memory = market_memory
        self.news_api_key = settings.news_api_key
        self.running = False
        
        # MongoDB connection
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.news_collection = get_collection(self.db, "market_events")
    
    async def fetch_news(self, query: Optional[str] = None, max_results: int = 20) -> List[Dict[str, Any]]:
        """Fetch news using configured query or default from settings."""
        # Use configured query if not provided
        if query is None:
            query = settings.news_query
        
        if not self.news_api_key:
            logger.warning("News API key not configured, skipping news fetch")
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                # NewsAPI endpoint
                url = "https://newsapi.org/v2/everything"
                params = {
                    "q": query,
                    "apiKey": self.news_api_key,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": max_results,
                    "from": (datetime.now() - timedelta(hours=24)).isoformat()
                }
                
                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                
                data = response.json()
                articles = data.get("articles", [])
                
                news_items = []
                for article in articles:
                    news_item = {
                        "title": article.get("title", ""),
                        "content": article.get("description", ""),
                        "source": article.get("source", {}).get("name", "unknown"),
                        "url": article.get("url", ""),
                        "published_at": article.get("publishedAt", ""),
                        "timestamp": datetime.now().isoformat(),
                        "event_type": "NEWS"
                    }
                    
                    # Simple sentiment analysis (can be enhanced with LLM)
                    news_item["sentiment_score"] = self._calculate_sentiment(news_item["title"])
                    
                    news_items.append(news_item)
                
                return news_items
                
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return []
    
    def _calculate_sentiment(self, text: str) -> float:
        """
        Simple sentiment calculation based on keywords.
        Returns -1.0 (very negative) to +1.0 (very positive).
        """
        text_lower = text.lower()
        
        # Positive keywords
        positive_words = ["surge", "rally", "gain", "profit", "growth", "up", "rise", "boost", "positive"]
        negative_words = ["fall", "drop", "decline", "loss", "crash", "down", "negative", "worry", "concern"]
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count == 0 and negative_count == 0:
            return 0.0
        
        # Normalize to -1 to +1
        total = positive_count + negative_count
        sentiment = (positive_count - negative_count) / total if total > 0 else 0.0
        
        # Clamp to [-1, 1]
        return max(-1.0, min(1.0, sentiment))
    
    async def collect_and_store(self):
        """Collect news and store in Redis and MongoDB."""
        logger.info("Collecting news and sentiment data...")
        
        news_items = await self.fetch_news()
        
        if not news_items:
            logger.warning("No news items collected")
            return
        
        # Calculate aggregate sentiment
        sentiment_scores = [item["sentiment_score"] for item in news_items]
        aggregate_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
        
        # Store in Redis
        self.market_memory.store_sentiment_score(aggregate_sentiment, "news")
        
        # Store individual news items in MongoDB
        for item in news_items:
            try:
                self.news_collection.insert_one(item)
            except Exception as e:
                logger.error(f"Error storing news item in MongoDB: {e}")
        
        logger.info(f"Collected {len(news_items)} news items, aggregate sentiment: {aggregate_sentiment:.2f}")
    
    async def run_continuous(self):
        """Run continuous news collection loop."""
        self.running = True
        logger.info("Starting continuous news collection...")
        
        while self.running:
            try:
                await self.collect_and_store()
                # Wait for next update interval
                await asyncio.sleep(settings.news_update_interval_minutes * 60)
            except Exception as e:
                logger.error(f"Error in news collection loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    def stop(self):
        """Stop the news collector."""
        self.running = False
        logger.info("News collector stopped")

