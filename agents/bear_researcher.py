"""Bear Researcher Agent."""

import logging
from typing import Dict, Any
from agents.base_agent import BaseAgent
from agents.state import AgentState
from pathlib import Path

logger = logging.getLogger(__name__)


class BearResearcherAgent(BaseAgent):
    """Bear researcher agent for constructing bearish thesis."""
    
    def __init__(self):
        """Initialize bear researcher agent."""
        prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "bear_researcher.txt"
        system_prompt = prompt_path.read_text() if prompt_path.exists() else self._get_default_prompt()
        super().__init__("bear", system_prompt)
    
    def _get_default_prompt(self) -> str:
        """Get default system prompt."""
        return """You are the Bear Researcher Agent for {instrument_name} trading.
Construct the strongest bear case for SELL signals."""
    
    def process(self, state: AgentState) -> AgentState:
        """Process bear research."""
        logger.info("Processing bear research...")
        
        # Default fallback values for graceful degradation
        current_price = state.current_price or 60000
        default_analysis = {
            "bear_thesis": "Analysis unavailable - using default neutral stance",
            "key_drivers": [],
            "downside_target": current_price * 0.97,
            "downside_probability": 0.5,
            "key_risks": [],
            "conviction_score": 0.5,
            "confidence_score": 0.3
        }
        
        try:
            # Gather all agent analyses
            fundamental = state.fundamental_analysis
            technical = state.technical_analysis
            sentiment = state.sentiment_analysis
            macro = state.macro_analysis
            
            current_price = state.current_price
            target = current_price * 0.97 if current_price else 0  # 3% downside target
            stop_loss = current_price * 1.015 if current_price else 0  # 1.5% upside stop
            
            prompt = f"""
Given the analysis from all agents:

Fundamental Analysis:
- Sector Strength: {fundamental.get('sector_strength', 'UNKNOWN')}
- Bearish Probability: {float(fundamental.get('bearish_probability', 0.5)):.2f}
- Key Risks: {', '.join(fundamental.get('key_risk_factors', []))}

Technical Analysis:
- Trend: {technical.get('trend_direction', 'UNKNOWN')} ({float(technical.get('trend_strength', 0)):.0f}% strength)
- RSI Status: {technical.get('rsi_status', 'NEUTRAL')}
- Resistance Level: {technical.get('resistance_level', 'N/A')}

Sentiment Analysis:
- Retail Sentiment: {float(sentiment.get('retail_sentiment', 0.0)):.2f}
- Institutional Sentiment: {float(sentiment.get('institutional_sentiment', 0.0)):.2f}

Macro Analysis:
- Macro Regime: {macro.get('macro_regime', 'UNKNOWN')}
- RBI Cycle: {macro.get('rbi_cycle', 'UNKNOWN')}
- Sector Headwind Score: {float(macro.get('sector_headwind_score', 0.0)):.2f}

Current Price: {current_price}
Downside Target: {target:.2f} (-3%)
Stop Loss: {stop_loss:.2f} (+1.5%)

Build the strongest BEAR CASE for why the price should go DOWN from here.
"""
            
            response_format = {
                "bear_thesis": "string",
                "key_drivers": "array of strings",
                "downside_target": "float",
                "downside_probability": "float (0-1)",
                "key_risks": "array of strings",
                "upside_risk": "float (0-1)",
                "conviction_score": "float (0-1)"
            }
            
            analysis = self._call_llm_structured(prompt, response_format)
            
            # Validate LLM response - ensure thesis is not empty
            bear_thesis = analysis.get("bear_thesis", "").strip()
            if not bear_thesis or bear_thesis.lower() in ["null", "none", "n/a", ""]:
                logger.warning("LLM returned empty bear thesis, using default")
                analysis = default_analysis
                bear_thesis = default_analysis["bear_thesis"]
            
            # Update state
            state.bear_thesis = bear_thesis
            state.bear_confidence = analysis.get("conviction_score", 0.5)
            
            explanation = f"Bear thesis: {analysis.get('conviction_score', 0.5):.2f} conviction, "
            explanation += f"downside prob: {analysis.get('downside_probability', 0.5):.2f}"
            
            self.update_state(state, analysis, explanation)
            
        except Exception as e:
            # Check if it's a rate limit error - if so, log but don't use defaults immediately
            error_str = str(e)
            is_rate_limit = "429" in error_str or "rate limit" in error_str.lower() or "Rate limit" in error_str
            is_timeout = "timeout" in error_str.lower() or "Timeout" in error_str
            
            if is_rate_limit:
                logger.warning(f"Bear research rate limited, will retry with fallback: {e}")
                # Don't use defaults for rate limits - let LLM manager try other providers
                raise
            
            # For timeouts or other errors, use defaults
            logger.warning(f"Bear research failed (using defaults): {e}")
            state.bear_thesis = default_analysis['bear_thesis']  # Ensure thesis is set
            state.bear_confidence = default_analysis['conviction_score']
            explanation = f"Bear thesis: {default_analysis['conviction_score']:.2f} conviction (default - LLM unavailable), "
            explanation += f"downside prob: {default_analysis['downside_probability']:.2f}"
            self.update_state(state, default_analysis, explanation)
        
        return state

