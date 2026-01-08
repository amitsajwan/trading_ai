"""Collect news from RSS feeds and store in database."""

import asyncio
import logging
import sys
from pathlib import Path

# Add news module to path
NEWS_MODULE_PATH = Path(__file__).resolve().parents[2]  # Go up to news_module root
sys.path.insert(0, str(NEWS_MODULE_PATH / "src"))

from pymongo import MongoClient
from news_module.api import build_news_service, collect_and_store_news


async def main():
    """Main news collection function."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # Build news service
        client = MongoClient("mongodb://localhost:27017/")
        db = client['zerodha_trading']
        news_collection = db['news']

        news_service = build_news_service(news_collection)

        print("📰 Starting news collection...")
        print("This will collect news from RSS feeds and analyze sentiment.")

        # Collect news for major instruments
        instruments = ["NIFTY", "BANKNIFTY", "RELIANCE", "TCS", "INFY"]
        collected_count = 0
        
        async with news_service:
            for instrument in instruments:
                try:
                    news = await news_service.get_latest_news(instrument, limit=5)
                    collected_count += len(news)
                    print(f"Collected {len(news)} news items for {instrument}")
                except Exception as e:
                    print(f"Failed to collect news for {instrument}: {e}")

        print(f"✅ News collection completed! Total items: {collected_count}")

    except Exception as e:
        print(f"❌ Error during news collection: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)