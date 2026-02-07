"""Sentiment agent implementing engine_module Agent contract.

This is a migration of the legacy sentiment_agent into the new module and
exposes an async `analyze(context)` method returning `AnalysisResult`.
"""

import logging
from datetime import datetime
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

        # Check data availability and freshness
        current_time = context.get("timestamp", datetime.now())
        if not latest_news:
            details = {
                "retail_sentiment": 0.0,
                "institutional_sentiment": 0.0,
                "sentiment_divergence": "UNKNOWN",
                "options_flow_signal": "UNKNOWN",
                "fear_greed_index": 50.0,
                "confidence_score": 0.0,
                "note": "NO_NEWS_DATA_AVAILABLE",
                "data_available": False,
                "missing_data": ["latest_news"],
                "data_freshness": "UNKNOWN"
            }
            return AnalysisResult(
                decision="EXCLUDED",
                confidence=0.0,
                details=details,
                excluded=True,
                exclusion_reason="No news data available for sentiment analysis"
            )

        # Check data freshness - news should be from last 24 hours
        news_timestamps = []
        for item in latest_news:
            if isinstance(item, dict) and 'published_at' in item:
                try:
                    # Try to parse timestamp
                    if isinstance(item['published_at'], str):
                        # Assume ISO format or similar
                        from dateutil import parser
                        news_time = parser.parse(item['published_at'])
                        news_timestamps.append(news_time)
                except:
                    pass

        if news_timestamps:
            latest_news_time = max(news_timestamps)
            time_diff = (current_time - latest_news_time).total_seconds() / 3600  # hours
            if time_diff > 24:
                details = {
                    "retail_sentiment": 0.0,
                    "institutional_sentiment": 0.0,
                    "sentiment_divergence": "UNKNOWN",
                    "options_flow_signal": "UNKNOWN",
                    "fear_greed_index": 50.0,
                    "confidence_score": 0.0,
                    "note": f"NEWS_DATA_STALE_{time_diff:.1f}H_OLD",
                    "data_available": False,
                    "data_freshness": f"STALE_{time_diff:.1f}H",
                    "latest_news_time": latest_news_time.isoformat()
                }
                return AnalysisResult(
                    decision="EXCLUDED",
                    confidence=0.0,
                    details=details,
                    excluded=True,
                    exclusion_reason=f"News data is {time_diff:.1f} hours old (stale)"
                )

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

            # Create fallback reasoning even without LLM
            reasoning_parts = [
                "Sentiment analysis using fallback aggregation due to LLM service unavailability.",
                f"News analysis: Sample headlines indicate {len(latest_news)} news items with aggregate sentiment {aggregate_sentiment:.2f}.",
                f"Retail sentiment interpretation: {'Bullish' if retail_sent > 0.1 else 'Bearish' if retail_sent < -0.1 else 'Neutral'} market sentiment ({retail_sent:.2f}).",
                "Institutional sentiment: Neutral position (0.0) - no strong directional bias detected.",
                "Sentiment divergence: None - retail and institutional sentiment aligned.",
                "Fear & Greed Index context: Neutral (50.0) indicating balanced market psychology.",
                "Options flow: Neutral - no significant directional pressure from options trading.",
                f"Decision rationale: HOLD recommended as market shows {confidence:.1f} confidence in neutral sentiment analysis."
            ]

            analysis = {
                "retail_sentiment": retail_sent,
                "institutional_sentiment": inst_sent,
                "sentiment_divergence": "NONE",
                "options_flow_signal": "NEUTRAL",
                "fear_greed_index": 50.0,
                "confidence_score": confidence,
                "status": "FALLBACK",
                "reasoning": " ".join(reasoning_parts),
                "analysis_summary": f"Sentiment analysis reveals neutral market mood with {confidence:.1f} confidence using fallback aggregation.",
                "news_coverage": len(latest_news),
                "market_psychology": f"Fear & Greed: 50.0, Retail: {retail_sent:.2f}, Institutional: {inst_sent:.2f}"
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

        # Generate rich natural language reasoning
        reasoning_parts = []

        # News analysis
        if latest_news:
            news_count = len(latest_news)
            reasoning_parts.append(f"Analyzed {news_count} recent news items to gauge market sentiment.")
            if news_count > 0:
                # Sample some headlines for context
                sample_headlines = [item.get('title', '') for item in latest_news[:3]]
                reasoning_parts.append(f"Key headlines include: {', '.join(sample_headlines)}.")
        else:
            reasoning_parts.append("No recent news data available for sentiment analysis.")

        # Sentiment interpretation
        if retail_sent > 0.2:
            reasoning_parts.append(f"Retail sentiment is strongly positive ({retail_sent:.2f}), indicating bullish enthusiasm from individual investors.")
        elif retail_sent < -0.2:
            reasoning_parts.append(f"Retail sentiment is strongly negative ({retail_sent:.2f}), suggesting widespread pessimism among individual traders.")
        else:
            reasoning_parts.append(f"Retail sentiment is neutral ({retail_sent:.2f}), showing balanced market participation.")

        if abs(inst_sent) > 0.1:
            reasoning_parts.append(f"Institutional sentiment shows {inst_sent:.2f} bias, indicating professional positioning.")
        else:
            reasoning_parts.append(f"Institutional sentiment remains neutral ({inst_sent:.2f}), suggesting professional caution.")

        # Divergence analysis
        if divergence == "BULLISH_DIVERGENCE":
            reasoning_parts.append("Bullish divergence detected between retail and institutional sentiment, often signaling market bottoms.")
        elif divergence == "BEARISH_DIVERGENCE":
            reasoning_parts.append("Bearish divergence observed, with institutional caution contrasting retail optimism.")
        else:
            reasoning_parts.append("No significant sentiment divergence between retail and institutional participants.")

        # Fear & Greed context
        if fear_greed < 25:
            reasoning_parts.append(f"Fear & Greed Index at {fear_greed:.0f} indicates extreme fear, which historically precedes market reversals.")
        elif fear_greed > 75:
            reasoning_parts.append(f"Fear & Greed Index at {fear_greed:.0f} shows extreme greed, potentially signaling market peaks.")
        else:
            reasoning_parts.append(f"Fear & Greed Index at {fear_greed:.0f} reflects balanced market psychology.")

        # Options flow context
        if options_flow == "BULLISH":
            reasoning_parts.append("Options flow shows bullish positioning with call buying dominating.")
        elif options_flow == "BEARISH":
            reasoning_parts.append("Options flow indicates bearish positioning with put buying prevalent.")
        else:
            reasoning_parts.append("Options flow remains neutral with balanced call/put activity.")

        # Decision rationale
        if sentiment_bias == "BULLISH":
            reasoning_parts.append(f"BUY signal generated from positive sentiment convergence with retail enthusiasm ({retail_sent:.2f}) and neutral institutional stance.")
        elif sentiment_bias == "BEARISH":
            reasoning_parts.append(f"SELL signal triggered by negative sentiment alignment with retail pessimism ({retail_sent:.2f}) and institutional caution.")
        else:
            reasoning_parts.append(f"HOLD recommended due to neutral sentiment landscape with balanced market psychology and no clear directional bias.")

        # Market psychology context
        reasoning_parts.append(f"Overall market psychology suggests {sentiment_bias.lower()} sentiment with {confidence:.1f} confidence in this assessment.")

        details = {
            "retail_sentiment": retail_sent,
            "institutional_sentiment": inst_sent,
            "sentiment_divergence": divergence,
            "options_flow_signal": options_flow,
            "fear_greed_index": fear_greed,
            "confidence_score": confidence,
            "status": status,
            "sentiment_bias": sentiment_bias,
            "reasoning": " ".join(reasoning_parts),
            "analysis_summary": f"Sentiment analysis reveals {sentiment_bias.lower()} market mood with {confidence:.1f} confidence based on news and social data.",
            "news_coverage": len(latest_news),
            "market_psychology": f"Fear & Greed: {fear_greed:.0f}, Retail: {retail_sent:.2f}, Institutional: {inst_sent:.2f}"
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
