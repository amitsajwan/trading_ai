"""Execution agent implementing engine_module Agent contract.

A simplified execution agent suitable for unit testing. It supports
paper trading by default and validates signals using `utils.signal_validation`.
"""

import logging
from typing import Dict, Any
from datetime import datetime

from engine_module.contracts import Agent, AnalysisResult
# Lazy import of signal validation to avoid import errors in isolated test runs
try:
    from utils.signal_validation import validate_trade_signal
except Exception:
    def validate_trade_signal(signal, entry_price, stop_loss, take_profit, confidence, current_market_price=None, tolerance_pct=0.50):
        # Fallback simple validator: ensure numeric values and logical SL/TP
        errors = []
        warnings = []
        try:
            e = float(entry_price)
            sl = float(stop_loss)
            tp = float(take_profit)
        except Exception as ex:
            errors.append(f"Price parse error: {ex}")
            return False, {"errors": errors, "warnings": warnings, "normalized_confidence": 0.5}
        if signal == "BUY":
            if sl >= e:
                errors.append("BUY signal: stop loss must be below entry")
            if tp <= e:
                errors.append("BUY signal: take profit must be above entry")
        elif signal == "SELL":
            if sl <= e:
                errors.append("SELL signal: stop loss must be above entry")
            if tp >= e:
                errors.append("SELL signal: take profit must be below entry")
        is_valid = len(errors) == 0
        return is_valid, {"errors": errors, "warnings": warnings, "normalized_confidence": min(0.99, max(0.0, float(confidence) if confidence is not None else 0.5))}
logger = logging.getLogger(__name__)


class ExecutionAgent(Agent):
    """Execution agent that simulates order placement (paper trading by default)."""

    def __init__(self, paper_trading: bool = True):
        self.paper_trading = paper_trading
        self._agent_name = "ExecutionAgent"

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        # Expected context: final_signal (BUY/SELL/HOLD), position_size, entry_price, stop_loss, take_profit, current_price
        signal = context.get("final_signal")
        if signal is None:
            return AnalysisResult(decision="HOLD", confidence=0.0, details={"note": "NO_SIGNAL"})

        signal_str = signal.value if hasattr(signal, "value") else str(signal)
        if signal_str not in ("BUY", "SELL"):
            return AnalysisResult(decision="HOLD", confidence=0.0, details={"note": "NO_EXECUTION"})

        quantity = int(context.get("position_size", 0))
        entry_price = context.get("entry_price")
        stop_loss = context.get("stop_loss")
        take_profit = context.get("take_profit")
        current_price = context.get("current_price")
        overall_confidence = float(context.get("confidence", 0.5))

        if quantity <= 0:
            return AnalysisResult(decision="HOLD", confidence=0.0, details={"note": "ZERO_QUANTITY"})

        # Validate trade signal
        is_valid, validation = validate_trade_signal(
            signal=signal_str,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=overall_confidence,
            current_market_price=current_price,
            tolerance_pct=0.50
        )

        if not is_valid:
            return AnalysisResult(decision="HOLD", confidence=0.0, details={"errors": validation.get("errors", [])})

        normalized_conf = validation.get("normalized_confidence", overall_confidence)

        # Place order (paper)
        order_id = f"PAPER_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        order_result = {
            "order_id": order_id,
            "filled_price": float(entry_price),
            "filled_quantity": quantity,
            "execution_timestamp": datetime.now().isoformat(),
            "status": "COMPLETE",
            "paper_trading": True
        }

        details = {"order": order_result, "validation": validation}
        return AnalysisResult(decision=signal_str, confidence=normalized_conf, details=details)

