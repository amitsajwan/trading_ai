"""Fundamental Analysis Agent."""

import logging
from typing import Dict, Any
from agents.base_agent import BaseAgent
from agents.state import AgentState
from pathlib import Path

logger = logging.getLogger(__name__)


class FundamentalAnalysisAgent(BaseAgent):
    """Fundamental analysis agent for bank sector analysis."""
    
    def __init__(self):
        """Initialize fundamental analysis agent."""
        prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "fundamental_analysis.txt"
        system_prompt = prompt_path.read_text() if prompt_path.exists() else self._get_default_prompt()
        super().__init__("fundamental", system_prompt)
    
    def _get_default_prompt(self) -> str:
        """Get default system prompt."""
        return """You are the Fundamental Analysis Agent for a {instrument_name} trading system.
Analyze fundamental factors affecting {instrument_name} performance."""
    
    def process(self, state: AgentState) -> AgentState:
        """Process fundamental analysis."""
        logger.info("Processing fundamental analysis...")
        
        # Default fallback values for graceful degradation
        default_analysis = {
            "sector_strength": "MODERATE",
            "credit_quality_trend": "STABLE",
            "rbi_policy_impact": "NEUTRAL",
            "bullish_probability": 0.5,
            "bearish_probability": 0.5,
            "key_risk_factors": [],
            "key_catalysts": [],
            "confidence_score": 0.5
        }
        
        try:
            # Gather context
            latest_news = state.latest_news[:10] if state.latest_news else []
            rbi_rate = state.rbi_rate
            npa_ratio = state.npa_ratio
            
            # Prepare prompt
            news_summary = "\n".join([
                f"- {item.get('title', 'No title')} (sentiment: {float(item.get('sentiment_score', 0.0)):.2f})"
                for item in latest_news
            ]) if latest_news else "No recent news available"
            
            # Get instrument name from settings
            from config.settings import settings
            instrument_name = settings.instrument_name
            
            prompt = f"""
Latest News for {instrument_name}:
{news_summary}

Market Context:
- Policy Rate: {rbi_rate if rbi_rate else 'Unknown'}
- Market Health Indicator: {npa_ratio if npa_ratio else 'Unknown'}

Analyze the fundamental strength of {instrument_name} and provide your assessment.
Focus on factors that directly impact {instrument_name} performance.
"""
            
            response_format = {
                "sector_strength": "string (STRONG/MODERATE/WEAK)",
                "credit_quality_trend": "string (IMPROVING/STABLE/DETERIORATING)",
                "rbi_policy_impact": "string (POSITIVE/NEUTRAL/NEGATIVE)",
                "bullish_probability": "float (0-1)",
                "bearish_probability": "float (0-1)",
                "key_risk_factors": "array of strings",
                "key_catalysts": "array of strings",
                "confidence_score": "float (0-1)"
            }
            
            analysis = self._call_llm_structured(prompt, response_format)
            
            # Ensure probabilities are floats before formatting
            bullish_prob = analysis.get('bullish_probability', 0.5)
            bearish_prob = analysis.get('bearish_probability', 0.5)
            try:
                bullish_prob = float(bullish_prob) if bullish_prob is not None else 0.5
            except (ValueError, TypeError):
                bullish_prob = 0.5
            try:
                bearish_prob = float(bearish_prob) if bearish_prob is not None else 0.5
            except (ValueError, TypeError):
                bearish_prob = 0.5
            
            explanation = f"Fundamental analysis: {analysis.get('sector_strength', 'UNKNOWN')} sector, "
            explanation += f"bullish prob: {bullish_prob:.2f}, "
            explanation += f"bearish prob: {bearish_prob:.2f}"
            
            self.update_state(state, analysis, explanation)
        
        except Exception as e:
            # Check if it's a rate limit error - if so, log but don't use defaults immediately
            error_str = str(e)
            is_rate_limit = "429" in error_str or "rate limit" in error_str.lower() or "Rate limit" in error_str
            
            if is_rate_limit:
                logger.warning(f"⚠️ [fundamental] Rate limited, will retry with fallback: {e}")
                # Don't use defaults for rate limits - let LLM manager try other providers
                # Re-raise to let LLM manager handle fallback
                raise
            
            # Only use defaults for actual errors (not rate limits)
            logger.error(f"❌ [fundamental] LLM call failed (using defaults): {e}")
            explanation = f"Fundamental analysis: {default_analysis['sector_strength']} sector (default - LLM unavailable), "
            explanation += f"bullish prob: {default_analysis['bullish_probability']:.2f}, "
            explanation += f"bearish prob: {default_analysis['bearish_probability']:.2f}"
            self.update_state(state, default_analysis, explanation)
        
        return state

