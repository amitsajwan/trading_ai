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
- Retail Sentiment: {float(sentiment.get('retail_sentiment') or 0.0):.2f}
- Institutional Sentiment: {float(sentiment.get('institutional_sentiment') or 0.0):.2f}

Macro Analysis:
- Macro Regime: {macro.get('macro_regime', 'UNKNOWN')}
- RBI Cycle: {macro.get('rbi_cycle', 'UNKNOWN')}
- Sector Headwind Score: {float(macro.get('sector_headwind_score') or 0.0):.2f}

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
            bear_thesis = str(analysis.get("bear_thesis", "") or "").strip()
            if not bear_thesis or bear_thesis.lower() in ["null", "none", "n/a", ""]:
                logger.warning("LLM returned empty bear thesis, using default")
                analysis = default_analysis
                bear_thesis = default_analysis["bear_thesis"]
            
            # Ensure thesis is not empty (fallback to default if still empty)
            if not bear_thesis or len(bear_thesis) < 10:
                logger.warning("Bear thesis is too short or empty, using default")
                bear_thesis = default_analysis["bear_thesis"]
                analysis = default_analysis
            
            # Update state
            state.bear_thesis = bear_thesis
            state.bear_confidence = analysis.get("conviction_score", 0.5)
            
            # Build human-readable explanation with points and reasoning
            conviction = analysis.get('conviction_score', 0.5)
            downside_prob = analysis.get('downside_probability', 0.5)
            downside_target = analysis.get('downside_target', current_price * 0.97)
            key_drivers = analysis.get('key_drivers', [])[:3]  # Top 3
            key_risks = analysis.get('key_risks', [])[:2]  # Top 2

            # Avoid division by zero when price is unavailable
            safe_price = current_price if current_price and current_price > 0 else None
            downside_pct = ((downside_target / safe_price - 1) * 100) if safe_price else None
            downside_pct_str = f"{downside_pct:.1f}%" if downside_pct is not None else "n/a"
            
            points = [
                ("Conviction Score", f"{conviction:.0%}",
                 f"{'High' if conviction > 0.7 else 'Moderate' if conviction > 0.5 else 'Low'} conviction in bearish thesis"),
                ("Downside Probability", f"{downside_prob:.0%}",
                 f"Probability of price moving lower"),
                ("Downside Target", f"{downside_target:.2f}",
                 f"Target price level ({downside_pct_str})"),
                ("Key Drivers", ", ".join(key_drivers) if key_drivers else "Market factors",
                 f"Main factors supporting bearish case"),
                ("Key Risks", ", ".join(key_risks) if key_risks else "Market risks",
                 f"Main risks to bearish thesis")
            ]
            
            summary = f"Bear Case: {conviction:.0%} conviction with {downside_prob:.0%} downside probability"
            
            explanation = self.format_explanation("Bear Thesis", points, summary)
            self.update_state(state, analysis, explanation)
            
        except Exception as e:
            error_str = str(e)
            
            # Check if all providers failed - if so, retry with exponential backoff
            if "All LLM providers failed" in error_str or "No available LLM providers" in error_str:
                logger.error(f"❌ Bear research: All LLM providers failed. Retrying with exponential backoff...")
                
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
                        bear_thesis = analysis.get("bear_thesis", "").strip()
                        if bear_thesis and bear_thesis.lower() not in ["null", "none", "n/a", ""]:
                            # Success - use the analysis
                            state.bear_thesis = bear_thesis
                            state.bear_confidence = analysis.get("conviction_score", 0.5)
                            explanation = f"Bear thesis: {analysis.get('conviction_score', 0.5):.2f} conviction, "
                            explanation += f"downside prob: {analysis.get('downside_probability', 0.5):.2f}"
                            self.update_state(state, analysis, explanation)
                            logger.info(f"✅ Bear research succeeded on retry {retry_attempt + 1}")
                            return state
                    except Exception as retry_error:
                        logger.warning(f"⚠️ Retry {retry_attempt + 1} failed: {retry_error}")
                        if retry_attempt == max_retries - 1:
                            # All retries exhausted - raise the error
                            logger.error(f"❌ Bear research failed after {max_retries} retries. All providers unavailable.")
                            raise RuntimeError(f"Bear research failed after {max_retries} retries with all providers. Last error: {retry_error}")
                        continue
                
                # Should not reach here, but if we do, raise
                raise RuntimeError(f"Bear research failed after {max_retries} retries")
            
            # For other errors (timeout, etc.), let LLM manager handle retries
            # Don't use defaults - re-raise to let the system handle it properly
            logger.error(f"❌ Bear research failed: {e}")
            raise
        
        return state

