"""Macro Analysis Agent."""

import logging
from typing import Dict, Any
from agents.base_agent import BaseAgent
from agents.state import AgentState
from pathlib import Path

logger = logging.getLogger(__name__)


class MacroAnalysisAgent(BaseAgent):
    """Macro analysis agent for macro regime detection."""
    
    def __init__(self):
        """Initialize macro analysis agent."""
        prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "macro_analysis.txt"
        system_prompt = prompt_path.read_text() if prompt_path.exists() else self._get_default_prompt()
        super().__init__("macro", system_prompt)
    
    def _get_default_prompt(self) -> str:
        """Get default system prompt."""
        return """You are the Macro Analysis Agent for a {instrument_name} trading system.
Analyze macro economic conditions and market regime."""
    
    def process(self, state: AgentState) -> AgentState:
        """Process macro analysis."""
        logger.info("Processing macro analysis...")
        
        # Default fallback values for graceful degradation
        default_analysis = {
            "macro_regime": "MIXED",
            "rbi_cycle": "NEUTRAL",
            "rate_cut_probability": 0.5,
            "rate_hike_probability": 0.5,
            "npa_concern_level": "MEDIUM",
            "liquidity_condition": "NORMAL",
            "sector_headwind_score": 0.0,
            "confidence_score": 0.5
        }
        
        try:
            # Gather context
            rbi_rate = state.rbi_rate
            inflation_rate = state.inflation_rate
            npa_ratio = state.npa_ratio
            
            # Get instrument name from settings
            from config.settings import settings
            instrument_name = settings.instrument_name
            
            prompt = f"""
Macro Economic Context:
- Interest Rate: {rbi_rate if rbi_rate else 'Unknown'}
- Inflation Rate: {inflation_rate if inflation_rate else 'Unknown'}
- Market Health Indicator: {npa_ratio if npa_ratio else 'Unknown'}

Analyze the macro regime and its impact on {instrument_name}.
"""
            
            response_format = {
                "macro_regime": "string (GROWTH/INFLATION/STRESS/MIXED)",
                "rbi_cycle": "string (TIGHTENING/EASING/NEUTRAL)",
                "rate_cut_probability": "float (0-1)",
                "rate_hike_probability": "float (0-1)",
                "npa_concern_level": "string (LOW/MEDIUM/HIGH)",
                "liquidity_condition": "string (EASY/NORMAL/TIGHT)",
                "sector_headwind_score": "float (-1 to +1)",
                "confidence_score": "float (0-1)"
            }
            
            analysis = self._call_llm_structured(prompt, response_format)
            
            headwind_score = analysis.get('sector_headwind_score', 0.0)
            # Ensure it's a float before formatting
            try:
                headwind_score = float(headwind_score) if headwind_score is not None else 0.0
            except (ValueError, TypeError):
                headwind_score = 0.0
            
            explanation = f"Macro analysis: {analysis.get('macro_regime', 'UNKNOWN')} regime, "
            explanation += f"RBI cycle: {analysis.get('rbi_cycle', 'UNKNOWN')}, "
            explanation += f"headwind score: {headwind_score:.2f}"
            
            self.update_state(state, analysis, explanation)
        
        except Exception as e:
            # Check if it's a rate limit error - if so, log but don't use defaults immediately
            error_str = str(e)
            is_rate_limit = "429" in error_str or "rate limit" in error_str.lower() or "Rate limit" in error_str
            
            if is_rate_limit:
                logger.warning(f"Macro analysis rate limited, will retry with fallback: {e}")
                # Don't use defaults for rate limits - let LLM manager try other providers
                raise
            
            # Only use defaults for actual errors (not rate limits)
            logger.warning(f"Macro analysis failed (using defaults): {e}")
            explanation = f"Macro analysis: {default_analysis['macro_regime']} regime (default - LLM unavailable), "
            explanation += f"RBI cycle: {default_analysis['rbi_cycle']}, "
            explanation += f"headwind score: {default_analysis['sector_headwind_score']:.2f}"
            self.update_state(state, default_analysis, explanation)
            
        except Exception as e:
            logger.error(f"Error in macro analysis: {e}")
            output = {
                "error": str(e),
                "macro_regime": "MIXED",
                "sector_headwind_score": 0.0,
                "confidence_score": 0.0
            }
            self.update_state(state, output, f"Error: {e}")
        
        return state

