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
        
        # Get instrument info from settings
        from config.settings import settings
        instrument_name = settings.instrument_name
        is_crypto = settings.data_source.upper() == "CRYPTO" or "BTC" in instrument_name.upper() or "Bitcoin" in instrument_name
        
        # Default fallback values - instrument-aware
        if is_crypto:
            default_analysis = {
                "sector_strength": "MODERATE",
                "credit_quality_trend": "STABLE",  # Not applicable for crypto, but kept for compatibility
                "rbi_policy_impact": "NEUTRAL",  # Will be replaced with regulatory_impact for crypto
                "regulatory_impact": "NEUTRAL",  # Crypto-specific
                "adoption_trend": "STABLE",  # Crypto-specific
                "bullish_probability": 0.5,
                "bearish_probability": 0.5,
                "key_risk_factors": [],
                "key_catalysts": [],
                "confidence_score": 0.5
            }
        else:
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
            
            # Prepare prompt - instrument-aware
            news_summary = "\n".join([
                f"- {item.get('title', 'No title')} (sentiment: {float(item.get('sentiment_score', 0.0)):.2f})"
                for item in latest_news
            ]) if latest_news else "No recent news available"
            
            if is_crypto:
                # Crypto-specific context
                prompt = f"""
Latest News for {instrument_name}:
{news_summary}

Market Context for {instrument_name} (Cryptocurrency):
- Regulatory Environment: Analyze recent regulatory news and policy changes
- Adoption Trends: Institutional adoption, ETF flows, mainstream acceptance
- Network Metrics: Hash rate, transaction volume, active addresses (if available)
- Market Structure: Exchange flows, whale movements, market sentiment

Analyze the fundamental strength of {instrument_name} as a cryptocurrency asset.
Focus on:
- Regulatory clarity and policy support
- Adoption and mainstream integration
- Network health and security
- Market structure and liquidity
"""
                response_format = {
                    "sector_strength": "string (STRONG/MODERATE/WEAK) - overall crypto market strength",
                    "credit_quality_trend": "string (IMPROVING/STABLE/DETERIORATING) - network security trend",
                    "rbi_policy_impact": "string (POSITIVE/NEUTRAL/NEGATIVE) - kept for compatibility",
                    "regulatory_impact": "string (POSITIVE/NEUTRAL/NEGATIVE) - regulatory environment impact",
                    "adoption_trend": "string (ACCELERATING/STABLE/DECLINING) - adoption trend",
                    "bullish_probability": "float (0-1)",
                    "bearish_probability": "float (0-1)",
                    "key_risk_factors": "array of strings - crypto-specific risks",
                    "key_catalysts": "array of strings - crypto-specific catalysts",
                    "confidence_score": "float (0-1)"
                }
            else:
                # Indian stocks/banking sector context
                rbi_rate = state.rbi_rate
                npa_ratio = state.npa_ratio
                
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
            
            # Build human-readable explanation with points and reasoning
            if is_crypto:
                key_catalysts = analysis.get('key_catalysts', [])[:3]  # Top 3
                key_risks = analysis.get('key_risk_factors', [])[:3]  # Top 3
                confidence = analysis.get('confidence_score', 0.5)
                
                points = [
                    ("Market Strength", analysis.get('asset_strength', 'UNKNOWN'), 
                     f"Based on adoption trends and network health"),
                    ("Regulatory Impact", analysis.get('regulatory_impact', 'NEUTRAL'),
                     f"Current regulatory environment assessment"),
                    ("Adoption Trend", analysis.get('adoption_trend', 'UNKNOWN'),
                     f"Institutional and retail adoption momentum"),
                    ("Bullish Probability", f"{bullish_prob:.0%}",
                     f"Based on {', '.join(key_catalysts[:2]) if key_catalysts else 'market factors'}"),
                    ("Bearish Probability", f"{bearish_prob:.0%}",
                     f"Due to {', '.join(key_risks[:2]) if key_risks else 'market risks'}"),
                    ("Confidence", f"{confidence:.0%}",
                     f"Analysis confidence based on data quality")
                ]
                
                summary = f"Overall: {analysis.get('asset_strength', 'UNKNOWN')} crypto market strength with {analysis.get('regulatory_impact', 'NEUTRAL')} regulatory environment"
            else:
                key_catalysts = analysis.get('key_catalysts', [])[:3]
                key_risks = analysis.get('key_risk_factors', [])[:3]
                confidence = analysis.get('confidence_score', 0.5)
                
                points = [
                    ("Sector Strength", analysis.get('sector_strength', 'UNKNOWN'),
                     f"Overall sector health assessment"),
                    ("Credit Quality Trend", analysis.get('credit_quality_trend', 'UNKNOWN'),
                     f"Credit quality direction"),
                    ("RBI Policy Impact", analysis.get('rbi_policy_impact', 'NEUTRAL'),
                     f"Impact of current RBI policy"),
                    ("Bullish Probability", f"{bullish_prob:.0%}",
                     f"Based on {', '.join(key_catalysts[:2]) if key_catalysts else 'sector factors'}"),
                    ("Bearish Probability", f"{bearish_prob:.0%}",
                     f"Due to {', '.join(key_risks[:2]) if key_risks else 'sector risks'}"),
                    ("Confidence", f"{confidence:.0%}",
                     f"Analysis confidence based on data quality")
                ]
                
                summary = f"Overall: {analysis.get('sector_strength', 'UNKNOWN')} sector strength"
            
            explanation = self.format_explanation("Fundamental Analysis", points, summary)
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

