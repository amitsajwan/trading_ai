"""Bear researcher agent: provides bearish thesis with memory and structured reporting."""

from typing import Dict, Any
from engine_module.contracts import Agent, AnalysisResult
from engine_module.utils.memory import AgentMemory
import logging

# Import standardized indicator names
try:
    from market_data.technical_indicators_constants import *
except ImportError:
    # Fallback if constants not available
    RSI_14 = "rsi_14"
    MACD_SIGNAL = "macd_signal"
    TREND_DIRECTION = "trend_direction"

logger = logging.getLogger(__name__)


class BearResearcher(Agent):
    """Conservative trader providing defensive strategy parameters with lower risk focus."""

    def __init__(self):
        self._agent_name = "BearResearcher"
        self.memory = AgentMemory("bear_researcher")

        # Trader profile: Conservative, risk-focused
        self.trading_style = {
            "risk_tolerance": "low",
            "time_horizon": "medium_to_long",
            "strategy_preference": "defensive",
            "volatility_preference": "low_to_moderate"
        }

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Act as a conservative trader providing defensive strategy parameters."""
        try:
            symbol = context.get('instrument', 'UNKNOWN')
            technical = context.get('technical_indicators', {}) or context.get('technical', {})
            current_price = context.get('current_price', 0)
            options_data = context.get('options_data', {})

            # Extract key market data
            rsi_val = technical.get(RSI_14, 50)
            trend_direction = technical.get(TREND_DIRECTION, 'SIDEWAYS')
            adx_val = technical.get('adx_14', 20)
            volatility = technical.get('volatility_level', 'MEDIUM')

            # BEAR RESEARCHER TRADING DECISIONS
            # As a conservative trader, I focus on risk management and capital preservation
            # I prefer tighter strikes and lower risk/reward setups

            trading_decision = self._make_trading_decision(
                current_price, rsi_val, trend_direction, adx_val, volatility, options_data
            )

            # Generate structured reasoning like a professional risk-manager trader
            reasoning = self._generate_trader_reasoning(
                symbol, current_price, rsi_val, trend_direction, adx_val, volatility, trading_decision
            )

            return AnalysisResult(
                decision=trading_decision['strategy_type'],
                confidence=trading_decision['confidence'],
                details={
                    "trading_parameters": trading_decision['parameters'],
                    "risk_assessment": trading_decision['risk_assessment'],
                    "market_view": "conservative_defensive",
                    "trader_style": "risk_focused",
                    "position_sizing": trading_decision['position_sizing'],
                    "entry_conditions": trading_decision['entry_conditions'],
                    "exit_strategy": trading_decision['exit_strategy'],
                    "reasoning": reasoning
                }
            )

        except Exception as e:
            logger.exception("BearResearcher trading decision failed")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={"error": str(e), "trader_style": "conservative_defensive"},
                reasoning=f"Conservative trader analysis failed: {str(e)}"
            )

    def _make_trading_decision(self, current_price: float, rsi_val: float,
                              trend_direction: str, adx_val: float, volatility: str,
                              options_data: Dict) -> Dict[str, Any]:
        """Make specific trading decisions as a conservative bear trader."""

        # Base decision on market regime - conservative approach
        if adx_val > 25:  # Strong trend
            if trend_direction == "DOWN":
                strategy_type = "BEAR_PUT_SPREAD"
                confidence = 0.7
            elif trend_direction == "UP":
                strategy_type = "IRON_CONDOR"  # Conservative play in uptrend
                confidence = 0.6
            else:
                strategy_type = "BEAR_CALL_SPREAD"
                confidence = 0.65
        else:  # Range-bound market - conservative preference
            if rsi_val > 60:  # Overbought bounce potential
                strategy_type = "BEAR_PUT_SPREAD"
                confidence = 0.7
            else:
                strategy_type = "IRON_CONDOR"  # Premium collection
                confidence = 0.65

        # Conservative trader adjustments
        if rsi_val > 70:  # Very overbought
            confidence += 0.05  # Slightly more confident
        if volatility == "HIGH":
            confidence -= 0.15  # Much more cautious in high vol
        if trend_direction == "DOWN":
            confidence += 0.05  # More confident in downtrends

        # Specific trading parameters based on strategy - CONSERVATIVE APPROACH
        if strategy_type == "IRON_CONDOR":
            parameters = {
                "strike_selection": {
                    "put_sell_range": "2-3% OTM",  # Tighter strikes for lower risk
                    "put_buy_range": "5-7% OTM",
                    "call_sell_range": "2-3% OTM",
                    "call_buy_range": "5-7% OTM"
                },
                "position_sizing": {
                    "allocation": "50% puts, 50% calls",  # Balanced for conservatism
                    "max_loss_limit": "₹5,000",  # Lower risk tolerance
                    "target_profit": "₹1,500"
                },
                "risk_management": {
                    "stop_loss": "25% of max loss",  # Tighter stops
                    "trailing_stop": False,  # No trailing for conservatism
                    "time_decay_management": "Close if theta decay > ₹200/day"
                }
            }
        elif strategy_type == "BEAR_PUT_SPREAD":
            parameters = {
                "strike_selection": {
                    "put_sell_range": "ATM to 1% OTM",
                    "put_buy_range": "3-4% OTM"  # Tighter wing for lower risk
                },
                "position_sizing": {
                    "allocation": "Equal weighting",
                    "max_loss_limit": "₹8,000",
                    "target_profit": "₹2,500"
                },
                "risk_management": {
                    "stop_loss": "20% of premium paid",
                    "time_decay_management": "Monitor delta changes closely"
                }
            }
        else:
            parameters = {}

        return {
            "strategy_type": strategy_type,
            "confidence": min(confidence, 0.85),  # Cap at 85% for conservatism
            "parameters": parameters,
            "risk_assessment": {
                "volatility_suitability": "low_to_moderate" if volatility in ["LOW", "MODERATE"] else "avoid",
                "trend_alignment": "favorable" if trend_direction == "DOWN" else "cautious",
                "momentum_strength": "moderate" if rsi_val > 60 else "weak"
            },
            "position_sizing": parameters.get("position_sizing", {}),
            "entry_conditions": {
                "technical_filters": [f"RSI > {rsi_val - 5}", f"Trend: {trend_direction}"],
                "timing": "Enter on overbought signal" if rsi_val > 70 else "Enter on bearish divergence"
            },
            "exit_strategy": {
                "profit_taking": "Take full profit at target, no scaling",
                "loss_management": "Cut losses immediately at stop level",
                "time_based": "Close position 5 days before expiry for safety"
            }
        }

    def _generate_trader_reasoning(self, symbol: str, current_price: float, rsi_val: float,
                                  trend_direction: str, adx_val: float, volatility: str,
                                  trading_decision: Dict) -> str:
        """Generate professional conservative trader-style reasoning."""

        strategy = trading_decision['strategy_type']
        confidence = trading_decision['confidence']

        reasoning_parts = [
            f"As a conservative trader, I'm focusing on capital preservation in {symbol} at ₹{current_price:.2f}.",
            f"Market regime: {trend_direction} trend (ADX: {adx_val:.1f}), volatility: {volatility}, RSI: {rsi_val:.1f}.",
            f"My thesis: {'Overbought conditions suggest caution' if rsi_val > 70 else 'Favorable risk management setup'}.",
            f"Strategy selection: {strategy} with {confidence:.1f} confidence for controlled risk.",
            f"Strike positioning: {trading_decision['parameters'].get('strike_selection', {}).get('put_sell_range', 'conservative')} OTM puts.",
            f"Risk management: {trading_decision['risk_assessment']['volatility_suitability']} volatility environment, {trading_decision['risk_assessment']['trend_alignment']} trend alignment.",
            f"Position sizing: {trading_decision['position_sizing'].get('allocation', 'balanced')} with ₹{trading_decision['position_sizing'].get('max_loss_limit', '5,000')} strict loss limit.",
            "Entry: Only when risk parameters align. Exit: Quick profit taking, strict loss management."
        ]

        return " ".join(reasoning_parts)
