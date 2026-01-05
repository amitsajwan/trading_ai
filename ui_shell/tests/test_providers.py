"""Test UI Data Provider implementations."""

import pytest
from datetime import datetime

from ui_shell.providers import EngineDataProvider, MockEngineInterface
from ui_shell.contracts import DecisionDisplay, PortfolioSummary, MarketOverview


class TestMockEngineInterface:
    """Test mock engine interface."""

    @pytest.fixture
    def mock_engine(self):
        """Create mock engine interface."""
        return MockEngineInterface()

    @pytest.mark.asyncio
    async def test_get_latest_decision(self, mock_engine):
        """Test mock engine returns decision data."""
        decision = await mock_engine.get_latest_decision()

        assert isinstance(decision, dict)
        assert "instrument" in decision
        assert "signal" in decision
        assert "confidence" in decision
        assert "reasoning" in decision
        assert "timestamp" in decision

    @pytest.mark.asyncio
    async def test_get_portfolio_status(self, mock_engine):
        """Test mock engine returns portfolio data."""
        portfolio = await mock_engine.get_portfolio_status()

        assert isinstance(portfolio, dict)
        assert "total_value" in portfolio
        assert "cash_balance" in portfolio
        assert "positions" in portfolio
        assert "pnl_today" in portfolio
        assert "pnl_total" in portfolio


class TestEngineDataProvider:
    """Test EngineDataProvider implementation."""

    @pytest.fixture
    def provider(self):
        """Create data provider with mock engine."""
        return EngineDataProvider()

    @pytest.mark.asyncio
    async def test_get_latest_decision(self, provider):
        """Test provider returns DecisionDisplay."""
        decision = await provider.get_latest_decision()

        assert isinstance(decision, DecisionDisplay)
        assert decision.instrument == "NIFTY"
        assert decision.signal == "HOLD"
        assert isinstance(decision.confidence, float)
        assert isinstance(decision.reasoning, str)
        assert isinstance(decision.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_get_portfolio_summary(self, provider):
        """Test provider returns PortfolioSummary."""
        portfolio = await provider.get_portfolio_summary()

        assert isinstance(portfolio, PortfolioSummary)
        assert isinstance(portfolio.total_value, float)
        assert isinstance(portfolio.cash_balance, float)
        assert isinstance(portfolio.positions, dict)
        assert isinstance(portfolio.pnl_today, float)
        assert isinstance(portfolio.pnl_total, float)
        assert isinstance(portfolio.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_get_market_overview(self, provider):
        """Test provider returns MarketOverview."""
        overview = await provider.get_market_overview()

        assert isinstance(overview, MarketOverview)
        assert isinstance(overview.nifty_price, float)
        assert isinstance(overview.banknifty_price, float)
        assert overview.market_status in ["OPEN", "CLOSED", "PRE_OPEN", "UNKNOWN"]
        assert isinstance(overview.volume_24h, int)
        assert isinstance(overview.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_get_recent_decisions(self, provider):
        """Test provider returns recent decisions list."""
        # Get a decision first to populate cache
        await provider.get_latest_decision()

        recent = await provider.get_recent_decisions(limit=5)

        assert isinstance(recent, list)
        assert len(recent) <= 5
        if recent:
            assert isinstance(recent[0], DecisionDisplay)

    @pytest.mark.asyncio
    async def test_provider_with_custom_engine(self):
        """Test provider with custom engine interface."""

        class CustomEngine:
            async def get_latest_decision(self):
                return {
                    "instrument": "BANKNIFTY",
                    "signal": "BUY",
                    "confidence": 0.9,
                    "reasoning": "Custom engine decision",
                    "timestamp": datetime.utcnow()
                }

        provider = EngineDataProvider(CustomEngine())
        decision = await provider.get_latest_decision()

        assert decision.instrument == "BANKNIFTY"
        assert decision.signal == "BUY"
        assert decision.confidence == 0.9
        assert decision.reasoning == "Custom engine decision"
