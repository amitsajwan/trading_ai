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
        
        # Get instrument info from settings
        from config.settings import settings
        instrument_name = settings.instrument_name
        is_crypto = settings.data_source.upper() == "CRYPTO" or "BTC" in instrument_name.upper() or "Bitcoin" in instrument_name
        
        # Default fallback values - instrument-aware
        if is_crypto:
            default_analysis = {
                "macro_regime": "MIXED",
                "rbi_cycle": "NEUTRAL",  # Will be replaced with fed_cycle for crypto
                "fed_cycle": "NEUTRAL",  # Crypto-specific
                "rate_cut_probability": 0.5,
                "rate_hike_probability": 0.5,
                "npa_concern_level": "MEDIUM",  # Not applicable for crypto
                "liquidity_condition": "NORMAL",
                "dollar_strength": "NEUTRAL",  # Crypto-specific
                "sector_headwind_score": 0.0,
                "confidence_score": 0.5
            }
        else:
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
            
            if is_crypto:
                # Crypto-specific macro context
                prompt = f"""
Macro Economic Context for {instrument_name} (Cryptocurrency):
- Global Interest Rates: {rbi_rate if rbi_rate else 'Unknown'} (use as proxy for global rates)
- Inflation Rate: {inflation_rate if inflation_rate else 'Unknown'}
- Dollar Strength (DXY): Analyze impact of USD strength on crypto
- Risk-On/Risk-Off Sentiment: Market risk appetite
- Liquidity Conditions: Global liquidity and funding conditions

Analyze the macro regime and its impact on {instrument_name} as a cryptocurrency.
Focus on:
- Fed policy cycle and global monetary policy
- Dollar strength correlation (inverse relationship)
- Risk-on/risk-off regime shifts
- Global liquidity conditions
- Inflation hedge narrative
"""
                response_format = {
                    "macro_regime": "string (RISK_ON/RISK_OFF/MIXED)",
                    "fed_cycle": "string (TIGHTENING/EASING/NEUTRAL) - Fed policy cycle (REQUIRED for crypto, NOT RBI)",
                    "rate_cut_probability": "float (0-1) - probability of Fed rate cuts",
                    "rate_hike_probability": "float (0-1) - probability of Fed rate hikes",
                    "liquidity_condition": "string (EASY/NORMAL/TIGHT) - global liquidity",
                    "dollar_strength": "string (STRONG/NEUTRAL/WEAK) - USD strength impact",
                    "sector_headwind_score": "float (-1 to +1) - negative = headwind, positive = tailwind",
                    "confidence_score": "float (0-1)",
                    "macro_regime_reasoning": "string explaining regime choice",
                    "fed_cycle_reasoning": "string explaining Fed cycle assessment"
                }
            else:
                # Indian stocks/banking sector context
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
            
            # Build human-readable explanation with points and reasoning
            if is_crypto:
                fed_cycle = analysis.get('fed_cycle')
                if not fed_cycle:
                    fed_cycle = analysis.get('rbi_cycle', 'UNKNOWN')
                    logger.warning("LLM returned rbi_cycle for crypto, should return fed_cycle")
                
                rate_cut_prob = analysis.get('rate_cut_probability', 0.5)
                rate_hike_prob = analysis.get('rate_hike_probability', 0.5)
                dollar_strength = analysis.get('dollar_strength', 'NEUTRAL')
                liquidity = analysis.get('liquidity_condition', 'NORMAL')
                confidence = analysis.get('confidence_score', 0.5)
                
                points = [
                    ("Macro Regime", analysis.get('macro_regime', 'UNKNOWN'),
                     f"Current market regime assessment"),
                    ("Fed Policy Cycle", fed_cycle,
                     f"Federal Reserve monetary policy stance"),
                    ("Rate Cut Probability", f"{rate_cut_prob:.0%}",
                     f"Likelihood of rate cuts in next 1-3 months"),
                    ("Rate Hike Probability", f"{rate_hike_prob:.0%}",
                     f"Likelihood of rate hikes in next 1-3 months"),
                    ("Dollar Strength", dollar_strength,
                     f"USD strength impact on crypto (inverse correlation)"),
                    ("Liquidity Condition", liquidity,
                     f"Global liquidity and funding conditions"),
                    ("Headwind Score", f"{headwind_score:.2f}",
                     f"{'Headwind' if headwind_score < 0 else 'Tailwind'} for crypto sector"),
                    ("Confidence", f"{confidence:.0%}",
                     f"Analysis confidence based on data quality")
                ]
                
                summary = f"Overall: {analysis.get('macro_regime', 'UNKNOWN')} regime with {fed_cycle} Fed cycle"
            else:
                rate_cut_prob = analysis.get('rate_cut_probability', 0.5)
                rate_hike_prob = analysis.get('rate_hike_probability', 0.5)
                npa_level = analysis.get('npa_concern_level', 'MEDIUM')
                liquidity = analysis.get('liquidity_condition', 'NORMAL')
                confidence = analysis.get('confidence_score', 0.5)
                
                points = [
                    ("Macro Regime", analysis.get('macro_regime', 'UNKNOWN'),
                     f"Current economic regime assessment"),
                    ("RBI Policy Cycle", analysis.get('rbi_cycle', 'UNKNOWN'),
                     f"RBI monetary policy stance"),
                    ("Rate Cut Probability", f"{rate_cut_prob:.0%}",
                     f"Likelihood of rate cuts in next 1-3 months"),
                    ("Rate Hike Probability", f"{rate_hike_prob:.0%}",
                     f"Likelihood of rate hikes in next 1-3 months"),
                    ("NPA Concern Level", npa_level,
                     f"Banking sector asset quality concerns"),
                    ("Liquidity Condition", liquidity,
                     f"Market liquidity and funding conditions"),
                    ("Headwind Score", f"{headwind_score:.2f}",
                     f"{'Headwind' if headwind_score < 0 else 'Tailwind'} for sector"),
                    ("Confidence", f"{confidence:.0%}",
                     f"Analysis confidence based on data quality")
                ]
                
                summary = f"Overall: {analysis.get('macro_regime', 'UNKNOWN')} regime with {analysis.get('rbi_cycle', 'UNKNOWN')} RBI cycle"
            
            explanation = self.format_explanation("Macro Analysis", points, summary)
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
            if is_crypto:
                explanation = f"Macro analysis: {default_analysis['macro_regime']} regime (default - LLM unavailable), "
                explanation += f"Fed cycle: {default_analysis.get('fed_cycle', 'NEUTRAL')}, "
                explanation += f"headwind score: {default_analysis['sector_headwind_score']:.2f}"
            else:
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

