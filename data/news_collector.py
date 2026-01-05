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
        self.finnhub_api_key = settings.finnhub_api_key
        self.eodhd_api_key = settings.eodhd_api_key
        self.news_api_provider = settings.news_api_provider
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
        
        # Fetch from both EODHD and Finnhub if keys are available
        all_news_items = []
        
        # Fetch from EODHD
        if self.eodhd_api_key:
            eodhd_news = await self._fetch_from_provider("eodhd", self.eodhd_api_key, query, max_results // 2)
            all_news_items.extend(eodhd_news)
        
        # Fetch from Finnhub
        if self.finnhub_api_key:
            finnhub_news = await self._fetch_from_provider("finnhub", self.finnhub_api_key, query, max_results // 2)
            all_news_items.extend(finnhub_news)
        
        # Sort by published_at (most recent first) and limit results
        all_news_items.sort(key=lambda x: x.get("published_at", ""), reverse=True)
        return all_news_items[:max_results]
    
    async def _fetch_from_provider(self, provider: str, api_key: str, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Fetch news from a specific provider."""
        try:
            async with httpx.AsyncClient() as client:
                if provider == "finnhub":
                    # Finnhub API
                    url = "https://finnhub.io/api/v1/news"
                    # Determine category based on instrument
                    category = "crypto" if "BTC" in settings.instrument_symbol.upper() else "general"
                    params = {
                        "category": category,
                        "token": api_key
                    }
                elif provider == "eodhd":
                    # EODHD API for financial news
                    url = "https://eodhd.com/api/news"
                    # Use appropriate topics based on instrument
                    if "BTC" in settings.instrument_symbol.upper():
                        topics = "crypto,blockchain,finance"
                    else:
                        topics = "finance,markets,economy"
                    params = {
                        "api_token": api_key,
                        "t": topics,
                        "limit": max_results,
                        "from": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                    }
                else:
                    # Default to NewsAPI
                    url = "https://newsapi.org/v2/everything"
                    params = {
                        "q": query,
                        "apiKey": api_key,
                        "language": "en",
                        "sortBy": "publishedAt",
                        "pageSize": max_results,
                        "from": (datetime.now() - timedelta(hours=24)).isoformat()
                    }
                
                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                
                data = response.json()
                
                if provider == "finnhub":
                    articles = data  # Finnhub returns direct array
                elif provider == "eodhd":
                    articles = data  # EODHD returns direct array
                else:
                    articles = data.get("articles", [])
                
                news_items = []
                for article in articles[:max_results]:  # Limit results
                    if provider == "finnhub":
                        news_item = {
                            "title": article.get("headline", ""),
                            "content": article.get("summary", ""),
                            "source": article.get("source", "finnhub"),
                            "url": article.get("url", ""),
                            "published_at": datetime.fromtimestamp(article.get("datetime", 0)).isoformat() if article.get("datetime") else "",
                            "timestamp": datetime.now().isoformat(),
                            "event_type": "NEWS"
                        }
                    elif provider == "eodhd":
                        news_item = {
                            "title": article.get("title", ""),
                            "content": article.get("content", ""),
                            "source": article.get("source", "eodhd"),
                            "url": article.get("link", ""),
                            "published_at": article.get("date", ""),
                            "timestamp": datetime.now().isoformat(),
                            "event_type": "NEWS"
                        }
                    else:
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
            logger.error(f"Error fetching news from {provider}: {e}")
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

