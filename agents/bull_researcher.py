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
- Bullish Probability: {float(fundamental.get('bullish_probability') or 0.5):.2f}
- Key Catalysts: {', '.join(fundamental.get('key_catalysts', []))}

Technical Analysis:
- Trend: {technical.get('trend_direction', 'UNKNOWN')} ({float(technical.get('trend_strength') or 0):.0f}% strength)
- RSI Status: {technical.get('rsi_status', 'NEUTRAL')}
- Support Level: {technical.get('support_level', 'N/A')}

Sentiment Analysis:
- Retail Sentiment: { ('N/A' if sentiment.get('confidence_score', 1.0) < 0.2 else f"{float(sentiment.get('retail_sentiment') or 0.0):.2f}") }
- Institutional Sentiment: { ('N/A' if sentiment.get('confidence_score', 1.0) < 0.2 else f"{float(sentiment.get('institutional_sentiment') or 0.0):.2f}") }

Macro Analysis:
- Macro Regime: {macro.get('macro_regime', 'UNKNOWN')}
- RBI Cycle: {macro.get('rbi_cycle', 'UNKNOWN')}
- Sector Headwind Score: {float(macro.get('sector_headwind_score') or 0.0):.2f}

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
            
            # Validate LLM response - ensure thesis is not empty
            bull_thesis = str(analysis.get("bull_thesis", "") or "").strip()
            if not bull_thesis or bull_thesis.lower() in ["null", "none", "n/a", ""]:
                logger.warning("LLM returned empty bull thesis, using default")
                analysis = default_analysis
                bull_thesis = default_analysis["bull_thesis"]
            
            # Ensure thesis is not empty (fallback to default if still empty)
            if not bull_thesis or len(bull_thesis) < 10:
                logger.warning("Bull thesis is too short or empty, using default")
                bull_thesis = default_analysis["bull_thesis"]
                analysis = default_analysis
            
            # Update state
            state.bull_thesis = bull_thesis
            state.bull_confidence = analysis.get("conviction_score", 0.5)
            
            # Build human-readable explanation with points and reasoning
            conviction = analysis.get('conviction_score', 0.5)
            upside_prob = analysis.get('upside_probability', 0.5)
            upside_target = analysis.get('upside_target', current_price * 1.03)
            key_drivers = analysis.get('key_drivers', [])[:3]  # Top 3
            key_risks = analysis.get('key_risks', [])[:2]  # Top 2

            # Avoid division by zero when price is unavailable
            safe_price = current_price if current_price and current_price > 0 else None
            upside_pct = ((upside_target / safe_price - 1) * 100) if safe_price else None
            upside_pct_str = f"+{upside_pct:.1f}%" if upside_pct is not None else "n/a"
            
            points = [
                ("Conviction Score", f"{conviction:.0%}",
                 f"{'High' if conviction > 0.7 else 'Moderate' if conviction > 0.5 else 'Low'} conviction in bullish thesis"),
                ("Upside Probability", f"{upside_prob:.0%}",
                 f"Probability of price moving higher"),
                ("Upside Target", f"{upside_target:.2f}",
                 f"Target price level ({upside_pct_str})"),
                ("Key Drivers", ", ".join(key_drivers) if key_drivers else "Market factors",
                 f"Main factors supporting bullish case"),
                ("Key Risks", ", ".join(key_risks) if key_risks else "Market risks",
                 f"Main risks to bullish thesis")
            ]
            
            summary = f"Bull Case: {conviction:.0%} conviction with {upside_prob:.0%} upside probability"
            
            explanation = self.format_explanation("Bull Thesis", points, summary)
            self.update_state(state, analysis, explanation)
            
        except Exception as e:
            error_str = str(e)
            
            # Check if all providers failed - if so, retry with exponential backoff
            if "All LLM providers failed" in error_str or "No available LLM providers" in error_str:
                logger.error(f"❌ Bull research: All LLM providers failed. Retrying with exponential backoff...")
                
                # Retry with exponential backoff (up to 3 retries)
                import time
                max_retries = 3
                for retry_attempt in range(max_retries):
                    wait_time = 2 ** retry_attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.info(f"⏳ Retry {retry_attempt + 1}/{max_retries} after {wait_time}s...")
                    time.sleep(wait_time)
                    
                    try:
                        # Try again - LLM manager will try all providers
                        analysis = self._call_llm_structured(prompt, response_format)
                        
                        # Validate LLM response
                        bull_thesis = analysis.get("bull_thesis", "").strip()
                        if bull_thesis and bull_thesis.lower() not in ["null", "none", "n/a", ""]:
                            # Success - use the analysis
                            state.bull_thesis = bull_thesis
                            state.bull_confidence = analysis.get("conviction_score", 0.5)
                            explanation = f"Bull thesis: {analysis.get('conviction_score', 0.5):.2f} conviction, "
                            explanation += f"upside prob: {analysis.get('upside_probability', 0.5):.2f}"
                            self.update_state(state, analysis, explanation)
                            logger.info(f"✅ Bull research succeeded on retry {retry_attempt + 1}")
                            return state
                    except Exception as retry_error:
                        logger.warning(f"⚠️ Retry {retry_attempt + 1} failed: {retry_error}")
                        if retry_attempt == max_retries - 1:
                            # All retries exhausted - raise the error
                            logger.error(f"❌ Bull research failed after {max_retries} retries. All providers unavailable.")
                            raise RuntimeError(f"Bull research failed after {max_retries} retries with all providers. Last error: {retry_error}")
                        continue
                
                # Should not reach here, but if we do, raise
                raise RuntimeError(f"Bull research failed after {max_retries} retries")
            
            # For other errors (timeout, etc.), let LLM manager handle retries
            # Don't use defaults - re-raise to let the system handle it properly
            logger.error(f"❌ Bull research failed: {e}")
            raise
        
        return state

