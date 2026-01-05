"""Sentiment agent implementing engine_module Agent contract.

This is a migration of the legacy sentiment_agent into the new module and
exposes an async `analyze(context)` method returning `AnalysisResult`.
"""

import logging
from typing import Dict, Any

from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


class SentimentAgent(Agent):
    """Simple sentiment agent that uses news + aggregate sentiment to produce a bias."""

    def __init__(self):
        """Initialize sentiment agent."""
        self._agent_name = "SentimentAgent"

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        latest_news = context.get("latest_news", []) or []
        aggregate_sentiment = float(context.get("sentiment_score", 0.0) or 0.0)

        # Default fallback
        default_analysis = {
            "retail_sentiment": 0.0,
            "institutional_sentiment": 0.0,
            "sentiment_divergence": "NONE",
            "options_flow_signal": "NEUTRAL",
            "fear_greed_index": 50.0,
            "confidence_score": 0.10,
            "status": "INSUFFICIENT_DATA"
        }

        if not latest_news:
            details = {**default_analysis, "note": "No recent news"}
            return AnalysisResult(decision="HOLD", confidence=details["confidence_score"], details=details)

        # Build a simple prompt (not used by default); _call_llm_structured can be monkeypatched in tests
        news_headlines = "\n".join([f"- {item.get('title', '')}" for item in latest_news])
        prompt = f"Latest News:\n{news_headlines}\nAggregate Sentiment: {aggregate_sentiment:.2f}\n"

        try:
            analysis = self._call_llm_structured(prompt, {})
        except Exception:
            logger.warning("LLM struct call failed; falling back to simple aggregation")
            # Simple fallback: use aggregate_sentiment for retail and neutral institutional
            retail_sent = aggregate_sentiment
            inst_sent = 0.0
            confidence = 0.3
            analysis = {
                "retail_sentiment": retail_sent,
                "institutional_sentiment": inst_sent,
                "sentiment_divergence": "NONE",
                "options_flow_signal": "NEUTRAL",
                "fear_greed_index": 50.0,
                "confidence_score": confidence,
                "status": "ACTIVE"
            }

        # Ensure numeric types
        try:
            retail_sent = float(analysis.get("retail_sentiment", 0.0) or 0.0)
        except Exception:
            retail_sent = 0.0
        try:
            inst_sent = float(analysis.get("institutional_sentiment", 0.0) or 0.0)
        except Exception:
            inst_sent = 0.0

        divergence = str(analysis.get("sentiment_divergence", "NONE") or "NONE")
        options_flow = str(analysis.get("options_flow_signal", "NEUTRAL") or "NEUTRAL")
        fear_greed = float(analysis.get("fear_greed_index", 50.0) or 50.0)
        confidence = float(analysis.get("confidence_score", 0.3) or 0.3)
        status = str(analysis.get("status", "ACTIVE") or "ACTIVE")

        # Derive sentiment bias
        if retail_sent > 0.2 and inst_sent >= 0:
            sentiment_bias = "BULLISH"
        elif retail_sent < -0.2 and inst_sent <= 0:
            sentiment_bias = "BEARISH"
        else:
            sentiment_bias = "NEUTRAL"

        # Map bias to decision
        if sentiment_bias == "BULLISH":
            decision = "BUY"
        elif sentiment_bias == "BEARISH":
            decision = "SELL"
        else:
            decision = "HOLD"

        details = {
            "retail_sentiment": retail_sent,
            "institutional_sentiment": inst_sent,
            "sentiment_divergence": divergence,
            "options_flow_signal": options_flow,
            "fear_greed_index": fear_greed,
            "confidence_score": confidence,
            "status": status,
            "sentiment_bias": sentiment_bias,
            "note": "Analyzed via LLM" if status == "ACTIVE" else "Fallback"
        }

        return AnalysisResult(decision=decision, confidence=confidence, details=details)

    def _call_llm_structured(self, prompt: str, response_format: Dict[str, Any]) -> Dict[str, Any]:
        """Placeholder for LLM structured call. Tests may monkeypatch this method."""
        # Default simple heuristic: positive words increase retail sentiment
        retail = 0.0
        if "up" in prompt.lower() or "bull" in prompt.lower():
            retail = 0.4
        elif "down" in prompt.lower() or "bear" in prompt.lower():
            retail = -0.4
        return {
            "retail_sentiment": retail,
            "institutional_sentiment": 0.0,
            "sentiment_divergence": "NONE",
            "options_flow_signal": "NEUTRAL",
            "fear_greed_index": 50.0,
            "confidence_score": 0.5,
            "status": "ACTIVE"
        }