"""RBI website scraper for macro economic data."""

import logging
import re
import httpx
from datetime import datetime
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class RBIScraper:
    """Scraper for RBI website to extract repo rate and policy announcements."""
    
    # RBI website URLs
    RBI_BASE_URL = "https://www.rbi.org.in"
    RBI_MONETARY_POLICY_URL = f"{RBI_BASE_URL}/scripts/BS_ViewMSE.aspx"
    RBI_PRESS_RELEASES_URL = f"{RBI_BASE_URL}/scripts/BS_PressReleaseView.aspx"
    RBI_RSS_FEED_URL = f"{RBI_BASE_URL}/scripts/BS_PressReleaseView.aspx?prid=0"
    
    def __init__(self):
        """Initialize RBI scraper."""
        self.session = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
    
    async def fetch_repo_rate(self) -> Optional[float]:
        """
        Fetch current RBI repo rate from website.
        
        Returns:
            Repo rate as float percentage, or None if not found
        """
        try:
            logger.info("Fetching RBI repo rate from website...")
            
            # Try multiple approaches
            rate = await self._scrape_repo_rate_from_policy_page()
            if rate:
                return rate
            
            rate = await self._scrape_repo_rate_from_press_releases()
            if rate:
                return rate
            
            logger.warning("Could not find repo rate on RBI website")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching repo rate: {e}")
            return None
    
    async def _scrape_repo_rate_from_policy_page(self) -> Optional[float]:
        """Scrape repo rate from monetary policy page."""
        try:
            response = await self.session.get(self.RBI_MONETARY_POLICY_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            
            # Look for repo rate patterns
            # Pattern 1: "Repo Rate: 6.50%" or "Repo Rate 6.50%"
            patterns = [
                r'Repo\s+Rate[:\s]+(\d+\.?\d*)%?',
                r'Policy\s+Repo\s+Rate[:\s]+(\d+\.?\d*)%?',
                r'Repurchase\s+Rate[:\s]+(\d+\.?\d*)%?',
                r'(\d+\.?\d*)\s*%\s*.*Repo\s+Rate',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    rate = float(match.group(1))
                    logger.info(f"Found repo rate: {rate}%")
                    return rate
            
            return None
            
        except Exception as e:
            logger.debug(f"Error scraping policy page: {e}")
            return None
    
    async def _scrape_repo_rate_from_press_releases(self) -> Optional[float]:
        """Scrape repo rate from latest press releases."""
        try:
            response = await self.session.get(self.RBI_PRESS_RELEASES_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for latest monetary policy announcement
            links = soup.find_all('a', href=True)
            for link in links[:10]:  # Check first 10 links
                href = link.get('href', '')
                text = link.get_text()
                
                if 'monetary' in text.lower() or 'policy' in text.lower():
                    # Follow link and check for repo rate
                    full_url = self.RBI_BASE_URL + href if href.startswith('/') else href
                    rate = await self._extract_rate_from_url(full_url)
                    if rate:
                        return rate
            
            return None
            
        except Exception as e:
            logger.debug(f"Error scraping press releases: {e}")
            return None
    
    async def _extract_rate_from_url(self, url: str) -> Optional[float]:
        """Extract repo rate from a specific URL."""
        try:
            response = await self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            
            # Look for repo rate
            patterns = [
                r'Repo\s+Rate[:\s]+(\d+\.?\d*)%?',
                r'Policy\s+Repo\s+Rate[:\s]+(\d+\.?\d*)%?',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    rate = float(match.group(1))
                    return rate
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting rate from URL: {e}")
            return None
    
    async def fetch_latest_policy_announcement(self) -> Optional[Dict[str, Any]]:
        """
        Fetch latest monetary policy announcement.
        
        Returns:
            Dict with announcement details or None
        """
        try:
            logger.info("Fetching latest RBI policy announcement...")
            
            response = await self.session.get(self.RBI_PRESS_RELEASES_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find latest monetary policy announcement
            announcements = []
            links = soup.find_all('a', href=True)
            
            for link in links[:20]:  # Check first 20 links
                text = link.get_text().strip()
                href = link.get('href', '')
                
                if 'monetary' in text.lower() or 'policy' in text.lower() or 'mpc' in text.lower():
                    full_url = self.RBI_BASE_URL + href if href.startswith('/') else href
                    announcements.append({
                        'title': text,
                        'url': full_url,
                        'date': datetime.now()  # Approximate, could parse from page
                    })
            
            if announcements:
                return announcements[0]  # Return latest
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching policy announcement: {e}")
            return None
    
    async def parse_rss_feed(self) -> list[Dict[str, Any]]:
        """
        Parse RBI RSS feed for announcements.
        
        Returns:
            List of announcement dicts
        """
        try:
            logger.info("Parsing RBI RSS feed...")
            
            # Try RSS feed URL
            rss_urls = [
                f"{self.RBI_BASE_URL}/scripts/rss.aspx",
                f"{self.RBI_BASE_URL}/scripts/BS_PressReleaseView.aspx?prid=0",
            ]
            
            announcements = []
            for url in rss_urls:
                try:
                    response = await self.session.get(url)
                    response.raise_for_status()
                    
                    # Try to parse as RSS/XML
                    soup = BeautifulSoup(response.text, 'xml')
                    
                    # Look for RSS items
                    items = soup.find_all('item')
                    if not items:
                        items = soup.find_all('entry')  # Atom feed
                    
                    for item in items[:10]:  # Latest 10
                        title_elem = item.find('title')
                        link_elem = item.find('link')
                        date_elem = item.find('pubDate') or item.find('published')
                        
                        if title_elem:
                            title = title_elem.get_text()
                            # Filter for monetary policy related
                            if any(keyword in title.lower() for keyword in ['monetary', 'policy', 'mpc', 'repo', 'rate']):
                                announcements.append({
                                    'title': title,
                                    'url': link_elem.get_text() if link_elem else '',
                                    'date': self._parse_date(date_elem.get_text() if date_elem else ''),
                                    'source': 'RBI RSS'
                                })
                    
                    if announcements:
                        break  # Found announcements, stop trying other URLs
                        
                except Exception as e:
                    logger.debug(f"Error parsing RSS URL {url}: {e}")
                    continue
            
            logger.info(f"Found {len(announcements)} policy-related announcements")
            return announcements
            
        except Exception as e:
            logger.error(f"Error parsing RSS feed: {e}")
            return []
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime."""
        try:
            # Try common formats
            formats = [
                '%Y-%m-%d',
                '%d-%m-%Y',
                '%Y-%m-%d %H:%M:%S',
                '%a, %d %b %Y %H:%M:%S %z',
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
            
            return datetime.now()  # Default to now
            
        except Exception:
            return datetime.now()
    
    async def close(self):
        """Close the HTTP session."""
        await self.session.aclose()

