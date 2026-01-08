"""YFinance news collector for financial news."""

from __future__ import annotations

from typing import List, Optional
import yfinance as yf
from datetime import datetime

from ..contracts import NewsItem, NewsCollector


class YFinanceNewsCollector(NewsCollector):
    """Collect news from Yahoo Finance using yfinance."""
    
    def __init__(self, symbol_mapping: Optional[dict] = None):
        """Initialize YFinance news collector.
        
        Args:
            symbol_mapping: Optional mapping from instrument names to Yahoo Finance symbols
                          e.g., {"BANKNIFTY": "^NSEBANK", "NIFTY": "^NSEI"}
        """
        self.symbol_mapping = symbol_mapping or {
            "BANKNIFTY": "^NSEBANK",
            "NIFTY": "^NSEI",
            "NIFTY 50": "^NSEI",
            "NIFTY BANK": "^NSEBANK"
        }
    
    def _get_yahoo_symbol(self, instrument: str) -> str:
        """Get Yahoo Finance symbol for instrument."""
        # Try direct mapping first
        if instrument.upper() in self.symbol_mapping:
            return self.symbol_mapping[instrument.upper()]
        
        # Try with spaces removed
        instrument_clean = instrument.upper().replace(" ", "")
        if instrument_clean in self.symbol_mapping:
            return self.symbol_mapping[instrument_clean]
        
        # Default: try to use instrument as-is
        return instrument.upper()
    
    async def collect_news(self, sources: List[str] = None, limit: int = 100) -> List[NewsItem]:
        """Collect news from Yahoo Finance.
        
        Args:
            sources: List of instruments/symbols (ignored, uses all mapped symbols)
            limit: Maximum number of news items to return
        
        Returns:
            List of NewsItem objects
        """
        news_items = []
        
        # Collect news for all mapped symbols
        for instrument, yahoo_symbol in self.symbol_mapping.items():
            try:
                ticker = yf.Ticker(yahoo_symbol)
                yf_news = ticker.news
                
                for article in yf_news[:limit]:
                    try:
                        published_at_ts = article.get("providerPublishTime") or 0
                        published_at = datetime.fromtimestamp(published_at_ts) if published_at_ts else datetime.now()

                        news_item = NewsItem(
                            title=article.get("title", ""),
                            content=article.get("summary", ""),
                            source="yfinance",
                            published_at=published_at,
                            url=article.get("link", ""),
                            instruments=[instrument],
                            tags=article.get("type", "").split(",") if article.get("type") else []
                        )
                        news_items.append(news_item)
                    except Exception as e:
                        # Log and continue, don't fail the whole instrument
                        print(f"Error parsing article for {instrument}: {e}")
                        continue
            except Exception as e:
                print(f"Error collecting news for {instrument} ({yahoo_symbol}): {e}")
                continue
        
        return news_items[:limit]
    
    async def collect_news_for_instrument(self, instrument: str, limit: int = 50) -> List[NewsItem]:
        """Collect news specifically for an instrument.
        
        Args:
            instrument: Instrument symbol (e.g., "BANKNIFTY", "NIFTY")
            limit: Maximum number of news items
        
        Returns:
            List of NewsItem objects
        """
        yahoo_symbol = self._get_yahoo_symbol(instrument)
        
        try:
            ticker = yf.Ticker(yahoo_symbol)
            yf_news = ticker.news
            
            news_items = []
            for article in yf_news[:limit]:
                news_item = NewsItem(
                    title=article.get("title", ""),
                    content=article.get("summary", ""),
                    source="yfinance",
                    published_at=datetime.fromtimestamp(article.get("providerPublishTime", 0)),
                    url=article.get("link", ""),
                    instruments=[instrument.upper()],
                    tags=article.get("type", "").split(",") if article.get("type") else []
                )
                news_items.append(news_item)
            
            return news_items
        except Exception as e:
            print(f"Error collecting news for {instrument} ({yahoo_symbol}): {e}")
            return []

