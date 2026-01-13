"""Multi-timeframe OHLC data reader with caching support.

This module provides efficient access to OHLC data across multiple timeframes
for technical analysis and trading decisions.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from functools import lru_cache

from ..contracts import MarketStore, OHLCBar

logger = logging.getLogger(__name__)


@dataclass
class TimeframeData:
    """Container for OHLC data for a single timeframe."""
    timeframe: str
    bars: List[OHLCBar]
    count: int
    latest_timestamp: Optional[datetime] = None
    cached_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timeframe": self.timeframe,
            "count": self.count,
            "latest_timestamp": self.latest_timestamp.isoformat() if self.latest_timestamp else None,
            "cached_at": self.cached_at.isoformat() if self.cached_at else None,
            "bars": [
                {
                    "instrument": bar.instrument,
                    "timeframe": bar.timeframe,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                    "start_at": bar.start_at.isoformat(),
                }
                for bar in self.bars
            ]
        }


class MultiTimeframeReader:
    """Efficient multi-timeframe OHLC data reader with caching.
    
    Provides access to OHLC data across multiple timeframes (5m, 15m, 1h, daily)
    with intelligent caching to minimize Redis queries.
    
    Example:
        reader = MultiTimeframeReader(market_store)
        data = await reader.fetch_all_timeframes("BANKNIFTY", timeframes=["5m", "15m", "1h", "daily"])
        # Returns dict with keys "5m", "15m", "1h", "daily"
    """
    
    # Standard timeframes supported
    SUPPORTED_TIMEFRAMES = ["5m", "15m", "1h", "4h", "daily"]
    
    # Default cache TTL in seconds (5 minutes)
    DEFAULT_CACHE_TTL = 300
    
    def __init__(
        self,
        market_store: MarketStore,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL,
        max_cache_size: int = 1000
    ):
        """Initialize multi-timeframe reader.
        
        Args:
            market_store: MarketStore instance for OHLC access
            cache_ttl_seconds: Cache TTL in seconds (default: 5 minutes)
            max_cache_size: Maximum number of cached results
        """
        self.market_store = market_store
        self.cache_ttl = cache_ttl_seconds
        
        # In-memory cache: {instrument: {timeframe: (data, cached_at)}}
        self._cache: Dict[str, Dict[str, tuple]] = {}
        self.max_cache_size = max_cache_size
        
        logger.info(f"MultiTimeframeReader initialized with cache TTL: {cache_ttl_seconds}s")
    
    def _get_cache_key(self, instrument: str, timeframe: str) -> str:
        """Generate cache key."""
        return f"{instrument}:{timeframe}"
    
    def _is_cache_valid(self, cached_at: datetime) -> bool:
        """Check if cached data is still valid."""
        age = (datetime.now() - cached_at).total_seconds()
        return age < self.cache_ttl
    
    def _get_from_cache(
        self, 
        instrument: str, 
        timeframe: str
    ) -> Optional[TimeframeData]:
        """Get data from cache if valid."""
        if instrument not in self._cache:
            return None
        
        if timeframe not in self._cache[instrument]:
            return None
        
        data, cached_at = self._cache[instrument][timeframe]
        
        if not self._is_cache_valid(cached_at):
            # Cache expired, remove it
            del self._cache[instrument][timeframe]
            if not self._cache[instrument]:
                del self._cache[instrument]
            return None
        
        return data
    
    def _store_in_cache(
        self, 
        instrument: str, 
        timeframe: str, 
        data: TimeframeData
    ):
        """Store data in cache."""
        # Clean up old cache entries if size limit reached
        if len(self._cache) >= self.max_cache_size:
            # Remove oldest entries (simple FIFO)
            if self._cache:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
        
        if instrument not in self._cache:
            self._cache[instrument] = {}
        
        self._cache[instrument][timeframe] = (data, datetime.now())
    
    def clear_cache(self, instrument: Optional[str] = None):
        """Clear cache for instrument or all instruments.
        
        Args:
            instrument: If provided, clear cache only for this instrument.
                       If None, clear all cache.
        """
        if instrument:
            if instrument in self._cache:
                del self._cache[instrument]
                logger.debug(f"Cleared cache for {instrument}")
        else:
            self._cache.clear()
            logger.debug("Cleared all cache")
    
    def fetch_timeframe(
        self,
        instrument: str,
        timeframe: str,
        limit: int = 100,
        use_cache: bool = True
    ) -> TimeframeData:
        """Fetch OHLC data for a single timeframe.
        
        Args:
            instrument: Trading instrument (e.g., "BANKNIFTY")
            timeframe: Timeframe string (e.g., "5m", "15m", "1h", "daily")
            limit: Maximum number of bars to return
            use_cache: Whether to use cache (default: True)
        
        Returns:
            TimeframeData with bars for the requested timeframe
        
        Raises:
            ValueError: If timeframe is not supported
        """
        if timeframe not in self.SUPPORTED_TIMEFRAMES:
            raise ValueError(
                f"Unsupported timeframe: {timeframe}. "
                f"Supported: {self.SUPPORTED_TIMEFRAMES}"
            )
        
        # Check cache first
        if use_cache:
            cached_data = self._get_from_cache(instrument, timeframe)
            if cached_data is not None:
                logger.debug(f"Cache hit for {instrument}:{timeframe}")
                return cached_data
        
        # Fetch from market store
        logger.debug(f"Fetching {instrument}:{timeframe} from market store (limit={limit})")
        bars_iterable = self.market_store.get_ohlc(instrument, timeframe, limit)
        
        # Convert to list and sort by start_at (ascending)
        bars = sorted(list(bars_iterable), key=lambda b: b.start_at)
        
        # Get latest timestamp
        latest_timestamp = bars[-1].start_at if bars else None
        
        # Create TimeframeData
        data = TimeframeData(
            timeframe=timeframe,
            bars=bars,
            count=len(bars),
            latest_timestamp=latest_timestamp,
            cached_at=datetime.now()
        )
        
        # Store in cache
        if use_cache:
            self._store_in_cache(instrument, timeframe, data)
        
        logger.debug(f"Fetched {len(bars)} bars for {instrument}:{timeframe}")
        return data
    
    def fetch_all_timeframes(
        self,
        instrument: str,
        timeframes: Optional[List[str]] = None,
        limit: int = 100,
        use_cache: bool = True
    ) -> Dict[str, TimeframeData]:
        """Fetch OHLC data for multiple timeframes.
        
        Args:
            instrument: Trading instrument (e.g., "BANKNIFTY")
            timeframes: List of timeframes to fetch. If None, fetches all supported timeframes.
            limit: Maximum number of bars per timeframe
            use_cache: Whether to use cache (default: True)
        
        Returns:
            Dictionary mapping timeframe to TimeframeData
        
        Example:
            data = reader.fetch_all_timeframes("BANKNIFTY", ["5m", "15m", "1h"])
            # Returns: {"5m": TimeframeData(...), "15m": TimeframeData(...), "1h": TimeframeData(...)}
        """
        if timeframes is None:
            timeframes = self.SUPPORTED_TIMEFRAMES
        
        result = {}
        
        for timeframe in timeframes:
            try:
                data = self.fetch_timeframe(instrument, timeframe, limit, use_cache)
                result[timeframe] = data
            except ValueError as e:
                logger.warning(f"Skipping unsupported timeframe {timeframe}: {e}")
            except Exception as e:
                logger.error(f"Error fetching {instrument}:{timeframe}: {e}", exc_info=True)
                # Continue with other timeframes even if one fails
        
        return result
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_entries = sum(len(timeframes) for timeframes in self._cache.values())
        instruments = list(self._cache.keys())
        
        return {
            "total_instruments": len(self._cache),
            "total_entries": total_entries,
            "max_cache_size": self.max_cache_size,
            "cache_ttl_seconds": self.cache_ttl,
            "cached_instruments": instruments
        }
