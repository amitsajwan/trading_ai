"""Abstract data source interface for loose coupling.

This module provides abstraction layers for different data sources,
enabling easy swapping between Zerodha, Binance, and other providers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class DataSourceType(Enum):
    """Supported data source types."""
    ZERODHA = "ZERODHA"
    CRYPTO = "CRYPTO"  # Binance
    MOCK = "MOCK"  # For testing


class MarketDataPoint:
    """Standardized market data structure."""
    
    def __init__(
        self,
        instrument: str,
        timestamp: datetime,
        price: float,
        volume: float,
        high: Optional[float] = None,
        low: Optional[float] = None,
        open: Optional[float] = None,
        close: Optional[float] = None,
    ):
        self.instrument = instrument
        self.timestamp = timestamp
        self.price = price
        self.volume = volume
        self.high = high or price
        self.low = low or price
        self.open = open or price
        self.close = close or price
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "instrument": self.instrument,
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "volume": self.volume,
            "high": self.high,
            "low": self.low,
            "open": self.open,
            "close": self.close,
        }


class IDataSource(ABC):
    """Abstract interface for market data sources."""
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to data source.
        
        Returns:
            bool: True if connection successful
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to data source."""
        pass
    
    @abstractmethod
    def subscribe(self, instruments: List[str]) -> bool:
        """Subscribe to real-time data for instruments.
        
        Args:
            instruments: List of instrument identifiers
            
        Returns:
            bool: True if subscription successful
        """
        pass
    
    @abstractmethod
    def get_latest_tick(self, instrument: str) -> Optional[MarketDataPoint]:
        """Get latest tick data for instrument.
        
        Args:
            instrument: Instrument identifier
            
        Returns:
            MarketDataPoint or None if not available
        """
        pass
    
    @abstractmethod
    def get_historical_data(
        self,
        instrument: str,
        from_date: datetime,
        to_date: datetime,
        interval: str = "1min"
    ) -> List[MarketDataPoint]:
        """Get historical OHLC data.
        
        Args:
            instrument: Instrument identifier
            from_date: Start date
            to_date: End date
            interval: Candle interval (1min, 5min, etc.)
            
        Returns:
            List of MarketDataPoint objects
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connection is active.
        
        Returns:
            bool: True if connected
        """
        pass


class ICredentialsManager(ABC):
    """Abstract interface for credentials management."""
    
    @abstractmethod
    def load_credentials(self) -> Dict[str, Any]:
        """Load credentials from storage.
        
        Returns:
            Dictionary of credentials
        """
        pass
    
    @abstractmethod
    def save_credentials(self, credentials: Dict[str, Any]) -> bool:
        """Save credentials to storage.
        
        Args:
            credentials: Dictionary of credentials
            
        Returns:
            bool: True if save successful
        """
        pass
    
    @abstractmethod
    def validate_credentials(self) -> bool:
        """Validate loaded credentials.
        
        Returns:
            bool: True if credentials are valid
        """
        pass
    
    @abstractmethod
    def refresh_credentials(self) -> bool:
        """Refresh expired credentials if possible.
        
        Returns:
            bool: True if refresh successful
        """
        pass


class DataSourceFactory:
    """Factory for creating data source instances."""
    
    _registry: Dict[DataSourceType, type] = {}
    
    @classmethod
    def register(cls, source_type: DataSourceType, implementation: type):
        """Register a data source implementation.
        
        Args:
            source_type: Type of data source
            implementation: Class implementing IDataSource
        """
        if not issubclass(implementation, IDataSource):
            raise TypeError(f"{implementation} must implement IDataSource")
        cls._registry[source_type] = implementation
    
    @classmethod
    def create(
        cls,
        source_type: DataSourceType,
        credentials_manager: Optional[ICredentialsManager] = None,
        **kwargs
    ) -> IDataSource:
        """Create a data source instance.
        
        Args:
            source_type: Type of data source to create
            credentials_manager: Optional credentials manager
            **kwargs: Additional arguments for the data source
            
        Returns:
            IDataSource instance
            
        Raises:
            ValueError: If source type not registered
        """
        if source_type not in cls._registry:
            raise ValueError(
                f"Data source type {source_type} not registered. "
                f"Available: {list(cls._registry.keys())}"
            )
        
        implementation = cls._registry[source_type]
        return implementation(credentials_manager=credentials_manager, **kwargs)


class MockDataSource(IDataSource):
    """Mock data source for testing."""
    
    def __init__(self, credentials_manager: Optional[ICredentialsManager] = None):
        self._connected = False
        self._subscriptions: List[str] = []
    
    def connect(self) -> bool:
        """Simulate connection."""
        self._connected = True
        return True
    
    def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
    
    def subscribe(self, instruments: List[str]) -> bool:
        """Simulate subscription."""
        self._subscriptions.extend(instruments)
        return True
    
    def get_latest_tick(self, instrument: str) -> Optional[MarketDataPoint]:
        """Return mock tick data."""
        if not self._connected or instrument not in self._subscriptions:
            return None
        
        return MarketDataPoint(
            instrument=instrument,
            timestamp=datetime.now(),
            price=50000.0,
            volume=100.0,
        )
    
    def get_historical_data(
        self,
        instrument: str,
        from_date: datetime,
        to_date: datetime,
        interval: str = "1min"
    ) -> List[MarketDataPoint]:
        """Return mock historical data."""
        return []
    
    def is_connected(self) -> bool:
        """Check mock connection status."""
        return self._connected


# Register mock data source
DataSourceFactory.register(DataSourceType.MOCK, MockDataSource)
