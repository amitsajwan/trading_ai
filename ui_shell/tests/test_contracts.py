"""Test UI Shell contracts and data structures."""

import pytest
from datetime import datetime

from ui_shell.contracts import (
    DecisionDisplay,
    PortfolioSummary,
    MarketOverview,
    UserAction,
    BuyOverride,
    SellOverride,
    StopLossUpdate,
    RiskLimitUpdate,
)


class TestDataStructures:
    """Test UI data structures."""

    def test_decision_display_creation(self):
        """Test DecisionDisplay dataclass creation."""
        decision = DecisionDisplay(
            instrument="NIFTY",
            signal="BUY",
            confidence=0.85,
            reasoning="Strong uptrend detected",
            timestamp=datetime.utcnow()
        )

        assert decision.instrument == "NIFTY"
        assert decision.signal == "BUY"
        assert decision.confidence == 0.85
        assert decision.reasoning == "Strong uptrend detected"
        assert isinstance(decision.timestamp, datetime)

    def test_portfolio_summary_creation(self):
        """Test PortfolioSummary dataclass creation."""
        portfolio = PortfolioSummary(
            total_value=250000.0,
            cash_balance=150000.0,
            positions={"NIFTY": {"quantity": 10, "pnl": 1500.0}},
            pnl_today=1250.0,
            pnl_total=8500.0,
            timestamp=datetime.utcnow()
        )

        assert portfolio.total_value == 250000.0
        assert portfolio.cash_balance == 150000.0
        assert portfolio.positions["NIFTY"]["quantity"] == 10
        assert portfolio.pnl_today == 1250.0
        assert portfolio.pnl_total == 8500.0

    def test_market_overview_creation(self):
        """Test MarketOverview dataclass creation."""
        overview = MarketOverview(
            nifty_price=22150.5,
            banknifty_price=47250.8,
            market_status="OPEN",
            volume_24h=1500000,
            timestamp=datetime.utcnow()
        )

        assert overview.nifty_price == 22150.5
        assert overview.banknifty_price == 47250.8
        assert overview.market_status == "OPEN"
        assert overview.volume_24h == 1500000


class TestUserActions:
    """Test user action classes."""

    def test_buy_override_creation(self):
        """Test BuyOverride action creation."""
        action = BuyOverride("NIFTY", 10, 22000.0)

        assert action.action_type == "BUY_OVERRIDE"
        assert action.instrument == "NIFTY"
        assert action.quantity == 10
        assert action.price_limit == 22000.0
        assert isinstance(action.timestamp, datetime)

    def test_sell_override_creation(self):
        """Test SellOverride action creation."""
        action = SellOverride("BANKNIFTY", 5)

        assert action.action_type == "SELL_OVERRIDE"
        assert action.instrument == "BANKNIFTY"
        assert action.quantity == 5
        assert action.price_limit is None

    def test_stop_loss_update_creation(self):
        """Test StopLossUpdate action creation."""
        action = StopLossUpdate("NIFTY", 21800.0)

        assert action.action_type == "STOP_LOSS_UPDATE"
        assert action.instrument == "NIFTY"
        assert action.stop_loss_price == 21800.0

    def test_risk_limit_update_creation(self):
        """Test RiskLimitUpdate action creation."""
        action = RiskLimitUpdate(50000.0, 10000.0)

        assert action.action_type == "RISK_LIMIT_UPDATE"
        assert action.max_position_size == 50000.0
        assert action.max_daily_loss == 10000.0


class TestBaseUserAction:
    """Test base UserAction class."""

    def test_user_action_creation(self):
        """Test base UserAction creation."""
        action = UserAction("CUSTOM_ACTION", param1="value1", param2=42)

        assert action.action_type == "CUSTOM_ACTION"
        assert action.param1 == "value1"
        assert action.param2 == 42
        assert isinstance(action.timestamp, datetime)

