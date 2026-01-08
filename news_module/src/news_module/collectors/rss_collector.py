"""RSS-based news collector for financial news sources."""

import logging
import feedparser
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import aiohttp
import hashlib

from ..contracts import NewsItem, NewsCollector, NewsSource

logger = logging.getLogger(__name__)


class RSSNewsCollector(NewsCollector):
    """Collect news from RSS feeds."""

    def __init__(self, sources: List[NewsSource], timeout: int = 30):
        """Initialize with news sources.

        Args:
            sources: List of NewsSource configurations
            timeout: HTTP timeout in seconds
        """
        self.sources = sources
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            headers=headers
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            try:
                await self.session.close()
            finally:
                # Make sure session reference is cleared to avoid accidental reuse
                self.session = None

    async def close(self):
        """Explicit close helper to allow manual cleanup outside context manager."""
        if self.session:
            try:
                await self.session.close()
            finally:
                self.session = None

    async def collect_news(self, sources: List[str] = None, limit: int = 100) -> List[NewsItem]:
        """Collect news from specified sources."""
        if not self.session:
            raise RuntimeError("Use async context manager to initialize session")

        # Filter sources if specified
        active_sources = [s for s in self.sources if s.enabled]
        if sources:
            active_sources = [s for s in active_sources if s.name in sources]

        all_news = []
        for source in active_sources:
            try:
                news_items = await self._collect_from_source(source, limit // len(active_sources))
                all_news.extend(news_items)
                logger.info(f"Collected {len(news_items)} items from {source.name}")
            except Exception as e:
                logger.error(f"Failed to collect from {source.name}: {e}")

        # Sort by published date, most recent first
        all_news.sort(key=lambda x: x.published_at, reverse=True)
        return all_news[:limit]

    async def collect_news_for_instrument(self, instrument: str, limit: int = 50) -> List[NewsItem]:
        """Collect news specifically related to an instrument."""
        # For now, collect general news and filter by relevance
        # TODO: Implement instrument-specific collection
        all_news = await self.collect_news(limit=limit * 2)

        # Simple keyword filtering for instrument relevance
        relevant_news = []
        keywords = self._get_instrument_keywords(instrument)

        for item in all_news:
            if self._is_relevant_to_instrument(item, instrument, keywords):
                item.instruments.append(instrument)
                relevant_news.append(item)
                if len(relevant_news) >= limit:
                    break

        return relevant_news

    async def _collect_from_source(self, source: NewsSource, limit: int) -> List[NewsItem]:
        """Collect news from a single RSS source."""
        try:
            async with self.session.get(source.url) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch {source.url}: HTTP {response.status}")
                    return []

                content = await response.text()
                feed = feedparser.parse(content)

                news_items = []
                for entry in feed.entries[:limit]:
                    try:
                        news_item = self._parse_feed_entry(entry, source)
                        if news_item:
                            news_items.append(news_item)
                    except Exception as e:
                        logger.warning(f"Failed to parse entry from {source.name}: {e}")

                return news_items

        except Exception as e:
            logger.error(f"Failed to collect from {source.name}: {e}")
            return []

    def _parse_feed_entry(self, entry: Dict[str, Any], source: NewsSource) -> Optional[NewsItem]:
        """Parse a single RSS feed entry into NewsItem."""
        try:
            # Extract title
            title = getattr(entry, 'title', '').strip()
            if not title:
                return None

            # Extract content/summary
            content = getattr(entry, 'description', '') or getattr(entry, 'summary', '')
            content = content.strip()

            # Extract published date
            published_at = self._parse_published_date(entry)

            # Extract URL
            url = getattr(entry, 'link', '') or getattr(entry, 'url', '')

            # Create unique ID for deduplication
            content_hash = hashlib.md5(f"{title}{content[:100]}".encode()).hexdigest()[:8]

            return NewsItem(
                title=title,
                content=content,
                source=source.name,
                url=url,
                published_at=published_at,
                instruments=[],  # Will be populated by relevance analysis
                tags=source.categories.copy(),
                language="en"  # Assume English for now
            )

        except Exception as e:
            logger.warning(f"Failed to parse feed entry: {e}")
            return None

    def _parse_published_date(self, entry: Dict[str, Any]) -> datetime:
        """Parse published date from RSS entry."""
        # Try various date fields
        date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']

        for field in date_fields:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    parsed = getattr(entry, field)
                    if isinstance(parsed, (list, tuple)) and len(parsed) >= 6:
                        return datetime(*parsed[:6])
                except:
                    continue

        # Fallback to current time if no valid date found
        return datetime.now()

    def _get_instrument_keywords(self, instrument: str) -> List[str]:
        """Get keywords for instrument relevance matching."""
        instrument = instrument.upper()

        # Common instrument mappings
        keyword_map = {
            "NIFTY": ["nifty", "nse", "india", "indian market", "market", "stock"],
            "BANKNIFTY": ["bank nifty", "banknifty", "banking", "banks", "market", "stock", "nifty"],
            "RELIANCE": ["reliance", "mukesh ambani", "oil", "refinery"],
            "TCS": ["tcs", "tata", "it services", "software"],
            "INFY": ["infosys", "it services", "software"],
            "HDFC": ["hdfc", "banking", "finance"],
            "ICICI": ["icici", "banking", "finance"],
            "BAJAJ": ["bajaj", "auto", "automobile"],
            "MARUTI": ["maruti", "auto", "automobile", "suzuki"]
        }

        return keyword_map.get(instrument, [instrument.lower()])

    def _is_relevant_to_instrument(self, news_item: NewsItem, instrument: str,
                                 keywords: List[str]) -> bool:
        """Check if news item is relevant to instrument."""
        text = f"{news_item.title} {news_item.content}".lower()

        # Check for instrument name
        if instrument.lower() in text:
            return True

        # Check for keywords
        for keyword in keywords:
            if keyword in text:
                return True

        return False