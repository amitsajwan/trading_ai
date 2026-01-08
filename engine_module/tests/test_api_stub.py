"""Tests for engine_module API facade and orchestrator stub."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from engine_module.api import build_orchestrator
from engine_module.contracts import AnalysisResult


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for dependency injection."""
    client = MagicMock()
    client.request = AsyncMock(return_value=MagicMock(content="Mock LLM response"))
    return client


@pytest.fixture
def mock_market_store():
    """Mock market store for dependency injection."""
    store = MagicMock()
    store.get_latest_ticks = AsyncMock(return_value=[])
    store.get_ohlc = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_options_data():
    """Mock options data source for dependency injection."""
    options = MagicMock()
    options.fetch_chain = AsyncMock(return_value={"available": True, "chain": []})
    return options


def test_build_orchestrator_returns_orchestrator_instance(
    mock_llm_client, mock_market_store, mock_options_data
):
    """Verify build_orchestrator factory returns orchestrator with injected deps."""
    orchestrator = build_orchestrator(
        llm_client=mock_llm_client,
        market_store=mock_market_store,
        options_data=mock_options_data,
    )

    assert orchestrator is not None
    assert hasattr(orchestrator, "run_cycle")
    assert orchestrator.llm_client is mock_llm_client
    assert orchestrator.market_data_provider is mock_market_store  # Updated attribute name
    assert orchestrator.options_data_provider is mock_options_data  # Updated attribute name


def test_build_orchestrator_accepts_optional_agents(
    mock_llm_client, mock_market_store, mock_options_data
):
    """Verify orchestrator accepts optional agent list."""
    mock_agent = MagicMock()
    orchestrator = build_orchestrator(
        llm_client=mock_llm_client,
        market_store=mock_market_store,
        options_data=mock_options_data,
        agents=[mock_agent],
    )

    assert len(orchestrator.agents) == 1
    assert orchestrator.agents[0] is mock_agent


@pytest.mark.asyncio
async def test_orchestrator_run_cycle_returns_analysis_result(
    mock_llm_client, mock_market_store, mock_options_data
):
    """Verify run_cycle returns AnalysisResult (stub implementation)."""
    orchestrator = build_orchestrator(
        llm_client=mock_llm_client,
        market_store=mock_market_store,
        options_data=mock_options_data,
    )

    result = await orchestrator.run_cycle(
        context={"instrument": "BANKNIFTY", "timestamp": datetime.now()}
    )

    assert isinstance(result, AnalysisResult)
    assert result.decision == "HOLD"  # Stub returns HOLD
    assert result.confidence == 0.0
    assert "Stub orchestrator" in result.details["reasoning"]
    assert result.details["instrument"] == "BANKNIFTY"


@pytest.mark.asyncio
async def test_orchestrator_run_cycle_with_default_context(
    mock_llm_client, mock_market_store, mock_options_data
):
    """Verify run_cycle handles empty context with defaults."""
    orchestrator = build_orchestrator(
        llm_client=mock_llm_client,
        market_store=mock_market_store,
        options_data=mock_options_data,
    )

    result = await orchestrator.run_cycle(context={})

    assert result.details["instrument"] == "BANKNIFTY"  # Default instrument for options
    assert "timestamp" in result.details

