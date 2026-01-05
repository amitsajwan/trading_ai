"""Tests for data source abstraction layer."""

import pytest
from datetime import datetime
from data.data_source_interface import (
    DataSourceType,
    DataSourceFactory,
    MarketDataPoint,
    MockDataSource,
    IDataSource,
    ICredentialsManager,
)


class TestMarketDataPoint:
    """Test MarketDataPoint standardization."""
    
    def test_basic_creation(self):
        """Test creating basic market data point."""
        dp = MarketDataPoint(
            instrument="BTC-USD",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            price=50000.0,
            volume=10.5,
        )
        
        assert dp.instrument == "BTC-USD"
        assert dp.price == 50000.0
        assert dp.volume == 10.5
        assert dp.high == 50000.0  # Defaults to price
        assert dp.low == 50000.0
        assert dp.open == 50000.0
        assert dp.close == 50000.0
    
    def test_full_ohlc_creation(self):
        """Test creating with full OHLC data."""
        dp = MarketDataPoint(
            instrument="NIFTY BANK",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            price=45000.0,
            volume=1000.0,
            high=45500.0,
            low=44500.0,
            open=44800.0,
            close=45200.0,
        )
        
        assert dp.high == 45500.0
        assert dp.low == 44500.0
        assert dp.open == 44800.0
        assert dp.close == 45200.0
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        dp = MarketDataPoint(
            instrument="TEST",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            price=100.0,
            volume=50.0,
        )
        
        result = dp.to_dict()
        
        assert result["instrument"] == "TEST"
        assert result["price"] == 100.0
        assert result["volume"] == 50.0
        assert "timestamp" in result


class TestDataSourceFactory:
    """Test factory pattern for data sources."""
    
    def test_mock_source_registered(self):
        """Test that mock source is registered."""
        source = DataSourceFactory.create(DataSourceType.MOCK)
        assert isinstance(source, MockDataSource)
        assert isinstance(source, IDataSource)
    
    def test_invalid_source_type(self):
        """Test error on invalid source type."""
        with pytest.raises(ValueError, match="not registered"):
            # Try to create unregistered source
            DataSourceFactory.create(DataSourceType.ZERODHA)
    
    def test_register_custom_source(self):
        """Test registering custom data source."""
        
        class CustomSource(IDataSource):
            def __init__(self, credentials_manager=None, **kwargs):
                self.credentials_manager = credentials_manager
            
            def connect(self) -> bool:
                return True
            
            def disconnect(self) -> None:
                pass
            
            def subscribe(self, instruments):
                return True
            
            def get_latest_tick(self, instrument):
                return None
            
            def get_historical_data(self, instrument, from_date, to_date, interval="1min"):
                return []
            
            def is_connected(self) -> bool:
                return True
        
        # Should not raise error
        DataSourceFactory.register(DataSourceType.CRYPTO, CustomSource)
        
        source = DataSourceFactory.create(DataSourceType.CRYPTO)
        assert isinstance(source, CustomSource)
    
    def test_register_invalid_implementation(self):
        """Test error when registering non-IDataSource class."""
        
        class InvalidSource:
            pass
        
        with pytest.raises(TypeError, match="must implement IDataSource"):
            DataSourceFactory.register(DataSourceType.CRYPTO, InvalidSource)


class TestMockDataSource:
    """Test mock data source for testing."""
    
    def test_connection_lifecycle(self):
        """Test connect/disconnect."""
        source = MockDataSource()
        
        assert not source.is_connected()
        
        assert source.connect()
        assert source.is_connected()
        
        source.disconnect()
        assert not source.is_connected()
    
    def test_subscription(self):
        """Test instrument subscription."""
        source = MockDataSource()
        source.connect()
        
        instruments = ["BTC-USD", "NIFTY BANK"]
        assert source.subscribe(instruments)
        
        # Should be able to get data for subscribed instruments
        tick = source.get_latest_tick("BTC-USD")
        assert tick is not None
        assert tick.instrument == "BTC-USD"
    
    def test_no_data_when_disconnected(self):
        """Test that no data is returned when disconnected."""
        source = MockDataSource()
        source.subscribe(["BTC-USD"])
        
        # Not connected yet
        tick = source.get_latest_tick("BTC-USD")
        assert tick is None
    
    def test_no_data_for_unsubscribed(self):
        """Test that no data is returned for unsubscribed instruments."""
        source = MockDataSource()
        source.connect()
        source.subscribe(["BTC-USD"])
        
        # Try to get data for unsubscribed instrument
        tick = source.get_latest_tick("NIFTY 50")
        assert tick is None
    
    def test_mock_tick_data(self):
        """Test mock tick data structure."""
        source = MockDataSource()
        source.connect()
        source.subscribe(["TEST"])
        
        tick = source.get_latest_tick("TEST")
        
        assert isinstance(tick, MarketDataPoint)
        assert tick.instrument == "TEST"
        assert tick.price > 0
        assert tick.volume > 0
        assert isinstance(tick.timestamp, datetime)


class TestLooseCoupling:
    """Test that abstraction enables loose coupling."""
    
    def test_source_interchangeability(self):
        """Test that different sources can be swapped."""
        
        def process_data(source: IDataSource, instrument: str):
            """Function that works with any IDataSource implementation."""
            if source.connect():
                source.subscribe([instrument])
                tick = source.get_latest_tick(instrument)
                source.disconnect()
                return tick
            return None
        
        # Should work with mock source
        mock = MockDataSource()
        result = process_data(mock, "BTC-USD")
        assert result is not None
    
    def test_factory_enables_dependency_injection(self):
        """Test factory pattern for dependency injection."""
        
        class TradingService:
            """Service that depends on data source."""
            
            def __init__(self, source_type: DataSourceType):
                self.data_source = DataSourceFactory.create(source_type)
            
            def get_price(self, instrument: str) -> float:
                self.data_source.connect()
                self.data_source.subscribe([instrument])
                tick = self.data_source.get_latest_tick(instrument)
                return tick.price if tick else 0.0
        
        # Can easily inject different implementations
        service = TradingService(DataSourceType.MOCK)
        price = service.get_price("TEST")
        assert price > 0
    
    def test_credentials_manager_abstraction(self):
        """Test that credentials manager is properly abstracted."""
        
        class MockCredentialsManager(ICredentialsManager):
            def load_credentials(self):
                return {"api_key": "test"}
            
            def save_credentials(self, credentials):
                return True
            
            def validate_credentials(self):
                return True
            
            def refresh_credentials(self):
                return True
        
        # Data source should accept any ICredentialsManager implementation
        creds_mgr = MockCredentialsManager()
        source = MockDataSource(credentials_manager=creds_mgr)
        
        assert source is not None
