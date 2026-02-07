"""Signal Creation Agent - Final signal synthesis from all agent inputs."""

import logging
from typing import Dict, Any, List
from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


class SignalCreationAgent(Agent):
    """Centralized signal creation agent that synthesizes final trading signals.

    This agent takes inputs from all analysis agents and creates final executable
    signals considering:
    - Current market conditions
    - Agent consensus and confidence levels
    - Risk management (position sizing, stop losses, take profits)
    - Current positions and cash availability
    - Market volatility and risk limits
    """

    def __init__(self, risk_config: Dict[str, Any] = None):
        self._agent_name = "SignalCreationAgent"
        self.risk_config = risk_config or {
            'max_position_size_pct': 0.02,  # 2% of portfolio per trade
            'max_total_risk_pct': 0.05,     # 5% total portfolio risk
            'min_confidence_threshold': 0.6, # Minimum confidence for signal creation
            'atr_stop_multiplier': 2.0,     # ATR-based stops
            'reward_risk_ratio': 2.0,       # Minimum R:R ratio
        }

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Create final executable signals from agent analysis inputs.

        Args:
            context: Must include:
                - 'agent_results': List[AnalysisResult] from all analysis agents
                - 'current_positions': Current portfolio positions
                - 'cash_available': Available cash
                - 'technical_indicators': Current market indicators
                - 'current_price': Current market price
                - 'volatility': Current market volatility

        Returns:
            AnalysisResult with structured signals in details['signals']
        """
        try:
            agent_results = context.get('agent_results', [])
            current_positions = context.get('current_positions', [])
            cash_available = context.get('cash_available', 1000000)
            technical_indicators = context.get('technical_indicators', {})
            current_price = context.get('current_price', 0)
            volatility = context.get('volatility', 0.15)

            if not agent_results:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={
                        "reasoning": "No agent analysis available for signal creation",
                        "signals": []
                    },
                    agent=self._agent_name
                )

            # Analyze agent consensus
            consensus = self._analyze_agent_consensus(agent_results)
            logger.info(f"Agent consensus: {consensus['decision']} (confidence: {consensus['confidence']:.2f})")

            # Check risk limits
            risk_assessment = self._assess_risk_limits(
                consensus, current_positions, cash_available, current_price
            )

            if not risk_assessment['can_trade']:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.8,
                    details={
                        "reasoning": f"Risk limits prevent trading: {risk_assessment['reason']}",
                        "consensus": consensus,
                        "risk_assessment": risk_assessment,
                        "signals": []
                    },
                    agent=self._agent_name
                )

            # Create final signals
            signals = self._create_final_signals(
                consensus, technical_indicators, current_price,
                volatility, risk_assessment, agent_results
            )

            confidence = min(consensus['confidence'] * risk_assessment['risk_multiplier'], 0.95)

            return AnalysisResult(
                decision=consensus['decision'],
                confidence=confidence,
                details={
                    "reasoning": self._generate_signal_reasoning(consensus, risk_assessment, signals),
                    "consensus": consensus,
                    "risk_assessment": risk_assessment,
                    "signals": signals,
                    "signal_count": len(signals)
                },
                agent=self._agent_name
            )

        except Exception as e:
            logger.exception("Signal creation failed")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={
                    "reasoning": f"Signal creation error: {str(e)}",
                    "error": str(e),
                    "signals": []
                },
                agent=self._agent_name
            )

    def _analyze_agent_consensus(self, agent_results: List[AnalysisResult]) -> Dict[str, Any]:
        """Analyze consensus across all agent results."""
        if not agent_results:
            return {"decision": "HOLD", "confidence": 0.0, "supporting_agents": 0}

        # Group by decision
        decision_counts = {}
        weighted_confidence = {}

        for result in agent_results:
            decision = result.decision.upper()
            confidence = result.confidence

            if decision not in decision_counts:
                decision_counts[decision] = 0
                weighted_confidence[decision] = 0

            decision_counts[decision] += 1
            weighted_confidence[decision] += confidence

        # Find consensus decision
        max_count = max(decision_counts.values())
        consensus_decisions = [d for d, c in decision_counts.items() if c == max_count]

        # If tie, prefer HOLD for safety
        if len(consensus_decisions) > 1:
            consensus_decision = "HOLD"
            consensus_confidence = 0.5
        else:
            consensus_decision = consensus_decisions[0]
            consensus_confidence = weighted_confidence[consensus_decision] / decision_counts[consensus_decision]

        # Special handling for options strategies
        options_strategies = [d for d in decision_counts.keys() if any(x in d for x in ["CALL", "PUT", "CONDOR", "SPREAD"])]
        if options_strategies:
            # Use the highest confidence options strategy
            best_options = max(options_strategies, key=lambda x: weighted_confidence[x] / decision_counts[x])
            if weighted_confidence[best_options] / decision_counts[best_options] > consensus_confidence:
                consensus_decision = best_options
                consensus_confidence = weighted_confidence[best_options] / decision_counts[best_options]

        return {
            "decision": consensus_decision,
            "confidence": consensus_confidence,
            "supporting_agents": decision_counts.get(consensus_decision, 0),
            "total_agents": len(agent_results),
            "decision_breakdown": decision_counts
        }

    def _assess_risk_limits(self, consensus: Dict, positions: List, cash_available: float, current_price: float) -> Dict[str, Any]:
        """Assess if trading is allowed within risk limits."""
        # Check minimum confidence
        if consensus['confidence'] < self.risk_config['min_confidence_threshold']:
            return {
                "can_trade": False,
                "reason": f"Consensus confidence {consensus['confidence']:.2f} below threshold {self.risk_config['min_confidence_threshold']}",
                "risk_multiplier": 0.0
            }

        # Check position limits (simplified - you'd check actual position sizing logic)
        max_position_value = cash_available * self.risk_config['max_position_size_pct']
        if current_price > 0 and max_position_value < current_price:
            return {
                "can_trade": False,
                "reason": f"Position size would exceed limit (max: {max_position_value:.0f}, needed: {current_price:.0f})",
                "risk_multiplier": 0.0
            }

        # Calculate risk multiplier based on confidence and market conditions
        risk_multiplier = min(consensus['confidence'] * 1.2, 1.0)

        return {
            "can_trade": True,
            "reason": "Risk limits allow trading",
            "risk_multiplier": risk_multiplier,
            "max_position_value": max_position_value
        }

    def _create_final_signals(self, consensus: Dict, technical_indicators: Dict,
                            current_price: float, volatility: float,
                            risk_assessment: Dict, agent_results: List[AnalysisResult]) -> List[Dict[str, Any]]:
        """Create final executable signals."""
        signals = []

        if consensus['decision'] == "HOLD":
            return signals

        # Get ATR for risk management
        atr = technical_indicators.get('atr', current_price * volatility * 0.02)
        if not atr or atr <= 0:
            atr = current_price * 0.02  # Fallback 2% of price

        # Calculate position sizing
        max_position_value = risk_assessment['max_position_value']
        position_size = min(max_position_value / current_price, 100)  # Max 100 contracts

        # Calculate stop loss and take profit
        if consensus['decision'] in ["BUY", "BULL_CALL_SPREAD"]:
            stop_loss = current_price - (atr * self.risk_config['atr_stop_multiplier'])
            take_profit = current_price + (atr * self.risk_config['atr_stop_multiplier'] * self.risk_config['reward_risk_ratio'])
            entry_condition = {
                "indicator": "current_price",
                "operator": "GREATER_EQUAL",
                "threshold": current_price * 0.998,  # Slight pullback for entry
                "source": "signal_creation"
            }
        elif consensus['decision'] in ["SELL", "BEAR_PUT_SPREAD"]:
            stop_loss = current_price + (atr * self.risk_config['atr_stop_multiplier'])
            take_profit = current_price - (atr * self.risk_config['atr_stop_multiplier'] * self.risk_config['reward_risk_ratio'])
            entry_condition = {
                "indicator": "current_price",
                "operator": "LESS_EQUAL",
                "threshold": current_price * 1.002,  # Slight rally for entry
                "source": "signal_creation"
            }
        else:
            # Options strategies - use existing logic or create simple condition
            entry_condition = {
                "indicator": "current_price",
                "operator": "GREATER_EQUAL",
                "threshold": current_price * 0.995,
                "source": "options_entry"
            }
            stop_loss = current_price * 0.8 if "BUY" in consensus['decision'] else current_price * 1.2
            take_profit = current_price * 1.5 if "BUY" in consensus['decision'] else current_price * 0.5

        signal = {
            "action": consensus['decision'],
            "strategy_type": "OPTIONS" if any(x in consensus['decision'] for x in ["CALL", "PUT", "CONDOR", "SPREAD"]) else "SPOT",
            "execution_mode": "CONDITIONAL",
            "confidence": consensus['confidence'],
            "position_size": position_size,
            "conditions": [entry_condition],
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "entry_price": current_price,
            "risk_reward_ratio": self.risk_config['reward_risk_ratio'],
            "valid_for_minutes": 30,
            "metadata": {
                "signal_source": "SignalCreationAgent",
                "agent_consensus": f"{consensus['supporting_agents']}/{consensus['total_agents']} agents agree",
                "risk_based_sizing": True,
                "atr_based_stops": True
            }
        }

        signals.append(signal)
        return signals

    def _generate_signal_reasoning(self, consensus: Dict, risk_assessment: Dict, signals: List[Dict]) -> str:
        """Generate natural language reasoning for signal creation."""
        parts = []

        parts.append(f"Signal creation analysis shows {consensus['decision']} consensus from {consensus['supporting_agents']}/{consensus['total_agents']} agents")

        if consensus['confidence'] >= 0.7:
            parts.append("with strong conviction")
        elif consensus['confidence'] >= 0.5:
            parts.append("with moderate confidence")
        else:
            parts.append("with cautious approach")

        if risk_assessment['can_trade']:
            parts.append("and risk limits allow position establishment")
        else:
            parts.append(f"but {risk_assessment['reason']}")

        if signals:
            signal = signals[0]
            parts.append(f"Created {len(signals)} signal(s) with {signal['position_size']:.1f} position size")
            parts.append(f"Risk management: Stop loss at {signal['stop_loss']:.0f}, Target at {signal['take_profit']:.0f}")

        return ". ".join(parts)