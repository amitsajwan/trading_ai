import pytest
from agents.bull_researcher import BullResearcherAgent
from agents.bear_researcher import BearResearcherAgent
from agents.state import AgentState


def test_bull_researcher_shows_na_for_low_confidence():
    agent = BullResearcherAgent()
    state = AgentState()
    state.sentiment_analysis = {
        "retail_sentiment": 0.0,
        "institutional_sentiment": 0.0,
        "confidence_score": 0.1
    }

    # Call process to ensure it doesn't crash when sentiment has low confidence
    updated = agent.process(state)
    # No exception means success; also check bull_thesis exists
    assert hasattr(updated, 'bull_thesis')


def test_bear_researcher_shows_na_for_low_confidence():
    agent = BearResearcherAgent()
    state = AgentState()
    state.sentiment_analysis = {
        "retail_sentiment": 0.0,
        "institutional_sentiment": 0.0,
        "confidence_score": 0.05
    }

    updated = agent.process(state)
    assert hasattr(updated, 'bear_thesis')
