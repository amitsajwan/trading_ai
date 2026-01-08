"""Test UI Dispatcher implementations."""

import pytest
from datetime import datetime

from ui_shell.dispatchers import EngineActionDispatcher, MockEngineInterface
from ui_shell.contracts import BuyOverride, SellOverride, StopLossUpdate, RiskLimitUpdate


class TestMockEngineInterface:
    """Test mock engine interface for dispatchers."""

    @pytest.fixture
    def mock_engine(self):
        """Create mock engine interface."""
        return MockEngineInterface()

    @pytest.mark.asyncio
    async def test_process_buy_override(self, mock_engine):
        """Test mock engine processes buy override."""
        action = BuyOverride("NIFTY", 10, 22000.0)
        result = await mock_engine.process_user_override(action)

        assert result["status"] == "queued"
        assert "buy_NIFTY" in result["action_id"]
        assert result["details"]["instrument"] == "NIFTY"
        assert result["details"]["quantity"] == 10
        assert result["details"]["price_limit"] == 22000.0

    @pytest.mark.asyncio
    async def test_process_sell_override(self, mock_engine):
        """Test mock engine processes sell override."""
        action = SellOverride("BANKNIFTY", 5)
        result = await mock_engine.process_user_override(action)

        assert result["status"] == "queued"
        assert "sell_BANKNIFTY" in result["action_id"]
        assert result["details"]["instrument"] == "BANKNIFTY"
        assert result["details"]["quantity"] == 5

    @pytest.mark.asyncio
    async def test_process_stop_loss_update(self, mock_engine):
        """Test mock engine processes stop loss update."""
        action = StopLossUpdate("NIFTY", 21800.0)
        result = await mock_engine.process_user_override(action)

        assert result["status"] == "updated"
        assert result["details"]["instrument"] == "NIFTY"
        assert result["details"]["stop_loss_price"] == 21800.0

    @pytest.mark.asyncio
    async def test_pause_trading(self, mock_engine):
        """Test mock engine pause trading."""
        result = await mock_engine.pause_trading("User requested")

        assert result["status"] == "paused"
        assert result["reason"] == "User requested"

    @pytest.mark.asyncio
    async def test_resume_trading(self, mock_engine):
        """Test mock engine resume trading."""
        result = await mock_engine.resume_trading()

        assert result["status"] == "resumed"

    @pytest.mark.asyncio
    async def test_emergency_stop(self, mock_engine):
        """Test mock engine emergency stop."""
        result = await mock_engine.emergency_stop("Critical issue")

        assert result["status"] == "stopped"
        assert result["reason"] == "Critical issue"
        assert result["alert_level"] == "critical"


class TestEngineActionDispatcher:
    """Test EngineActionDispatcher implementation."""

    @pytest.fixture
    def dispatcher(self):
        """Create action dispatcher with mock engine."""
        return EngineActionDispatcher()

    @pytest.mark.asyncio
    async def test_submit_buy_override(self, dispatcher):
        """Test dispatcher handles buy override."""
        action = BuyOverride("NIFTY", 10, 22000.0)
        result = await dispatcher.submit_override(action)

        assert result["status"] == "queued"
        assert result["action_type"] == "BUY_OVERRIDE"
        assert "processed_at" in result
        assert result["details"]["instrument"] == "NIFTY"

    @pytest.mark.asyncio
    async def test_submit_sell_override(self, dispatcher):
        """Test dispatcher handles sell override."""
        action = SellOverride("BANKNIFTY", 5)
        result = await dispatcher.submit_override(action)

        assert result["status"] == "queued"
        assert result["action_type"] == "SELL_OVERRIDE"
        assert result["details"]["instrument"] == "BANKNIFTY"

    @pytest.mark.asyncio
    async def test_submit_stop_loss_update(self, dispatcher):
        """Test dispatcher handles stop loss update."""
        action = StopLossUpdate("NIFTY", 21800.0)
        result = await dispatcher.submit_override(action)

        assert result["status"] == "updated"
        assert result["action_type"] == "STOP_LOSS_UPDATE"
        assert result["details"]["stop_loss_price"] == 21800.0

    @pytest.mark.asyncio
    async def test_submit_risk_limit_update(self, dispatcher):
        """Test dispatcher handles risk limit update."""
        action = RiskLimitUpdate(50000.0, 10000.0)
        result = await dispatcher.submit_override(action)

        assert result["status"] == "updated"
        assert result["action_type"] == "RISK_LIMIT_UPDATE"
        assert result["details"]["max_position_size"] == 50000.0
        assert result["details"]["max_daily_loss"] == 10000.0

    @pytest.mark.asyncio
    async def test_pause_trading(self, dispatcher):
        """Test dispatcher pause trading."""
        result = await dispatcher.pause_trading("Testing pause")

        assert result["status"] == "paused"
        assert result["reason"] == "Testing pause"

    @pytest.mark.asyncio
    async def test_resume_trading(self, dispatcher):
        """Test dispatcher resume trading."""
        result = await dispatcher.resume_trading()

        assert result["status"] == "resumed"

    @pytest.mark.asyncio
    async def test_emergency_stop(self, dispatcher):
        """Test dispatcher emergency stop."""
        result = await dispatcher.emergency_stop("Test emergency")

        assert result["status"] == "stopped"
        assert result["reason"] == "Test emergency"
        assert result["alert_level"] == "critical"

    @pytest.mark.asyncio
    async def test_invalid_action(self, dispatcher):
        """Test dispatcher handles invalid actions."""
        result = await dispatcher.submit_override("invalid_action")

        assert result["status"] == "error"
        assert "Invalid action type" in result["message"]

    @pytest.mark.asyncio
    async def test_dispatcher_with_custom_engine(self):
        """Test dispatcher with custom engine interface."""

        class CustomEngine:
            async def process_user_override(self, action):
                return {"status": "custom_processed", "action": action.action_type}

        dispatcher = EngineActionDispatcher(CustomEngine())
        action = BuyOverride("NIFTY", 10)
        result = await dispatcher.submit_override(action)

        assert result["status"] == "custom_processed"
        assert result["action"] == "BUY_OVERRIDE"

