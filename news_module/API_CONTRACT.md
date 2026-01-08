# News API Contract

## Base URL
`http://localhost:8005`

## Health Check

### GET /health
Check service health and dependencies.

**Response:**
```json
{
  "status": "healthy" | "degraded",
  "module": "news",
  "timestamp": "2024-01-01T00:00:00",
  "dependencies": {
    "mongodb": "healthy" | "unhealthy",
    "news_service": "initialized" | "not_initialized"
  }
}
```

## News Endpoints

### GET /api/v1/news
Get latest news for default instrument (NIFTY).

**Parameters:**
- `limit` (query, optional): Maximum number of news items (default: 10)

**Response:** Same as GET /api/v1/news/{instrument}

### GET /api/v1/news/{instrument}
Get latest news for an instrument.

**Parameters:**
- `instrument` (path): Instrument symbol (e.g., "BANKNIFTY", "NIFTY")
- `limit` (query, optional): Maximum number of news items (default: 10)

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "count": 5,
  "news": [
    {
      "title": "Bank Nifty surges on positive news",
      "content": "Full article content...",
      "source": "moneycontrol-rss",
      "url": "https://...",
      "published_at": "2024-01-01T00:00:00",
      "sentiment_score": 0.7,
      "sentiment_label": "positive",
      "instruments": ["BANKNIFTY", "NIFTY"]
    }
  ],
  "timestamp": "2024-01-01T00:00:00"
}
```

### GET /api/v1/news/sentiment
Get sentiment summary for default instrument (NIFTY).

**Parameters:**
- `hours` (query, optional): Hours to analyze (default: 24)

**Response:** Same as GET /api/v1/news/{instrument}/sentiment

### GET /api/v1/news/{instrument}/sentiment
Get sentiment summary for an instrument.

**Parameters:**
- `instrument` (path): Instrument symbol
- `hours` (query, optional): Hours to analyze (default: 24)

**Response:**
```json
{
  "instrument": "BANKNIFTY",
  "average_sentiment": 0.65,
  "sentiment_trend": "bullish",
  "positive_count": 10,
  "negative_count": 3,
  "neutral_count": 2,
  "timestamp": "2024-01-01T00:00:00"
}
```

### POST /api/v1/news/collect
Trigger news collection for instruments.

**Request Body (optional):**
```json
{
  "instruments": ["BANKNIFTY", "NIFTY"]
}
```
If no body is provided, the service will collect for the default instruments: `NIFTY`, `BANKNIFTY`, `RELIANCE`, `TCS`, `INFY`.

**Response (200):**
```json
{
  "status": "success",
  "instruments": ["BANKNIFTY", "NIFTY"],
  "collected_count": 15,
  "timestamp": "2024-01-01T00:00:00"
}
```

**Example curl:**
```bash
# Trigger collection for defaults
curl -X POST http://localhost:8005/api/v1/news/collect

# Trigger collection for specific instruments
curl -X POST http://localhost:8005/api/v1/news/collect -H "Content-Type: application/json" -d '{"instruments":["BANKNIFTY","RELIANCE"]}'
```

## Error Responses

All endpoints may return:
- `500`: Internal server error

