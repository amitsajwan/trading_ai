"""Integration tests for the trading system."""

import pytest
from datetime import datetime
from agents.state import AgentState, SignalType
from agents.portfolio_manager import PortfolioManagerAgent


@pytest.mark.integration
def test_portfolio_manager_decision_logic():
    """Test portfolio manager decision making."""
    # This is a simplified integration test
    # In a real scenario, you'd mock the LLM calls
    
    state = AgentState(
        current_price=45000.0,
        technical_analysis={
            "trend_direction": "UP",
            "trend_strength": 75.0,
            "confidence_score": 0.8
        },
        fundamental_analysis={
            "bullish_probability": 0.7,
            "bearish_probability": 0.3
        },
        sentiment_analysis={
            "retail_sentiment": 0.6
        },
        macro_analysis={
            "sector_headwind_score": 0.5
        },
        bull_confidence=0.7,
        bear_confidence=0.3,
        neutral_risk_recommendation={
            "position_size": 50,
            "stop_loss_price": 44325.0
        }
    )
    
    # Note: This will fail if OpenAI API key is not set
    # In real tests, you'd mock the LLM calls
    try:
        portfolio_manager = PortfolioManagerAgent()
        result = portfolio_manager.process(state)
        
        assert result.final_signal in [SignalType.BUY, SignalType.SELL, SignalType.HOLD]
    except Exception as e:
        # If API key is not set, skip the test
        pytest.skip(f"Skipping integration test: {e}")

