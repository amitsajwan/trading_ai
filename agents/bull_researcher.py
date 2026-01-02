"""Bull Researcher Agent."""

import logging
from typing import Dict, Any
from agents.base_agent import BaseAgent
from agents.state import AgentState
from pathlib import Path

logger = logging.getLogger(__name__)


class BullResearcherAgent(BaseAgent):
    """Bull researcher agent for constructing bullish thesis."""
    
    def __init__(self):
        """Initialize bull researcher agent."""
        prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "bull_researcher.txt"
        system_prompt = prompt_path.read_text() if prompt_path.exists() else self._get_default_prompt()
        super().__init__("bull", system_prompt)
    
    def _get_default_prompt(self) -> str:
        """Get default system prompt."""
        return """You are the Bull Researcher Agent for {instrument_name} trading.
Construct the strongest bull case for BUY signals."""
    
    def process(self, state: AgentState) -> AgentState:
        """Process bull research."""
        logger.info("Processing bull research...")
        
        # Default fallback values for graceful degradation
        current_price = state.current_price or 60000
        default_analysis = {
            "bull_thesis": "Analysis unavailable - using default neutral stance",
            "key_drivers": [],
            "upside_target": current_price * 1.03,
            "upside_probability": 0.5,
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
            target = current_price * 1.03 if current_price else 0  # 3% target
            stop_loss = current_price * 0.985 if current_price else 0  # 1.5% stop loss
            
            prompt = f"""
Given the analysis from all agents:

Fundamental Analysis:
- Sector Strength: {fundamental.get('sector_strength', 'UNKNOWN')}
- Bullish Probability: {float(fundamental.get('bullish_probability', 0.5)):.2f}
- Key Catalysts: {', '.join(fundamental.get('key_catalysts', []))}

Technical Analysis:
- Trend: {technical.get('trend_direction', 'UNKNOWN')} ({float(technical.get('trend_strength', 0)):.0f}% strength)
- RSI Status: {technical.get('rsi_status', 'NEUTRAL')}
- Support Level: {technical.get('support_level', 'N/A')}

Sentiment Analysis:
- Retail Sentiment: {float(sentiment.get('retail_sentiment', 0.0)):.2f}
- Institutional Sentiment: {float(sentiment.get('institutional_sentiment', 0.0)):.2f}

Macro Analysis:
- Macro Regime: {macro.get('macro_regime', 'UNKNOWN')}
- RBI Cycle: {macro.get('rbi_cycle', 'UNKNOWN')}
- Sector Headwind Score: {float(macro.get('sector_headwind_score', 0.0)):.2f}

Current Price: {current_price}
Upside Target: {target:.2f} (+3%)
Stop Loss: {stop_loss:.2f} (-1.5%)

Build the strongest BULL CASE for why the price should go UP from here.
"""
            
            response_format = {
                "bull_thesis": "string",
                "key_drivers": "array of strings",
                "upside_target": "float",
                "upside_probability": "float (0-1)",
                "key_risks": "array of strings",
                "downside_risk": "float (0-1)",
                "conviction_score": "float (0-1)"
            }
            
            analysis = self._call_llm_structured(prompt, response_format)
            
            # Update state
            state.bull_thesis = analysis.get("bull_thesis", "")
            state.bull_confidence = analysis.get("conviction_score", 0.5)
            
            explanation = f"Bull thesis: {analysis.get('conviction_score', 0.5):.2f} conviction, "
            explanation += f"upside prob: {analysis.get('upside_probability', 0.5):.2f}"
            
            self.update_state(state, analysis, explanation)
            
        except Exception as e:
            # Check if it's a rate limit error - if so, log but don't use defaults immediately
            error_str = str(e)
            is_rate_limit = "429" in error_str or "rate limit" in error_str.lower() or "Rate limit" in error_str
            
            if is_rate_limit:
                logger.warning(f"Bull research rate limited, will retry with fallback: {e}")
                # Don't use defaults for rate limits - let LLM manager try other providers
                raise
            
            # Only use defaults for actual errors (not rate limits)
            logger.warning(f"Bull research failed (using defaults): {e}")
            state.bull_confidence = default_analysis['conviction_score']
            explanation = f"Bull thesis: {default_analysis['conviction_score']:.2f} conviction (default - LLM unavailable), "
            explanation += f"upside prob: {default_analysis['upside_probability']:.2f}"
            self.update_state(state, default_analysis, explanation)
        
        return state

