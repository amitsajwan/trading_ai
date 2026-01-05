"""Basic tests for user module functionality."""

import pytest
import sys
import os
from decimal import Decimal
from datetime import datetime

# Add module src to path for proper imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'user_module', 'src'))

from user_module.contracts import UserAccount, TradeExecutionRequest
from user_module.services import RiskProfileManager


class TestRiskProfileManager:
    """Test risk profile management."""

    def test_get_risk_profile_conservative(self):
        """Test conservative risk profile."""
        manager = RiskProfileManager(None)
        profile = manager.get_risk_profile("conservative")

        assert profile["max_daily_loss_pct"] == 2.0
        assert profile["max_position_size_pct"] == 5.0
        assert profile["stop_loss_required"] is True

    def test_get_risk_profile_aggressive(self):
        """Test aggressive risk profile."""
        manager = RiskProfileManager(None)
        profile = manager.get_risk_profile("aggressive")

        assert profile["max_daily_loss_pct"] == 10.0
        assert profile["max_position_size_pct"] == 20.0
        assert profile["stop_loss_required"] is False

    def test_get_risk_profile_default(self):
        """Test default (moderate) risk profile."""
        manager = RiskProfileManager(None)
        profile = manager.get_risk_profile("unknown")

        assert profile["max_daily_loss_pct"] == 5.0  # Moderate default


class TestDataContracts:
    """Test data contract creation."""

    def test_user_account_creation(self):
        """Test UserAccount dataclass."""
        user = UserAccount(
            user_id="user123",
            email="test@example.com",
            full_name="Test User",
            created_at=datetime.utcnow(),
            risk_profile="moderate"
        )

        assert user.user_id == "user123"
        assert user.email == "test@example.com"
        assert user.risk_profile == "moderate"

    def test_trade_execution_request(self):
        """Test TradeExecutionRequest creation."""
        request = TradeExecutionRequest(
            user_id="user123",
            instrument="BANKNIFTY",
            side="BUY",
            quantity=10,
            order_type="MARKET",
            stop_loss_price=Decimal("44000")
        )

        assert request.user_id == "user123"
        assert request.instrument == "BANKNIFTY"
        assert request.side == "BUY"
        assert request.quantity == 10
        assert request.stop_loss_price == Decimal("44000")


class TestAPIFunctions:
    """Test API facade functions."""

    def test_build_user_module_structure(self):
        """Test build_user_module returns correct structure."""
        # We can't test with actual MongoDB, but we can test the structure
        # This would normally be integration tested
        pass

    def test_imports(self):
        """Test that all expected classes can be imported."""
        from user_module import (
            UserAccount, MongoUserStore, RiskProfileManager,
            build_user_store, create_user_account
        )

        # Just test that imports work
        assert UserAccount is not None
        assert MongoUserStore is not None
        assert RiskProfileManager is not None
        assert build_user_store is not None
        assert create_user_account is not None
