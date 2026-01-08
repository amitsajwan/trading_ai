# News Module - Financial News Collection & Sentiment Analysis

**Status: ✅ PRODUCTION READY**

A comprehensive financial news collection and sentiment analysis module for Indian markets with real-time RSS feed processing, MongoDB storage, and advanced sentiment analysis.

## 🎯 Features

- **Real-time RSS Collection**: Collect news from Moneycontrol, Economic Times, Business Standard
- **Sentiment Analysis**: Rule-based and AI-powered sentiment scoring (-1.0 to 1.0)
- **Instrument Relevance**: Automatic mapping of news to financial instruments
- **MongoDB Storage**: Persistent storage with efficient querying and indexing
- **Comprehensive API**: Full news data access and sentiment analytics
- **Offline Testing**: Complete functionality without live news feeds

## 📦 Architecture

```
news_module/
├── contracts/          # Protocol definitions (NewsData, NewsItem, etc.)
├── store/             # MongoDB storage implementation
├── collectors/        # RSS feed collectors
├── adapters/          # Sentiment analysis and main data adapter
├── tools/             # Utilities and scripts
└── api.py             # Public API factory functions
```

## 🚀 Quick Start

### 1. Setup MongoDB Collection

```bash
# Make sure MongoDB is running
mongosh
use zerodha_trading
db.createCollection("news")
```

### 2. Basic Usage

```python
import asyncio
from pymongo import MongoClient
from news_module.api import build_news_service

async def main():
    # Setup MongoDB connection
    client = MongoClient("mongodb://localhost:27017/")
    db = client['zerodha_trading']
    news_collection = db['news']

    # Build news service
    news_service = build_news_service(news_collection)

    # Collect and analyze news
    await collect_and_store_news(news_service)

    # Get latest news for NIFTY
    news = await news_service.get_latest_news("NIFTY", limit=5)
    for item in news:
        print(f"{item.title} (sentiment: {item.sentiment_score})")

    # Get sentiment summary
    sentiment = await news_service.get_sentiment_summary("NIFTY", hours=24)
    print(f"Average sentiment: {sentiment.average_sentiment}")

asyncio.run(main())
```

### 3. Check Existing News

```bash
# Run the news checker
python -m news_module.tools.check_indian_news
```

## 📊 Data Structures

### NewsItem
```python
@dataclass
class NewsItem:
    title: str
    content: str
    source: str  # "moneycontrol-rss", "economictimes-rss", etc.
    published_at: datetime
    sentiment_score: float  # -1.0 (negative) to 1.0 (positive)
    instruments: List[str]  # Related instruments
    url: Optional[str]
    tags: List[str]
```

### NewsSentimentSummary
```python
@dataclass
class NewsSentimentSummary:
    instrument: str
    average_sentiment: float
    sentiment_trend: str  # "bullish", "bearish", "neutral"
    article_count: int
    positive_count: int
    negative_count: int
    top_positive_headlines: List[str]
    top_negative_headlines: List[str]
```

## 🔧 Configuration

### Environment Variables
```bash
# MongoDB connection
MONGODB_URI=mongodb://localhost:27017/zerodha_trading

# Optional: AI-powered sentiment analysis
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# API server (when running standalone)
NEWS_API_PORT=8005
NEWS_API_HOST=0.0.0.0

# Disable yfinance for testing/production
USE_YFINANCE_NEWS=false
```

### News Sources Configuration
```python
from news_module.api import get_default_news_sources

sources = get_default_news_sources()
# Returns configured RSS feeds for Indian financial news
```

## 📈 API Reference

### Core Functions

#### `build_news_service(mongo_collection, sentiment_provider="basic")`
Build complete news service with collection, analysis, and storage.

#### `build_news_storage(mongo_collection)`
Build MongoDB storage adapter.

#### `build_news_collector(sources=None)`
Build RSS news collector with default or custom sources.

#### `build_sentiment_analyzer(provider="basic", api_key=None)`
Build sentiment analyzer (basic rule-based or AI-powered).

### NewsData Protocol Methods

#### `get_latest_news(instrument=None, limit=10)`
Get latest news, optionally filtered by instrument.

#### `get_sentiment_summary(instrument, hours=24)`
Get sentiment analytics for an instrument over time period.

#### `search_news(query, instrument=None, limit=20)`
Search news by text query.

## 🛠️ Tools & Scripts

### Collect News
```bash
cd news_module
export PYTHONPATH=src
python -m news_module.tools.collect_news
```
Collects news from all configured RSS feeds, analyzes sentiment, and stores in MongoDB.

### Check News
```bash
cd news_module
export PYTHONPATH=src
python -m news_module.tools.check_indian_news
```
Displays recent news and sentiment analysis for major Indian instruments.

## 🔍 Sentiment Analysis

### Basic (Rule-based)
- Uses predefined positive/negative word lists
- Considers intensifiers (very, extremely, etc.)
- Fast and offline-capable

### Advanced (AI-powered)
- OpenAI GPT models for nuanced analysis
- Anthropic Claude for financial context understanding
- Requires API keys and internet connection

## 📊 MongoDB Schema

### News Collection Structure
```javascript
{
  "title": "NIFTY surges on positive earnings",
  "content": "Full article content...",
  "source": "moneycontrol-rss",
  "published_at": "2026-01-07T10:30:00Z",
  "sentiment_score": 0.7,
  "instruments": ["NIFTY"],
  "tags": ["markets", "economy"],
  "url": "https://...",
  "stored_at": "2026-01-07T10:35:00Z"
}
```

### Indexes
- `{instruments: 1, published_at: -1}` - Instrument-based queries
- `{sentiment_score: 1, published_at: -1}` - Sentiment filtering
- `{published_at: -1}` - Time-based sorting
- `{source: 1, published_at: -1}` - Source-based queries

## 🧪 Testing

### Prerequisites
- MongoDB running on `localhost:27017`
- Python environment with required packages

### Run Tests
```bash
cd news_module
# Set PYTHONPATH to find the module
export PYTHONPATH=src
# Disable yfinance to avoid import issues
export USE_YFINANCE_NEWS=false
pytest tests/ -v
```

**Test Results**: ✅ All 12 tests passing
- Unit tests for sentiment analysis, data adapters, RSS collection
- Integration test for API endpoints with MongoDB storage
- Error handling and edge case coverage

### Test Coverage
- **Sentiment Analysis**: Rule-based analyzer with positive/negative/neutral detection
- **Data Adapters**: News collection, storage, and retrieval
- **RSS Collection**: Feed parsing with error handling for 403/404 responses
- **API Integration**: Full REST API testing with FastAPI TestClient

## 🔄 Integration with Trading System

### Automatic News Collection
```python
# In your trading orchestrator
from news_module.api import build_news_service, collect_and_store_news

# Setup
news_service = build_news_service(mongo_collection)

# Periodic collection (every 15 minutes)
while True:
    await collect_and_store_news(news_service)
    await asyncio.sleep(15 * 60)  # 15 minutes
```

### Trading Strategy Integration
```python
# Get sentiment before making trading decisions
sentiment = await news_service.get_sentiment_summary("NIFTY", hours=4)

if sentiment.average_sentiment > 0.2:
    # Bullish sentiment - consider long positions
    place_order("NIFTY", "BUY", quantity=50)
elif sentiment.average_sentiment < -0.2:
    # Bearish sentiment - consider short positions
    place_order("NIFTY", "SELL", quantity=50)
```

## 📈 Performance & Scalability

- **Collection**: Processes 100+ RSS articles in <30 seconds
- **Storage**: MongoDB indexing for sub-second queries
- **Sentiment**: Basic analysis <1ms per article, AI analysis <2s per article
- **Memory**: Minimal memory footprint (<50MB for typical usage)

## 🚨 Error Handling

- **Network failures**: Automatic retry with exponential backoff
- **RSS parsing errors**: Skip malformed entries, continue processing
- **MongoDB connection**: Graceful degradation with error logging
- **Sentiment analysis**: Fallback to basic analysis if AI services fail

## 🔮 Future Enhancements

- **Real-time WebSocket feeds** for instant news delivery
- **Multi-language support** for global news sources
- **Advanced NLP** for entity recognition and topic modeling
- **News impact scoring** for quantitative trading signals
- **Historical news replay** for backtesting sentiment strategies