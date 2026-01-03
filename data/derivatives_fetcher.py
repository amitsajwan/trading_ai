"""Abstract base class for fetching derivatives data - currency/region agnostic."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime


class DerivativesFetcher(ABC):
    """
    Abstract base class for fetching derivatives data.
    Completely generic - works for any instrument, currency, region.
    """
    
    @abstractmethod
    async def fetch_options_chain(
        self, 
        strikes: Optional[List[int]] = None,
        expiry: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch options chain data.
        
        Args:
            strikes: Optional list of strikes to fetch (if None, auto-calculate)
            expiry: Optional expiry date (if None, use nearest)
            **kwargs: Additional parameters (currency, exchange-specific)
        
        Returns:
            {
                "underlying_price": float,  # Spot or futures price
                "currency": str,  # INR, USD, etc.
                "expiry": str,  # ISO format
                "strikes": {
                    strike: {
                        "ce_ltp": float,
                        "ce_oi": int,
                        "ce_volume": int,
                        "pe_ltp": float,
                        "pe_oi": int,
                        "pe_volume": int,
                        "currency": str  # Same as base currency
                    }
                },
                "oi_changes": {...},  # Optional: OI changes over time
                "timestamp": str,  # ISO format
                "exchange": str,
                "region": str
            }
        """
        pass
    
    @abstractmethod
    async def fetch_futures(
        self,
        contract: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch futures data.
        
        Args:
            contract: Optional contract identifier (if None, use nearest)
            **kwargs: Additional parameters
        
        Returns:
            {
                "futures_price": float,
                "spot_price": float,  # If available
                "basis": float,  # Futures - Spot
                "funding_rate": float,  # For crypto perpetuals
                "open_interest": float,
                "volume": float,
                "currency": str,
                "contract": str,
                "expiry": str,  # ISO format
                "timestamp": str,  # ISO format
                "exchange": str,
                "region": str
            }
        """
        pass
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize fetcher.
        Fetch instrument tokens, connect WebSockets, etc.
        """
        pass
    
    def supports_options(self) -> bool:
        """Check if options are supported."""
        return False
    
    def supports_futures(self) -> bool:
        """Check if futures are supported."""
        return False
    
    def supports_spot(self) -> bool:
        """Check if spot is supported."""
        return False
    
    def get_currency(self) -> str:
        """Get base currency for this instrument."""
        return "USD"  # Default, override in implementations
    
    def get_region(self) -> str:
        """Get region for this instrument."""
        return "GLOBAL"  # Default, override in implementations
    
    def get_exchange(self) -> str:
        """Get exchange name."""
        return "UNKNOWN"  # Override in implementations

