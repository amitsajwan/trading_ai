"""Sentiment Analysis Agent."""

import logging
from typing import Dict, Any
from agents.base_agent import BaseAgent
from agents.state import AgentState
from pathlib import Path

logger = logging.getLogger(__name__)


class SentimentAnalysisAgent(BaseAgent):
    """Sentiment analysis agent for market sentiment extraction."""
    
    def __init__(self):
        """Initialize sentiment analysis agent."""
        prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "sentiment_analysis.txt"
        system_prompt = prompt_path.read_text() if prompt_path.exists() else self._get_default_prompt()
        super().__init__("sentiment", system_prompt)
    
    def _get_default_prompt(self) -> str:
        """Get default system prompt."""
        return """You are the Sentiment Analysis Agent for a {instrument_name} trading system.
Analyze market sentiment from news, social media, and market flow data."""
    
    def process(self, state: AgentState) -> AgentState:
        """Process sentiment analysis."""
        logger.info("Processing sentiment analysis...")
        
        # Default fallback values for graceful degradation
        default_analysis = {
            "retail_sentiment": 0.0,
            "institutional_sentiment": 0.0,
            "sentiment_divergence": "NONE",
            "options_flow_signal": "NEUTRAL",
            "fear_greed_index": 50.0,
            "confidence_score": 0.5
        }
        
        try:
            # Gather context
            latest_news = state.latest_news[:20] if state.latest_news else []
            aggregate_sentiment = state.sentiment_score
            
            # Prepare prompt
            news_headlines = "\n".join([
                f"- {item.get('title', 'No title')}"
                for item in latest_news
            ]) if latest_news else "No recent news available"
            
            prompt = f"""
Latest News Headlines:
{news_headlines}

Aggregate Sentiment Score: {aggregate_sentiment:.2f} (range: -1 to +1)

Analyze the market sentiment and provide your assessment.
"""
            
            response_format = {
                "retail_sentiment": "float (-1 to +1)",
                "institutional_sentiment": "float (-1 to +1)",
                "sentiment_divergence": "string (NONE/RETAIL_BULLISH/INSTITUTIONAL_BULLISH/EXTREME_FEAR/EXTREME_GREED)",
                "options_flow_signal": "string (BULLISH/BEARISH/NEUTRAL)",
                "fear_greed_index": "float (0-100)",
                "confidence_score": "float (0-1)"
            }
            
            analysis = self._call_llm_structured(prompt, response_format)
            
            # Ensure all values are proper types (handle string returns from LLM)
            retail_sent = float(analysis.get('retail_sentiment', 0.0) or 0.0)
            inst_sent = float(analysis.get('institutional_sentiment', 0.0) or 0.0)
            divergence = str(analysis.get('sentiment_divergence', 'NONE') or 'NONE')
            options_flow = str(analysis.get('options_flow_signal', 'NEUTRAL') or 'NEUTRAL')
            fear_greed = float(analysis.get('fear_greed_index', 50) or 50)
            confidence = float(analysis.get('confidence_score', 0.3) or 0.3)
            
            # Build human-readable explanation with points and reasoning
            retail_desc = "bullish" if retail_sent > 0.2 else "bearish" if retail_sent < -0.2 else "neutral"
            inst_desc = "bullish" if inst_sent > 0.2 else "bearish" if inst_sent < -0.2 else "neutral"
            fear_greed_desc = "extreme greed" if fear_greed > 75 else "greed" if fear_greed > 55 else "neutral" if fear_greed > 45 else "fear" if fear_greed > 25 else "extreme fear"
            
            points = [
                ("Retail Sentiment", f"{retail_sent:.2f} ({retail_desc})",
                 f"Retail investor sentiment based on news and social media"),
                ("Institutional Sentiment", f"{inst_sent:.2f} ({inst_desc})",
                 f"Institutional investor sentiment based on positioning"),
                ("Sentiment Divergence", divergence,
                 f"{'No divergence' if divergence == 'NONE' else 'Divergence detected'} between retail and institutional"),
                ("Options Flow", options_flow,
                 f"Options market sentiment signal"),
                ("Fear & Greed Index", f"{fear_greed:.0f} ({fear_greed_desc})",
                 f"Market sentiment indicator (0=extreme fear, 100=extreme greed)"),
                ("Confidence", f"{confidence:.0%}",
                 f"Analysis confidence based on data availability")
            ]
            
            summary = f"Overall: {retail_desc} retail sentiment, {inst_desc} institutional sentiment"
            
            explanation = self.format_explanation("Sentiment Analysis", points, summary)
            self.update_state(state, analysis, explanation)
        
        except Exception as e:
            # Check if it's a rate limit error - if so, log but don't use defaults immediately
            error_str = str(e)
            is_rate_limit = "429" in error_str or "rate limit" in error_str.lower() or "Rate limit" in error_str
            
            if is_rate_limit:
                logger.warning(f"Sentiment analysis rate limited, will retry with fallback: {e}")
                # Don't use defaults for rate limits - let LLM manager try other providers
                raise
            
            # Only use defaults for actual errors (not rate limits)
            logger.warning(f"Sentiment analysis failed (using defaults): {e}")
            explanation = f"Sentiment analysis: retail {default_analysis['retail_sentiment']:.2f}, "
            explanation += f"institutional {default_analysis['institutional_sentiment']:.2f}, "
            explanation += f"divergence: {default_analysis['sentiment_divergence']} (default - LLM unavailable)"
            self.update_state(state, default_analysis, explanation)
        
        return state

