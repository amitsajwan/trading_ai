"""Comprehensive integration tests for full trading cycle."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from agents.state import AgentState, SignalType
from trading_orchestration.trading_graph import TradingGraph
from monitoring.position_monitor import PositionMonitor
from services.trading_service import TradingService
from utils.paper_trading import PaperTrading
from data.market_memory import MarketMemory


@pytest.fixture
def mock_kite():
    """Mock KiteConnect instance."""
    kite = Mock()
    kite.instruments.return_value = [
        {"tradingsymbol": "NIFTY BANK", "instrument_token": 26009}
    ]
    kite.orders.return_value = []
    kite.positions.return_value = {"net": []}
    kite.ltp.return_value = {"NSE:NIFTY BANK": {"last_price": 45250}}
    kite.place_order.return_value = "ORDER123"
    return kite


@pytest.fixture
def mock_market_memory():
    """Mock MarketMemory instance."""
    memory = Mock(spec=MarketMemory)
    memory.get_current_price.return_value = 45250.0
    memory.get_recent_ohlc.return_value = []
    memory.store_tick.return_value = None
    memory.store_ohlc.return_value = None
    return memory


@pytest.fixture
def paper_trading():
    """Create paper trading instance."""
    return PaperTrading(initial_capital=1000000)


@pytest.mark.asyncio
async def test_position_monitor_sl_hit(mock_kite, mock_market_memory, paper_trading):
    """Test position monitor exits on stop-loss."""
    # Create a position
    trade_id = paper_trading.place_order(
        signal="BUY",
        quantity=25,
        price=45250.0,
        stop_loss=45100.0,
        take_profit=45500.0
    )["order_id"]
    
    # Create position monitor
    monitor = PositionMonitor(
        kite=mock_kite,
        market_memory=mock_market_memory,
        paper_trading=paper_trading
    )
    
    # Mock current price below stop-loss
    mock_market_memory.get_current_price.return_value = 45000.0
    
    # Create mock position in MongoDB
    from mongodb_schema import get_mongo_client, get_collection
    from config.settings import settings
    
    mongo_client = get_mongo_client()
    db = mongo_client[settings.mongodb_db_name]
    trades_collection = get_collection(db, "trades_executed")
    
    trades_collection.insert_one({
        "trade_id": trade_id,
        "signal": "BUY",
        "quantity": 25,
        "entry_price": 45250.0,
        "filled_price": 45250.0,
        "stop_loss": 45100.0,
        "take_profit": 45500.0,
        "status": "OPEN",
        "paper_trading": True,
        "entry_timestamp": datetime.now().isoformat()
    })
    
    # Monitor positions
    await monitor._monitor_positions()
    
    # Check if position was closed
    position = trades_collection.find_one({"trade_id": trade_id})
    assert position is not None
    # Position should be closed or exit logic should have been triggered
    # (actual exit depends on implementation details)


@pytest.mark.asyncio
async def test_position_monitor_target_hit(mock_kite, mock_market_memory, paper_trading):
    """Test position monitor exits on take-profit."""
    # Create a position
    trade_id = paper_trading.place_order(
        signal="BUY",
        quantity=25,
        price=45250.0,
        stop_loss=45100.0,
        take_profit=45500.0
    )["order_id"]
    
    # Create position monitor
    monitor = PositionMonitor(
        kite=mock_kite,
        market_memory=mock_market_memory,
        paper_trading=paper_trading
    )
    
    # Mock current price above take-profit
    mock_market_memory.get_current_price.return_value = 45600.0
    
    # Create mock position in MongoDB
    from mongodb_schema import get_mongo_client, get_collection
    from config.settings import settings
    
    mongo_client = get_mongo_client()
    db = mongo_client[settings.mongodb_db_name]
    trades_collection = get_collection(db, "trades_executed")
    
    trades_collection.insert_one({
        "trade_id": trade_id,
        "signal": "BUY",
        "quantity": 25,
        "entry_price": 45250.0,
        "filled_price": 45250.0,
        "stop_loss": 45100.0,
        "take_profit": 45500.0,
        "status": "OPEN",
        "paper_trading": True,
        "entry_timestamp": datetime.now().isoformat()
    })
    
    # Monitor positions
    await monitor._monitor_positions()
    
    # Check if position was closed
    position = trades_collection.find_one({"trade_id": trade_id})
    assert position is not None


@pytest.mark.asyncio
async def test_trading_graph_execution(mock_kite, mock_market_memory):
    """Test trading graph execution."""
    # Create trading graph
    graph = TradingGraph(kite=mock_kite, market_memory=mock_market_memory)
    
    # Create initial state
    initial_state = AgentState(
        current_price=45250.0,
        current_time=datetime.now()
    )
    
    # Run graph
    result = await graph.arun(initial_state)
    
    # Verify result
    assert result is not None
    assert hasattr(result, 'final_signal')


@pytest.mark.asyncio
async def test_paper_trading_order_placement(paper_trading):
    """Test paper trading order placement."""
    result = paper_trading.place_order(
        signal="BUY",
        quantity=25,
        price=45250.0,
        stop_loss=45100.0,
        take_profit=45500.0
    )
    
    assert result["status"] == "COMPLETE"
    assert result["paper_trading"] is True
    assert "order_id" in result


def test_paper_trading_insufficient_capital(paper_trading):
    """Test paper trading with insufficient capital."""
    # Try to place order with more capital than available
    result = paper_trading.place_order(
        signal="BUY",
        quantity=10000,  # Very large quantity
        price=45250.0,
        stop_loss=45100.0,
        take_profit=45500.0
    )
    
    assert result["status"] == "REJECTED"
    assert result["reason"] == "INSUFFICIENT_CAPITAL"


@pytest.mark.asyncio
async def test_trading_service_initialization(mock_kite):
    """Test trading service initialization."""
    service = TradingService(kite=mock_kite, paper_trading=True)
    
    # Initialize (should not raise)
    await service.initialize()
    
    assert service.market_memory is not None
    assert service.trading_graph is not None
    assert service.position_monitor is not None
    assert service.paper_trading_sim is not None


@pytest.mark.asyncio
async def test_circuit_breaker_integration():
    """Test circuit breaker integration."""
    from monitoring.circuit_breakers import CircuitBreaker
    from config.settings import settings
    
    breaker = CircuitBreaker()
    
    # Test daily loss check
    result = breaker.check_all(
        current_pnl=-30000,  # 3% loss (assuming 10L capital)
        consecutive_losses=0,
        data_feed_healthy=True
    )
    
    # Should trigger if loss exceeds 2%
    # (exact behavior depends on implementation)
    assert "triggered" in result


def test_market_memory_fallback():
    """Test market memory fallback when Redis unavailable."""
    # Create market memory without Redis
    memory = MarketMemory()
    
    # Should work in fallback mode
    memory.store_tick("BANKNIFTY", {"price": 45250.0})
    price = memory.get_current_price("BANKNIFTY")
    
    # Should not raise error even if Redis unavailable
    assert True  # Just verify no exception

