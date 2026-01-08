import pytest
from engine_module.agents.sentiment_agent import SentimentAgent
from engine_module.contracts import AnalysisResult


@pytest.mark.asyncio
async def test_sentiment_agent_no_news():
    agent = SentimentAgent()
    res = await agent.analyze({})
    assert isinstance(res, AnalysisResult)
    assert res.decision == "HOLD"
    assert abs(res.confidence - 0.1) < 1e-6
    assert res.details["status"] == "INSUFFICIENT_DATA"


@pytest.mark.asyncio
async def test_sentiment_agent_with_news_and_llm(monkeypatch):
    agent = SentimentAgent()

    def fake_llm(prompt, rf):
        return {
            "retail_sentiment": 0.6,
            "institutional_sentiment": 0.1,
            "sentiment_divergence": "NONE",
            "options_flow_signal": "NEUTRAL",
            "fear_greed_index": 60.0,
            "confidence_score": 0.8,
            "status": "ACTIVE"
        }

    monkeypatch.setattr(agent, "_call_llm_structured", fake_llm)

    news = [{"title": "Market rallies as bulls take charge"}]
    res = await agent.analyze({"latest_news": news, "sentiment_score": 0.2})

    assert res.decision == "BUY"
    assert abs(res.confidence - 0.8) < 1e-6
    assert res.details["sentiment_bias"] == "BULLISH"
    assert res.details["retail_sentiment"] == 0.6

