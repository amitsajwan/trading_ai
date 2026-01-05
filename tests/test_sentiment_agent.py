import pytest
from agents.sentiment_agent import SentimentAnalysisAgent
from agents.state import AgentState


def test_sentiment_agent_no_news_fallback():
    agent = SentimentAnalysisAgent()
    state = AgentState()
    state.latest_news = []  # explicit no news
    # Set sentiment_score to None-case is not supported by AgentState type, so leave as default 0.0

    updated = agent.process(state)

    sa = updated.sentiment_analysis
    assert sa.get("retail_sentiment_reasoning") == "No recent news available"
    assert sa.get("institutional_sentiment_reasoning") == "Insufficient data to assess"
    assert sa.get("confidence_score") == pytest.approx(0.10, rel=1e-3)
    assert sa.get("sentiment_divergence") == "NONE"
