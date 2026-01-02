"""Automatic macro economic data fetcher service."""

import asyncio
import logging
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from data.macro_collector import MacroCollector
from data.rbi_scraper import RBIScraper
from data.inflation_scraper import InflationScraper
from config.settings import settings

logger = logging.getLogger(__name__)


class MacroDataFetcher:
    """
    Automatically fetches macro economic data from external sources:
    - RBI repo rate (from RBI website or financial APIs)
    - Inflation data (CPI) from government statistics
    - NPA ratio from RBI banking sector reports
    """
    
    def __init__(self):
        """Initialize macro data fetcher."""
        self.macro_collector = MacroCollector()
        self.rbi_scraper = RBIScraper()
        self.inflation_scraper = InflationScraper()
        self.running = False
    
    async def fetch_rbi_rate(self) -> Optional[float]:
        """
        Fetch current RBI repo rate from RBI website.
        
        Returns:
            Repo rate as float percentage, or None if not found
        """
        try:
            logger.info("Fetching RBI repo rate from website...")
            
            # Try scraping RBI website
            rate = await self.rbi_scraper.fetch_repo_rate()
            if rate:
                logger.info(f"✅ Successfully fetched RBI repo rate: {rate}%")
                return rate
            
            # Fallback: Use existing data from database
            logger.warning("Could not fetch RBI rate from website, using existing data")
            macro_context = self.macro_collector.get_latest_macro_context()
            existing_rate = macro_context.get("rbi_rate")
            if existing_rate:
                logger.info(f"Using existing RBI rate from database: {existing_rate}%")
                return existing_rate
            
            logger.warning("No RBI rate available (neither scraped nor in database)")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching RBI rate: {e}")
            # Fallback to existing data
            macro_context = self.macro_collector.get_latest_macro_context()
            existing_rate = macro_context.get("rbi_rate")
            if existing_rate:
                logger.info(f"Using existing RBI rate after error: {existing_rate}%")
                return existing_rate
            return None
    
    async def fetch_inflation_data(self) -> Optional[Dict[str, float]]:
        """
        Fetch inflation data (CPI, WPI) from government sources.
        
        Returns dict with 'cpi' and optionally 'wpi' keys.
        """
        try:
            logger.info("Fetching inflation data from government sources...")
            
            # Try scraping CPI
            cpi = await self.inflation_scraper.fetch_cpi()
            
            # Try scraping WPI
            wpi = await self.inflation_scraper.fetch_wpi()
            
            if cpi or wpi:
                result = {}
                if cpi:
                    result["cpi"] = cpi
                    logger.info(f"✅ Successfully fetched CPI: {cpi}%")
                if wpi:
                    result["wpi"] = wpi
                    logger.info(f"✅ Successfully fetched WPI: {wpi}%")
                return result
            
            # Fallback: Use existing data from database
            logger.warning("Could not fetch inflation data, using existing data")
            macro_context = self.macro_collector.get_latest_macro_context()
            existing_cpi = macro_context.get("inflation_rate")
            if existing_cpi:
                logger.info(f"Using existing inflation rate from database: {existing_cpi}%")
                return {"cpi": existing_cpi}
            
            logger.warning("No inflation data available")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching inflation data: {e}")
            # Fallback to existing data
            macro_context = self.macro_collector.get_latest_macro_context()
            existing_cpi = macro_context.get("inflation_rate")
            if existing_cpi:
                logger.info(f"Using existing inflation rate after error: {existing_cpi}%")
                return {"cpi": existing_cpi}
            return None
    
    async def fetch_npa_data(self) -> Optional[float]:
        """
        Fetch banking sector NPA ratio from RBI reports.
        
        Returns NPA ratio as float percentage.
        """
        try:
            logger.info("Fetching NPA ratio from RBI reports...")
            
            # Try to extract NPA from RBI announcements/press releases
            # NPA data is typically in RBI's Financial Stability Report or Banking Sector reports
            announcements = await self.rbi_scraper.parse_rss_feed()
            
            # Look for NPA-related announcements
            for announcement in announcements:
                title = announcement.get('title', '').lower()
                if 'npa' in title or 'non-performing' in title or 'asset quality' in title:
                    # Could parse the announcement content for NPA ratio
                    # For now, log that we found relevant announcement
                    logger.info(f"Found NPA-related announcement: {announcement.get('title')}")
                    # TODO: Parse announcement content for actual NPA ratio
            
            # Fallback: Use existing data from database
            logger.warning("Could not fetch NPA data, using existing data")
            macro_context = self.macro_collector.get_latest_macro_context()
            existing_npa = macro_context.get("npa_ratio")
            if existing_npa:
                logger.info(f"Using existing NPA ratio from database: {existing_npa}%")
                return existing_npa
            
            logger.warning("No NPA data available")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching NPA data: {e}")
            # Fallback to existing data
            macro_context = self.macro_collector.get_latest_macro_context()
            existing_npa = macro_context.get("npa_ratio")
            if existing_npa:
                logger.info(f"Using existing NPA ratio after error: {existing_npa}%")
                return existing_npa
            return None
    
    async def fetch_all_macro_data(self) -> Dict[str, Any]:
        """Fetch all macro data and store in database."""
        logger.info("Fetching macro economic data...")
        
        results = {
            "rbi_rate": None,
            "inflation": None,
            "npa": None,
            "updated": False
        }
        
        # Fetch RBI rate
        rbi_rate = await self.fetch_rbi_rate()
        if rbi_rate:
            try:
                self.macro_collector.store_rbi_rate(rbi_rate, datetime.now(), "Auto-fetched")
                results["rbi_rate"] = rbi_rate
                results["updated"] = True
                logger.info(f"✅ Updated RBI rate: {rbi_rate}%")
            except Exception as e:
                logger.error(f"Error storing RBI rate: {e}")
        
        # Fetch inflation data
        inflation_data = await self.fetch_inflation_data()
        if inflation_data and inflation_data.get("cpi"):
            try:
                self.macro_collector.store_inflation_data(
                    inflation_data["cpi"],
                    inflation_data.get("wpi"),
                    datetime.now()
                )
                results["inflation"] = inflation_data
                results["updated"] = True
                logger.info(f"✅ Updated inflation: CPI={inflation_data['cpi']}%")
            except Exception as e:
                logger.error(f"Error storing inflation data: {e}")
        
        # Fetch NPA data
        npa_ratio = await self.fetch_npa_data()
        if npa_ratio:
            try:
                self.macro_collector.store_npa_data(npa_ratio, datetime.now())
                results["npa"] = npa_ratio
                results["updated"] = True
                logger.info(f"✅ Updated NPA ratio: {npa_ratio}%")
            except Exception as e:
                logger.error(f"Error storing NPA data: {e}")
        
        if not results["updated"]:
            logger.info("No macro data updated (using existing data or manual entry required)")
        
        return results
    
    async def run_continuous(self, update_interval_hours: int = 24):
        """
        Run continuous macro data fetching loop.
        
        Args:
            update_interval_hours: Hours between updates (default: 24 hours)
        """
        self.running = True
        logger.info(f"Starting continuous macro data fetcher (update interval: {update_interval_hours} hours)")
        
        # Fetch immediately on start
        await self.fetch_all_macro_data()
        
        while self.running:
            try:
                # Wait for next update interval
                await asyncio.sleep(update_interval_hours * 3600)
                
                if self.running:
                    await self.fetch_all_macro_data()
                    
            except asyncio.CancelledError:
                logger.info("Macro data fetcher cancelled")
                break
            except Exception as e:
                logger.error(f"Error in macro data fetcher loop: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retry
    
    async def close(self):
        """Close scrapers and cleanup."""
        await self.rbi_scraper.close()
        await self.inflation_scraper.close()
    
    def stop(self):
        """Stop the macro data fetcher."""
        self.running = False
        logger.info("Macro data fetcher stopped")

