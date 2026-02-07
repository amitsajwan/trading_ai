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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',  # Removed 'br' (Brotli) - aiohttp handles gzip/deflate automatically
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
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

        # Sort sources by priority (high priority first)
        active_sources.sort(key=lambda s: s.priority)

        all_news = []
        successful_sources = 0

        for source in active_sources:
            try:
                # Allocate more items to higher priority sources
                priority_weight = {1: 1.5, 2: 1.0, 3: 0.5}
                weight = priority_weight.get(source.priority, 1.0)
                source_limit = max(5, int((limit * weight) // len(active_sources)))

                news_items = await self._collect_from_source(source, source_limit)
                if news_items:  # Only count as success if we got items
                    all_news.extend(news_items)
                    successful_sources += 1
                    logger.info(f"✅ Collected {len(news_items)} items from {source.name} (priority: {source.priority})")
                else:
                    logger.warning(f"⚠️ No items collected from {source.name} (may be temporarily unavailable)")

            except Exception as e:
                logger.error(f"❌ Failed to collect from {source.name}: {e}")

        # Log summary
        total_items = len(all_news)
        if successful_sources > 0:
            logger.info(f"📊 News collection complete: {total_items} items from {successful_sources}/{len(active_sources)} sources")
        else:
            logger.warning(f"⚠️ No news sources available - all {len(active_sources)} sources failed")

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
        """Collect news from a single RSS source with retry logic."""
        max_retries = getattr(source, 'retry_count', 3)

        for attempt in range(max_retries):
            try:
                async with self.session.get(source.url) as response:
                    if response.status == 403:
                        # HTTP 403 Forbidden - site is blocking requests
                        if attempt < max_retries - 1:  # Don't log warning on last attempt
                            logger.debug(f"Attempt {attempt + 1}/{max_retries}: {source.name} returned 403 Forbidden, retrying...")
                            await asyncio.sleep(1 * (attempt + 1))  # Progressive delay
                            continue
                        else:
                            logger.warning(f"❌ {source.name} persistently blocking requests (403 Forbidden) after {max_retries} attempts")
                            return []

                    elif response.status != 200:
                        if attempt < max_retries - 1:
                            logger.debug(f"Attempt {attempt + 1}/{max_retries}: {source.name} returned {response.status}, retrying...")
                            await asyncio.sleep(0.5 * (attempt + 1))
                            continue
                        else:
                            logger.warning(f"❌ {source.name} failed with HTTP {response.status} after {max_retries} attempts")
                            return []

                    content = await response.text()
                    feed = feedparser.parse(content)

                    # Check if feed parsing was successful
                    if feed.bozo and feed.bozo_exception:
                        logger.warning(f"Feed parsing error for {source.name}: {feed.bozo_exception}")
                        # Still try to parse entries if available
                        if not feed.entries:
                            return []

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
                logger.error(f"❌ Unexpected error collecting from {source.name}: {e}")
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

        # Extract base instrument from derivatives (e.g., BANKNIFTY26JANFUT -> BANKNIFTY)
        base_instrument = self._extract_base_instrument(instrument)

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

        return keyword_map.get(base_instrument, [base_instrument.lower()])

    def _extract_base_instrument(self, instrument: str) -> str:
        """Extract base instrument from derivative names.

        Examples:
        - BANKNIFTY26JANFUT -> BANKNIFTY
        - NIFTY26JANFUT -> NIFTY
        - RELIANCE -> RELIANCE (no change)
        """
        # Common Indian market instruments
        bases = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]

        for base in bases:
            if instrument.startswith(base):
                return base

        # For stocks, remove any numeric/date suffixes
        # RELIANCE26JANFUT -> RELIANCE
        # But be careful not to remove legitimate parts
        import re

        # Pattern: letters followed by numbers/dates
        # Keep original if it doesn't match derivative pattern
        if re.match(r'^[A-Z]+(?:\d{2}[A-Z]{3}[A-Z]{3})?$', instrument):
            # Extract just the letters part (stock name)
            match = re.match(r'^([A-Z]+)', instrument)
            if match:
                return match.group(1)

        return instrument

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