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
        instrument_name = context.get("instrument_name", "INSTRUMENT")

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
            details = {
                "macro_regime": macro_regime,
                "sector_headwind_score": headwind,
                "macro_bias": macro_bias,
                "confidence_score": confidence
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

