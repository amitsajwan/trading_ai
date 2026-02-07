"""Macro agent implementing engine_module Agent contract.

Migration of legacy MacroAnalysisAgent into a simple agent that calls
an LLM structured method (which can be monkeypatched in tests) and
returns an AnalysisResult.
"""

import logging
from typing import Dict, Any

from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


class MacroAgent(Agent):
    """Macro agent that analyzes macro context and returns bias."""

    def __init__(self):
        """Initialize macro agent."""
        self._agent_name = "MacroAgent"

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        # Context may contain rbi_rate, inflation_rate, npa_ratio, and instrument_name
        rbi_rate = context.get("rbi_rate")
        inflation_rate = context.get("inflation_rate")
        npa_ratio = context.get("npa_ratio")
        instrument_name = context.get("instrument", "INSTRUMENT")

        # Check if we have any macro data
        has_macro_data = any([
            rbi_rate is not None,
            inflation_rate is not None,
            npa_ratio is not None
        ])

        if not has_macro_data:
            details = {
                "macro_regime": "UNKNOWN",
                "sector_headwind_score": 0.0,
                "confidence_score": 0.0,
                "time_horizon": "UNKNOWN",
                "note": "NO_MACRO_DATA_AVAILABLE",
                "data_available": False,
                "missing_data": ["rbi_rate", "inflation_rate", "npa_ratio"],
                "reasoning": "No macroeconomic data available for analysis"
            }
            return AnalysisResult(
                decision="EXCLUDED",
                confidence=0.0,
                details=details,
                excluded=True,
                exclusion_reason="No macroeconomic data available (RBI rate, inflation, NPA ratio)"
            )

        # Build a prompt (tests will monkeypatch _call_llm_structured)
        prompt = f"Macro context for {instrument_name}: rbi={rbi_rate}, inflation={inflation_rate}, npa={npa_ratio}"

        # Default analysis
        default = {
            "macro_regime": "MIXED",
            "sector_headwind_score": 0.0,
            "confidence_score": 0.5,
            "time_horizon": "INTRADAY_15M"
        }

        try:
            response_format = {
                "macro_regime": "RISK_ON|RISK_OFF|MIXED",
                "macro_headwind_score": "float (-1 to +1)",
                "confidence_score": "float (0-1)"
            }
            analysis = self._call_llm_structured(prompt, response_format)

            headwind = analysis.get("macro_headwind_score", 0.0)
            try:
                headwind = float(headwind) if headwind is not None else 0.0
            except Exception:
                headwind = 0.0

            macro_regime = (analysis.get("macro_regime") or "MIXED").upper()

            if headwind > 0.05 and macro_regime == "RISK_ON":
                macro_bias = "BULLISH"
            elif headwind < -0.05 and macro_regime == "RISK_OFF":
                macro_bias = "BEARISH"
            else:
                macro_bias = "NEUTRAL"

            decision = "HOLD"
            if macro_bias == "BULLISH":
                decision = "BUY"
            elif macro_bias == "BEARISH":
                decision = "SELL"

            confidence = float(analysis.get("confidence_score", 0.5) or 0.5)

            # Generate rich natural language reasoning
            reasoning_parts = []

            # Economic data analysis
            if rbi_rate is not None:
                if rbi_rate > 6.5:
                    reasoning_parts.append(f"RBI repo rate at {rbi_rate:.2f}% indicates tight monetary policy, potentially cooling economic growth.")
                elif rbi_rate < 5.5:
                    reasoning_parts.append(f"RBI repo rate at {rbi_rate:.2f}% suggests accommodative monetary stance, supporting economic expansion.")
                else:
                    reasoning_parts.append(f"RBI repo rate at {rbi_rate:.2f}% reflects neutral monetary policy stance.")

            if inflation_rate is not None:
                if inflation_rate > 6.0:
                    reasoning_parts.append(f"Inflation rate at {inflation_rate:.2f}% is elevated, which may prompt tighter monetary policy and pressure consumer spending.")
                elif inflation_rate < 3.0:
                    reasoning_parts.append(f"Inflation rate at {inflation_rate:.2f}% is contained, providing room for monetary accommodation.")
                else:
                    reasoning_parts.append(f"Inflation rate at {inflation_rate:.2f}% is moderate, maintaining policy stability.")

            if npa_ratio is not None:
                if npa_ratio > 4.0:
                    reasoning_parts.append(f"Gross NPA ratio at {npa_ratio:.2f}% indicates banking sector stress, potentially constraining credit growth.")
                elif npa_ratio < 2.0:
                    reasoning_parts.append(f"Gross NPA ratio at {npa_ratio:.2f}% suggests healthy banking sector, supporting credit expansion.")
                else:
                    reasoning_parts.append(f"Gross NPA ratio at {npa_ratio:.2f}% reflects manageable banking sector conditions.")

            # Market regime analysis
            if macro_regime == "RISK_ON":
                reasoning_parts.append("Current macro regime is risk-on, characterized by favorable economic conditions, low volatility, and positive growth expectations.")
            elif macro_regime == "RISK_OFF":
                reasoning_parts.append("Current macro regime is risk-off, marked by economic uncertainty, high volatility, and cautious market sentiment.")
            else:
                reasoning_parts.append("Current macro regime is mixed, with balanced economic indicators and moderate market volatility.")

            # Headwind analysis
            if abs(headwind) > 0.1:
                direction = "positive" if headwind > 0 else "negative"
                reasoning_parts.append(f"Sector headwind score of {headwind:.2f} indicates {direction} macro environment for {instrument_name}.")
            else:
                reasoning_parts.append(f"Sector headwind score of {headwind:.2f} suggests neutral macro conditions for {instrument_name}.")

            # Bias and decision rationale
            if macro_bias == "BULLISH":
                reasoning_parts.append(f"Bullish macro bias identified from {macro_regime.lower()} regime and favorable economic indicators.")
            elif macro_bias == "BEARISH":
                reasoning_parts.append(f"Bearish macro bias detected due to {macro_regime.lower()} regime and challenging economic backdrop.")
            else:
                reasoning_parts.append(f"Neutral macro bias prevails with mixed economic signals and balanced risk-reward profile.")

            # Decision rationale
            if decision == "BUY":
                reasoning_parts.append(f"BUY recommendation based on positive macro convergence with {macro_regime.lower()} regime and supportive economic data.")
            elif decision == "SELL":
                reasoning_parts.append(f"SELL recommendation driven by negative macro alignment with {macro_regime.lower()} regime and challenging economic conditions.")
            else:
                reasoning_parts.append(f"HOLD recommended due to neutral macro landscape requiring careful monitoring of economic developments.")

            # Investment implications
            reasoning_parts.append(f"Macro analysis suggests {macro_bias.lower()} positioning with {confidence:.1f} confidence in current economic assessment.")

            details = {
                "macro_regime": macro_regime,
                "sector_headwind_score": headwind,
                "macro_bias": macro_bias,
                "confidence_score": confidence,
                "reasoning": " ".join(reasoning_parts),
                "analysis_summary": f"Macro analysis identifies {macro_regime.lower()} regime with {macro_bias.lower()} bias and {confidence:.1f} confidence.",
                "economic_indicators": {
                    "rbi_rate": rbi_rate,
                    "inflation_rate": inflation_rate,
                    "npa_ratio": npa_ratio
                },
                "market_regime": macro_regime,
                "policy_stance": "tight" if rbi_rate and rbi_rate > 6.5 else "accommodative" if rbi_rate and rbi_rate < 5.5 else "neutral"
            }

            return AnalysisResult(decision=decision, confidence=confidence, details=details)

        except Exception as e:
            logger.warning(f"Macro analysis failed: {e}")
            return AnalysisResult(decision="HOLD", confidence=default["confidence_score"], details=default)

    def _call_llm_structured(self, prompt: str, response_format: Dict[str, Any]) -> Dict[str, Any]:
        """Stub for LLM structured call. Tests can monkeypatch this."""
        # Provide a simple deterministic heuristic based on prompt keywords
        if "inflation" in prompt and "high" in prompt:
            return {"macro_regime": "RISK_OFF", "macro_headwind_score": -0.2, "confidence_score": 0.6}
        return {"macro_regime": "MIXED", "macro_headwind_score": 0.0, "confidence_score": 0.5}

