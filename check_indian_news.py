from mongodb_schema import get_mongo_client, get_collection
from datetime import datetime, timedelta

# Connect to MongoDB and check for Indian market news
client = get_mongo_client()
db = client['zerodha_trading']
news_collection = get_collection(db, 'market_events')

# Query for recent Moneycontrol RSS news (Indian market news)
cutoff_time = datetime.now() - timedelta(hours=1)
indian_news = list(news_collection.find(
    {'event_type': 'NEWS', 'source': 'moneycontrol-rss', 'timestamp': {'$gte': cutoff_time.isoformat()}},
    {'_id': 0}
).sort('timestamp', -1).limit(3))

print(f'Found {len(indian_news)} recent Moneycontrol RSS (Indian market) news items')
if indian_news:
    print('Sample Indian market news:')
    for i, item in enumerate(indian_news, 1):
        title = item.get('title', 'N/A')[:50]
        sentiment = item.get('sentiment_score', 'N/A')
        print(f'{i}. {title}... (sentiment: {sentiment})')