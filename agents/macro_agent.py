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
                    "macro_regime": "RISK_ON | RISK_OFF | MIXED",
                    "macro_regime_reasoning": "string",
                    "monetary_cycle": "TIGHTENING | EASING | NEUTRAL",
                    "monetary_cycle_reasoning": "string",
                    "rate_cut_probability": "float (0-1)",
                    "rate_hike_probability": "float (0-1)",
                    "rate_probability_reasoning": "string",
                    "risk_appetite": "HIGH | MEDIUM | LOW",
                    "risk_reasoning": "string",
                    "liquidity_condition": "EASY | NORMAL | TIGHT",
                    "liquidity_reasoning": "string",
                    "macro_headwind_score": "float (-1 to +1)",
                    "headwind_reasoning": "string",
                    "confidence_score": "float (0-1)",
                    "confidence_reasoning": "string"
                }
            else:
                # Indian stocks/banking sector context
                prompt = f"""
Macro Economic Context:
- Interest Rate: {rbi_rate if rbi_rate else 'Unknown'}
- Inflation Rate: {inflation_rate if inflation_rate else 'Unknown'}
- Market Health Indicator: {npa_ratio if npa_ratio else 'Unknown'}

Analyze the macro regime and its impact on {instrument_name}.
Use a 15-minute to 1-day trading horizon and focus on how
macro conditions change the odds of bullish vs bearish moves.
"""
                response_format = {
                    "macro_regime": "RISK_ON | RISK_OFF | MIXED",
                    "macro_regime_reasoning": "string",
                    "monetary_cycle": "TIGHTENING | EASING | NEUTRAL",
                    "monetary_cycle_reasoning": "string",
                    "rate_cut_probability": "float (0-1)",
                    "rate_hike_probability": "float (0-1)",
                    "rate_probability_reasoning": "string",
                    "risk_appetite": "HIGH | MEDIUM | LOW",
                    "risk_reasoning": "string",
                    "liquidity_condition": "EASY | NORMAL | TIGHT",
                    "liquidity_reasoning": "string",
                    "macro_headwind_score": "float (-1 to +1)",
                    "headwind_reasoning": "string",
                    "confidence_score": "float (0-1)",
                    "confidence_reasoning": "string"
                }
            
            analysis = self._call_llm_structured(prompt, response_format)
            
            # Normalize schema for downstream agents
            headwind_score = analysis.get('macro_headwind_score', analysis.get('sector_headwind_score', 0.0))
            # Ensure it's a float before formatting
            try:
                headwind_score = float(headwind_score) if headwind_score is not None else 0.0
            except (ValueError, TypeError):
                headwind_score = 0.0

            # Derive a simple macro bias (BULLISH/BEARISH/NEUTRAL) for the
            # near-term horizon based on regime and headwind score.
            macro_regime = (analysis.get('macro_regime') or '').upper()
            if headwind_score > 0.05 and macro_regime == 'RISK_ON':
                macro_bias = "BULLISH"
            elif headwind_score < -0.05 and macro_regime == 'RISK_OFF':
                macro_bias = "BEARISH"
            else:
                macro_bias = "NEUTRAL"

            normalized = dict(analysis)
            # Keep backwards-compatible field names used by portfolio manager
            normalized.setdefault('sector_headwind_score', headwind_score)
            # RBI/Fed cycle compatible key
            monetary_cycle = analysis.get('monetary_cycle')
            if is_crypto:
                normalized.setdefault('fed_cycle', monetary_cycle or 'NEUTRAL')
            else:
                normalized.setdefault('rbi_cycle', monetary_cycle or 'NEUTRAL')
            normalized.setdefault('macro_bias', macro_bias)
            normalized.setdefault('time_horizon', 'INTRADAY_15M')
            
            # Build human-readable explanation with points and reasoning
            if is_crypto:
                fed_cycle = normalized.get('fed_cycle')
                if not fed_cycle:
                    fed_cycle = analysis.get('rbi_cycle', 'UNKNOWN')
                    logger.warning("LLM returned rbi_cycle for crypto, should return fed_cycle")
                
                rate_cut_prob = analysis.get('rate_cut_probability', 0.5)
                rate_hike_prob = analysis.get('rate_hike_probability', 0.5)
                dollar_strength = analysis.get('dollar_strength', 'NEUTRAL')
                liquidity = analysis.get('liquidity_condition', 'NORMAL')
                confidence = analysis.get('confidence_score', 0.5)
                
                points = [
                    ("Macro Regime", macro_regime or 'UNKNOWN',
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
                    ("Macro Bias (15m)", macro_bias,
                     f"Near-term macro tilt for risk assets"),
                    ("Confidence", f"{confidence:.0%}",
                     f"Analysis confidence based on data quality")
                ]
                
                summary = f"Overall: {macro_regime or 'UNKNOWN'} regime with {fed_cycle} Fed cycle ({macro_bias} bias, 15m horizon)"
            else:
                rate_cut_prob = analysis.get('rate_cut_probability', 0.5)
                rate_hike_prob = analysis.get('rate_hike_probability', 0.5)
                npa_level = analysis.get('npa_concern_level', 'MEDIUM')
                liquidity = analysis.get('liquidity_condition', 'NORMAL')
                confidence = analysis.get('confidence_score', 0.5)
                
                points = [
                    ("Macro Regime", macro_regime or 'UNKNOWN',
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
                    ("Macro Bias (15m)", macro_bias,
                     f"Near-term macro tilt for risk assets"),
                    ("Confidence", f"{confidence:.0%}",
                     f"Analysis confidence based on data quality")
                ]
                
                summary = f"Overall: {macro_regime or 'UNKNOWN'} regime with {normalized.get('rbi_cycle', 'UNKNOWN')} RBI cycle ({macro_bias} bias, 15m horizon)"
            
            explanation = self.format_explanation("Macro Analysis", points, summary)
            self.update_state(state, normalized, explanation)
        
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

