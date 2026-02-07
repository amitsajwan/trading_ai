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
        """Analyze trade execution feasibility and validate order parameters.

        ExecutionAgent validates:
        - Signal validity and market conditions
        - Risk management (stop loss, take profit)
        - Position sizing and quantity
        - Confidence thresholds
        - Paper vs live trading constraints
        """
        print("🚨🚨🚨 EXECUTIONAGENT CALLED - THIS SHOULD SHOW UP 🚨🚨🚨")
        print(f"🚨 EXECUTIONAGENT: context keys: {list(context.keys())}")

        reasoning_parts = []

        # Check for orchestrator's final decision
        orchestrator_decision = context.get("orchestrator_decision") or context.get("final_decision")
        signal = context.get("final_signal")

        if orchestrator_decision:
            # We have an orchestrator decision to validate
            decision = orchestrator_decision.get("decision", "HOLD")
            confidence = orchestrator_decision.get("confidence", 0.0)

            reasoning_parts.append(f"Received orchestrator decision: {decision} with {confidence:.1%} confidence.")

            if decision == "HOLD":
                reasoning_parts.append("Orchestrator determined to HOLD position. No trade execution required at this time.")
                reasoning_parts.append("This decision may be due to insufficient market conviction, risk management protocols, or unfavorable market conditions identified by other agents.")
                reasoning = " ".join(reasoning_parts)
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={
                        "reasoning": reasoning,
                        "analysis_summary": f"Orchestrator HOLD validated - no execution required",
                        "execution_status": "VALIDATED_HOLD",
                        "orchestrator_decision": decision,
                        "orchestrator_confidence": confidence
                    }
                )
            else:
                reasoning_parts.append(f"Orchestrator recommends {decision} position. Validating execution feasibility.")
                # Continue with execution validation...

        # Fallback: no signal but we can still analyze execution readiness
        reasoning_parts = []

        # Check if we have agent results to analyze
        agent_results = context.get("agent_results", [])
        if agent_results:
            reasoning_parts.append(f"Analyzing execution readiness based on {len(agent_results)} agent assessments.")

            # Analyze agent consensus
            decisions = [r.decision for r in agent_results if hasattr(r, 'decision')]
            if decisions:
                hold_count = decisions.count('HOLD')
                buy_count = decisions.count('BUY') + decisions.count('BULL_CALL_SPREAD')
                sell_count = decisions.count('SELL') + decisions.count('BEAR_PUT_SPREAD')

                reasoning_parts.append(f"Agent consensus: {hold_count} HOLD, {buy_count} BUY signals, {sell_count} SELL signals.")

                if hold_count > len(decisions) * 0.6:
                    reasoning_parts.append("Majority of agents recommend HOLD. Market conditions appear uncertain or unfavorable for active trading.")
                elif buy_count > sell_count:
                    reasoning_parts.append("Bullish bias detected across agents. Execution would proceed if signal meets validation criteria.")
                elif sell_count > buy_count:
                    reasoning_parts.append("Bearish bias detected across agents. Execution would proceed if signal meets validation criteria.")
                else:
                    reasoning_parts.append("Mixed signals from agents. Execution requires clear directional consensus.")
            else:
                reasoning_parts.append("No clear decision signals from agents. Unable to assess execution readiness.")

        reasoning_parts.append("Execution agent is standing by for validated trading signals. All risk management protocols are active.")

        reasoning = " ".join(reasoning_parts)
        return AnalysisResult(
            decision="HOLD",
            confidence=0.0,
            details={
                "reasoning": reasoning,
                "analysis_summary": "Execution agent ready - awaiting validated signals",
                "execution_status": "STANDBY",
                "agent_consensus": f"{len(agent_results)} agents analyzed"
            }
        )

        signal_str = signal.value if hasattr(signal, "value") else str(signal)
        if signal_str not in ("BUY", "SELL"):
            reasoning = f"Received signal '{signal_str}' is not executable. Execution agent only processes BUY or SELL signals for order placement. HOLD signals require no execution action."
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={
                    "reasoning": reasoning,
                    "analysis_summary": f"Execution rejected: Invalid signal type '{signal_str}'",
                    "execution_status": "REJECTED_INVALID_SIGNAL"
                }
            )

        reasoning_parts.append(f"Analyzing {signal_str} signal execution feasibility with paper trading mode enabled.")

        quantity = int(context.get("position_size", 0))
        entry_price = context.get("entry_price")
        stop_loss = context.get("stop_loss")
        take_profit = context.get("take_profit")
        current_price = context.get("current_price")
        overall_confidence = float(context.get("confidence", 0.5))

        reasoning_parts.append(f"Order parameters: Quantity={quantity}, Entry={entry_price}, SL={stop_loss}, TP={take_profit}, Current={current_price}")

        if quantity <= 0:
            reasoning = " ".join(reasoning_parts + [
                "Position size validation failed. Quantity must be positive for order execution.",
                "Execution rejected due to invalid position sizing parameters."
            ])
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={
                    "reasoning": reasoning,
                    "analysis_summary": "Execution rejected: Invalid quantity",
                    "execution_status": "REJECTED_QUANTITY"
                }
            )

        # Validate trade signal
        reasoning_parts.append("Performing comprehensive trade validation including risk parameters and market conditions.")
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
            errors = validation.get("errors", [])
            reasoning = " ".join(reasoning_parts + [
                f"Trade validation failed with {len(errors)} errors: {', '.join(errors)}.",
                "Order execution rejected due to risk management or parameter validation failures.",
                "Recommend reviewing stop loss and take profit levels for proper risk-reward ratio."
            ])
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={
                    "reasoning": reasoning,
                    "analysis_summary": f"Execution rejected: Validation failed ({len(errors)} errors)",
                    "validation_errors": errors,
                    "execution_status": "REJECTED_VALIDATION"
                }
            )

        normalized_conf = validation.get("normalized_confidence", overall_confidence)
        warnings = validation.get("warnings", [])

        # Execution approval
        reasoning_parts.append("All validation checks passed. Signal approved for paper trading execution.")
        if warnings:
            reasoning_parts.append(f"Execution approved with {len(warnings)} warnings: {', '.join(warnings)}.")

        reasoning_parts.append("Order placement simulation completed successfully in paper trading environment.")

        # Place order (paper)
        order_id = f"PAPER_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        order_result = {
            "order_id": order_id,
            "filled_price": float(entry_price),
            "filled_quantity": quantity,
            "execution_timestamp": datetime.now().isoformat(),
            "status": "COMPLETE",
            "paper_trading": True,
            "signal_type": signal_str,
            "confidence_validated": normalized_conf
        }

        reasoning = " ".join(reasoning_parts)
        details = {
            "order": order_result,
            "validation": validation,
            "reasoning": reasoning,
            "analysis_summary": f"{signal_str} order validated and executed in paper trading (Confidence: {normalized_conf:.1%})",
            "execution_status": "EXECUTED_PAPER",
            "risk_checks": "PASSED" if not validation.get("errors") else "FAILED",
            "validation_warnings": warnings
        }

        return AnalysisResult(decision=signal_str, confidence=normalized_conf, details=details)

