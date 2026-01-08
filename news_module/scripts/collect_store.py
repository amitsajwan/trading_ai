#!/usr/bin/env python3
"""Run a direct collection and storage using the News service (no API)."""
import asyncio
from pymongo import MongoClient
from pathlib import Path
import sys

# Ensure src on path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / 'src'))

from news_module.api import build_news_service, collect_and_store_news
from news_module.api_service import get_mongo_collection

async def main():
    collection = get_mongo_collection()
    service = build_news_service(collection, use_yfinance=False)

    await collect_and_store_news(service, instruments=['BANKNIFTY', 'NIFTY'])

if __name__ == '__main__':
    asyncio.run(main())
