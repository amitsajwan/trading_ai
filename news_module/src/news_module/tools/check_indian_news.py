"""Check and display recent Indian market news from the news module."""

import asyncio
import sys
from pathlib import Path

# Add news module to path
NEWS_MODULE_PATH = Path(__file__).resolve().parents[2]  # Go up to news_module root
sys.path.insert(0, str(NEWS_MODULE_PATH / "src"))

from pymongo import MongoClient
from news_module.api import build_news_service


async def check_indian_news():
    """Check and display recent Indian market news."""
    try:
        # Build news service
        client = MongoClient("mongodb://localhost:27017/")
        db = client['zerodha_trading']
        news_collection = db['news']  # Use 'news' collection instead of 'market_events'

        news_service = build_news_service(news_collection)

        # Check news for major Indian instruments
        instruments = ["NIFTY", "BANKNIFTY", "RELIANCE", "TCS", "INFY"]

        print("📰 Recent Indian Market News Analysis")
        print("=" * 50)

        total_news = 0
        for instrument in instruments:
            try:
                # Get latest news for this instrument
                news_items = await news_service.get_latest_news(instrument, limit=3)

                if news_items:
                    print(f"\n📊 {instrument} News:")
                    for i, item in enumerate(news_items, 1):
                        title = item.title[:60] + "..." if len(item.title) > 60 else item.title
                        sentiment = f"{item.sentiment_score:.2f}" if item.sentiment_score else "N/A"
                        published = item.published_at.strftime("%H:%M")
                        print(f"  {i}. {title}")
                        print(f"     Sentiment: {sentiment} | Published: {published}")

                    total_news += len(news_items)

                # Get sentiment summary
                sentiment_summary = await news_service.get_sentiment_summary(instrument, hours=24)
                print(f"  📈 Sentiment Summary: {sentiment_summary.average_sentiment:.2f} ({sentiment_summary.sentiment_trend})")

            except Exception as e:
                print(f"❌ Error checking {instrument}: {e}")

        print(f"\n✅ Total news items found: {total_news}")

        if total_news == 0:
            print("\n💡 No news found. You may need to run the news collector first:")
            print("   python -m news_module.tools.collect_news")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure MongoDB is running and the news collection exists.")


if __name__ == "__main__":
    asyncio.run(check_indian_news())