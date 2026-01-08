"""FastAPI REST API service for news_module.

This provides HTTP endpoints for:
- News collection and retrieval
- Sentiment analysis
- Health checks
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.collection import Collection
from contextlib import asynccontextmanager
from typing import List

from .api import build_news_service, build_news_collector
from .contracts import NewsData, NewsItem, NewsSentimentSummary
import os


# Pydantic models for API requests/responses
class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    module: str
    timestamp: str
    dependencies: Dict[str, str]


class NewsItemResponse(BaseModel):
    """News item response."""
    title: str
    content: str
    source: str
    url: str
    published_at: str
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    instruments: List[str] = []


class NewsListResponse(BaseModel):
    """News list response."""
    instrument: str
    count: int
    news: List[NewsItemResponse]
    timestamp: str


class SentimentResponse(BaseModel):
    """Sentiment summary response."""
    instrument: str
    average_sentiment: float
    sentiment_trend: str
    positive_count: int
    negative_count: int
    neutral_count: int
    timestamp: str


# FastAPI app with lifespan handler
@asynccontextmanager
async def lifespan(app):
    """Initialize and cleanup resources using FastAPI lifespan events."""
    try:
        print("News API: Starting initialization...")
        # Startup: verify MongoDB and initialize news service
        mongo_client = get_mongo_client()
        mongo_client.admin.command('ping')
        print("News API: MongoDB connection verified")
        # Initialize the service eagerly so it's ready
        get_news_service()
        print("News API: Services initialized successfully")
        print("News API: Yielding control to FastAPI...")
        yield
        print("News API: Returned from yield, starting shutdown...")
    except Exception as e:
        print(f"News API: Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        print("News API: Starting cleanup...")
        # Shutdown: cleanup resources
        global _news_service, _mongo_client
        if _news_service:
            try:
                if hasattr(_news_service, '__aexit__'):
                    await _news_service.__aexit__(None, None, None)
            except Exception as e:
                print(f"News API: Error cleaning up service: {e}")
            _news_service = None
        if _mongo_client:
            try:
                _mongo_client.close()
            except Exception as e:
                print(f"News API: Error closing MongoDB client: {e}")
            _mongo_client = None
        print("News API: Cleanup complete")

app = FastAPI(
    title="News API",
    description="REST API for news collection, retrieval, and sentiment analysis",
    version="1.0.0",
    lifespan=lifespan
)

# Global service instance
_news_service: Optional[NewsData] = None
_mongo_client: Optional[MongoClient] = None


def get_mongo_client() -> MongoClient:
    """Get MongoDB client."""
    global _mongo_client
    
    if _mongo_client is None:
        mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/zerodha_trading")
        _mongo_client = MongoClient(mongodb_uri)
    
    return _mongo_client


def get_mongo_collection() -> Collection:
    """Get MongoDB collection for news storage."""
    mongo_client = get_mongo_client()
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/zerodha_trading")
    db_name = mongodb_uri.split("/")[-1] if "/" in mongodb_uri else "zerodha_trading"
    db = mongo_client[db_name]
    return db["news"]


def get_news_service() -> NewsData:
    """Get news service instance."""
    global _news_service
    
    if _news_service is None:
        collection = get_mongo_collection()
        # Use yfinance collector by default
        use_yfinance = os.getenv("USE_YFINANCE_NEWS", "true").lower() == "true"
        _news_service = build_news_service(collection, use_yfinance=use_yfinance)
    
    return _news_service





@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        mongo_client = get_mongo_client()
        mongo_client.admin.command('ping')
        mongo_status = "healthy"
    except Exception as e:
        mongo_status = f"unhealthy: {str(e)}"
    
    return HealthResponse(
        status="healthy" if mongo_status == "healthy" else "degraded",
        module="news",
        timestamp=datetime.now(timezone.utc).isoformat(),
        dependencies={
            "mongodb": mongo_status,
            "news_service": "initialized" if _news_service is not None else "not_initialized"
        }
    )


@app.get("/api/v1/news/{instrument}", response_model=NewsListResponse)
async def get_news(
    instrument: str,
    limit: int = 10
):
    """Get latest news for an instrument."""
    try:
        service = get_news_service()
        news_items = await service.get_latest_news(instrument.upper(), limit=limit)
        
        # Build response list and compute sentiment_label if not provided on the NewsItem
        news_list = []
        for item in news_items:
            sentiment_label = None
            if getattr(item, 'sentiment_score', None) is not None:
                if item.sentiment_score > 0.1:
                    sentiment_label = "positive"
                elif item.sentiment_score < -0.1:
                    sentiment_label = "negative"
                else:
                    sentiment_label = "neutral"

            news_list.append(
                NewsItemResponse(
                    title=item.title,
                    content=item.content,
                    source=item.source,
                    url=item.url,
                    published_at=item.published_at.isoformat() if item.published_at else "",
                    sentiment_score=item.sentiment_score,
                    sentiment_label=sentiment_label,
                    instruments=item.instruments or []
                )
            )

        return NewsListResponse(
            instrument=instrument.upper(),
            count=len(news_list),
            news=news_list,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/news", response_model=NewsListResponse)
async def get_news_default(
    limit: int = 10
):
    """Get latest news for NIFTY (default instrument)."""
    return await get_news("NIFTY", limit=limit)


@app.get("/api/v1/news/{instrument}/sentiment", response_model=SentimentResponse)
async def get_sentiment(
    instrument: str,
    hours: int = 24
):
    """Get sentiment summary for an instrument."""
    try:
        service = get_news_service()
        sentiment = await service.get_sentiment_summary(instrument.upper(), hours=hours)
        
        return SentimentResponse(
            instrument=instrument.upper(),
            average_sentiment=sentiment.average_sentiment,
            sentiment_trend=sentiment.sentiment_trend,
            positive_count=sentiment.positive_count,
            negative_count=sentiment.negative_count,
            neutral_count=sentiment.neutral_count,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/news/sentiment", response_model=SentimentResponse)
async def get_sentiment_default(
    hours: int = 24
):
    """Get sentiment summary for NIFTY (default instrument)."""
    return await get_sentiment("NIFTY", hours=hours)


class NewsCollectRequest(BaseModel):
    instruments: Optional[List[str]] = None


class NewsCollectResponse(BaseModel):
    status: str
    instruments: List[str]
    collected_count: int
    timestamp: str


@app.post("/api/v1/news/collect", response_model=NewsCollectResponse)
async def collect_news(request: NewsCollectRequest = Body(None)):
    """Trigger news collection for instruments.

    Uses a fresh service instance inside an async context manager so that
    any underlying HTTP client sessions are properly closed when collection
    completes. This avoids leaving aiohttp ClientSessions open across
    requests and prevents 'Unclosed client session' warnings.
    """
    try:
        # Default instruments to collect news for
        default_instruments = ["NIFTY", "BANKNIFTY", "RELIANCE", "TCS", "INFY"]
        instruments = request.instruments if request and request.instruments is not None else default_instruments

        # Build a fresh service (local instance) to perform collection and ensure cleanup
        collection = get_mongo_collection()
        local_service = build_news_service(collection)

        collected_count = 0
        # Use async context manager to ensure collector sessions are closed
        async with local_service:
            for instrument in instruments:
                try:
                    news = await local_service.get_latest_news(instrument.upper(), limit=10)
                    collected_count += len(news)
                except Exception as e:
                    print(f"Failed to collect news for {instrument}: {e}")

        return NewsCollectResponse(
            status="success",
            instruments=instruments,
            collected_count=collected_count,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("NEWS_API_PORT", "8005"))
    host = os.getenv("NEWS_API_HOST", "0.0.0.0")
    
    print(f"Starting News API on {host}:{port}")
    try:
        uvicorn.run(app, host=host, port=port)
    except Exception as e:
        print(f"Failed to start server: {e}")
        import traceback
        traceback.print_exc()

