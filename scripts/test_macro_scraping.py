"""Test script for macro data scraping."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.rbi_scraper import RBIScraper
from data.inflation_scraper import InflationScraper
from data.macro_data_fetcher import MacroDataFetcher
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_rbi_scraper():
    """Test RBI scraper."""
    print("\n" + "="*70)
    print("Testing RBI Scraper")
    print("="*70 + "\n")
    
    scraper = RBIScraper()
    try:
        # Test repo rate fetching
        print("1. Fetching RBI repo rate...")
        rate = await scraper.fetch_repo_rate()
        if rate:
            print(f"   ✅ Found repo rate: {rate}%")
        else:
            print("   ⚠️  Could not fetch repo rate")
        
        # Test RSS feed parsing
        print("\n2. Parsing RBI RSS feed...")
        announcements = await scraper.parse_rss_feed()
        if announcements:
            print(f"   ✅ Found {len(announcements)} announcements:")
            for i, ann in enumerate(announcements[:3], 1):
                print(f"      {i}. {ann.get('title', 'No title')}")
        else:
            print("   ⚠️  No announcements found")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    finally:
        await scraper.close()


async def test_inflation_scraper():
    """Test inflation scraper."""
    print("\n" + "="*70)
    print("Testing Inflation Scraper")
    print("="*70 + "\n")
    
    scraper = InflationScraper()
    try:
        print("1. Fetching CPI inflation...")
        cpi = await scraper.fetch_cpi()
        if cpi:
            print(f"   ✅ Found CPI: {cpi}%")
        else:
            print("   ⚠️  Could not fetch CPI")
        
        print("\n2. Fetching WPI inflation...")
        wpi = await scraper.fetch_wpi()
        if wpi:
            print(f"   ✅ Found WPI: {wpi}%")
        else:
            print("   ⚠️  Could not fetch WPI")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    finally:
        await scraper.close()


async def test_macro_fetcher():
    """Test macro data fetcher."""
    print("\n" + "="*70)
    print("Testing Macro Data Fetcher")
    print("="*70 + "\n")
    
    fetcher = MacroDataFetcher()
    try:
        print("1. Fetching all macro data...")
        results = await fetcher.fetch_all_macro_data()
        
        print(f"\n   Results:")
        print(f"   - RBI Rate: {results.get('rbi_rate', 'Not found')}")
        print(f"   - Inflation: {results.get('inflation', 'Not found')}")
        print(f"   - NPA: {results.get('npa', 'Not found')}")
        print(f"   - Updated: {results.get('updated', False)}")
        
        if results.get('updated'):
            print("\n   ✅ Macro data updated successfully!")
        else:
            print("\n   ⚠️  No data was updated (using existing or not found)")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    finally:
        await fetcher.close()


async def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("MACRO DATA SCRAPING TESTS")
    print("="*70)
    
    # Test individual scrapers
    await test_rbi_scraper()
    await test_inflation_scraper()
    
    # Test integrated fetcher
    await test_macro_fetcher()
    
    print("\n" + "="*70)
    print("TESTS COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

