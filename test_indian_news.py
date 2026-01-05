import asyncio
import os
from data.market_memory import MarketMemory
from data.news_collector import NewsCollector

async def test_indian_news():
    # Set up environment for testing both providers
    os.environ['FINNHUB_API_KEY'] = 'd5blghhr01qnaiducpg0d5blghhr01qnaiducpgg'
    os.environ['EODHD_API_KEY'] = '695b181b7260f8.07822295'
    os.environ['INSTRUMENT_SYMBOL'] = 'NIFTY BANK'  # Indian market

    market_memory = MarketMemory()
    collector = NewsCollector(market_memory)

    print('Testing news collection from both EODHD and Finnhub...')

    # Debug: check what keys are loaded
    from config.settings import settings
    print(f'Finnhub key loaded: {settings.finnhub_api_key is not None}')
    print(f'EODHD key loaded: {settings.eodhd_api_key is not None}')

    # Test fetch from both providers
    news = await collector.fetch_news(max_results=10)
    print(f'Fetched {len(news)} total news items from both providers')

    # Count items from each provider
    sources = [item.get('source', 'unknown') for item in news]
    unique_sources = set(sources)
    print(f'Unique sources: {unique_sources}')
    
    # Check if we have items from both APIs (by checking if sources include API provider names or news sources)
    has_finnhub = any('finnhub' in str(item).lower() for item in news)
    has_eodhd = any('eodhd' in str(item).lower() for item in news)
    
    print(f'Has Finnhub data: {has_finnhub}')
    print(f'Has EODHD data: {has_eodhd}')

    if news:
        print('Sample news items:')
        for i, item in enumerate(news[:3]):  # Show first 3 items
            print(f'{i+1}. [{item.get("source", "unknown")}] {item.get("title", "N/A")[:50]}...')

    # Test storage
    await collector.collect_and_store()
    print('News stored in database')

if __name__ == "__main__":
    asyncio.run(test_indian_news())