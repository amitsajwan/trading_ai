"""Bull Researcher Agent: Aggressive trader providing bullish strategy parameters."""

from typing import Dict, Any
from engine_module.contracts import Agent, AnalysisResult
from engine_module.utils.memory import AgentMemory
import logging

# Import standardized indicator names
try:
    from market_data.technical_indicators_constants import *
except ImportError:
    # Fallback if constants not available - use the actual Redis key names
    RSI_14 = "rsi_14"
    MACD_SIGNAL = "macd_signal"
    TREND_DIRECTION = "trend_direction"

logger = logging.getLogger(__name__)


class BullResearcher(Agent):
    """Aggressive trader providing bullish strategy parameters with higher risk/reward focus."""

    def __init__(self):
        self._agent_name = "BullResearcher"
        self.memory = AgentMemory("bull_researcher")

        # Trader profile: Aggressive, momentum-focused
        self.trading_style = {
            "risk_tolerance": "high",
            "time_horizon": "short_to_medium",
            "strategy_preference": "directional",
            "volatility_preference": "moderate_to_high"
        }

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Act as an aggressive trader providing specific bullish strategy parameters."""
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

            # BULL RESEARCHER TRADING DECISIONS
            # As an aggressive trader, I focus on momentum and trend continuation
            # I prefer wider strikes to capture bigger moves with higher risk/reward

            trading_decision = self._make_trading_decision(
                current_price, rsi_val, trend_direction, adx_val, volatility, options_data
            )

            # Generate structured reasoning like a professional trader
            reasoning = self._generate_trader_reasoning(
                symbol, current_price, rsi_val, trend_direction, adx_val, volatility, trading_decision
            )

            return AnalysisResult(
                decision=trading_decision['strategy_type'],
                confidence=trading_decision['confidence'],
                details={
                    "trading_parameters": trading_decision['parameters'],
                    "risk_assessment": trading_decision['risk_assessment'],
                    "market_view": "bullish_aggressive",
                    "trader_style": "momentum_focused",
                    "position_sizing": trading_decision['position_sizing'],
                    "entry_conditions": trading_decision['entry_conditions'],
                    "exit_strategy": trading_decision['exit_strategy'],
                    "reasoning": reasoning
                }
            )

        except Exception as e:
            logger.exception("BullResearcher trading decision failed")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={"error": str(e), "trader_style": "bullish_aggressive"},
                reasoning=f"Bull trader analysis failed: {str(e)}"
            )

    def _make_trading_decision(self, current_price: float, rsi_val: float,
                              trend_direction: str, adx_val: float, volatility: str,
                              options_data: Dict) -> Dict[str, Any]:
        """Make specific trading decisions as an aggressive bull trader."""

        # Base decision on market regime
        if adx_val > 25:  # Strong trend
            if trend_direction == "UP":
                strategy_type = "BULL_CALL_SPREAD"
                confidence = 0.75
            elif trend_direction == "DOWN":
                strategy_type = "IRON_CONDOR"  # Conservative play in downtrend
                confidence = 0.6
            else:
                strategy_type = "BULL_PUT_SPREAD"
                confidence = 0.65
        else:  # Range-bound market
            if rsi_val < 40:  # Oversold bounce potential
                strategy_type = "BULL_CALL_SPREAD"
                confidence = 0.7
            else:
                strategy_type = "IRON_CONDOR"  # Premium collection
                confidence = 0.65

        # Aggressive trader adjustments
        if rsi_val < 30:  # Very oversold
            confidence += 0.1  # More aggressive
        if volatility == "HIGH":
            confidence -= 0.1  # More cautious in high vol

        # Specific trading parameters based on strategy
        if strategy_type == "IRON_CONDOR":
            parameters = {
                "strike_selection": {
                    "put_sell_range": "3-5% OTM",  # Wider strikes for premium
                    "put_buy_range": "8-12% OTM",
                    "call_sell_range": "3-5% OTM",
                    "call_buy_range": "8-12% OTM"
                },
                "position_sizing": {
                    "allocation": "60% puts, 40% calls",  # Favor put side for bull bias
                    "max_loss_limit": "₹10,000",
                    "target_profit": "₹3,000"
                },
                "risk_management": {
                    "stop_loss": "50% of max loss",
                    "trailing_stop": True,
                    "time_decay_management": "Close if theta decay > ₹500/day"
                }
            }
        elif strategy_type == "BULL_CALL_SPREAD":
            parameters = {
                "strike_selection": {
                    "call_buy_range": "ATM to 2% OTM",
                    "call_sell_range": "5-8% OTM"
                },
                "position_sizing": {
                    "allocation": "Equal weighting",
                    "max_loss_limit": "₹15,000",
                    "target_profit": "₹5,000"
                },
                "risk_management": {
                    "stop_loss": "25% of premium paid",
                    "time_decay_management": "Monitor delta changes"
                }
            }
        else:
            parameters = {}

        return {
            "strategy_type": strategy_type,
            "confidence": min(confidence, 0.9),
            "parameters": parameters,
            "risk_assessment": {
                "volatility_suitability": "moderate_to_high" if volatility in ["MODERATE", "HIGH"] else "low",
                "trend_alignment": "favorable" if trend_direction == "UP" else "neutral",
                "momentum_strength": "strong" if rsi_val < 40 else "moderate"
            },
            "position_sizing": parameters.get("position_sizing", {}),
            "entry_conditions": {
                "technical_filters": [f"RSI < {rsi_val + 5}", f"Trend: {trend_direction}"],
                "timing": "Enter on next bullish candle" if rsi_val < 40 else "Enter on retracement"
            },
            "exit_strategy": {
                "profit_taking": "Scale out 50% at 50% target, 50% at full target",
                "loss_management": "Cut losses at 25% of max loss",
                "time_based": "Close position 3 days before expiry"
            }
        }

    def _generate_trader_reasoning(self, symbol: str, current_price: float, rsi_val: float,
                                  trend_direction: str, adx_val: float, volatility: str,
                                  trading_decision: Dict) -> str:
        """Generate professional trader-style reasoning."""

        strategy = trading_decision['strategy_type']
        confidence = trading_decision['confidence']

        reasoning_parts = [
            f"As an aggressive bull trader, I'm positioning for upside momentum in {symbol} at ₹{current_price:.2f}.",
            f"Market regime: {trend_direction} trend (ADX: {adx_val:.1f}), volatility: {volatility}, RSI: {rsi_val:.1f}.",
            f"My thesis: {'Strong bullish momentum opportunity' if rsi_val < 40 else 'Favorable risk/reward setup'}.",
            f"Strategy selection: {strategy} with {confidence:.1f} confidence.",
            f"Strike positioning: {trading_decision['parameters'].get('strike_selection', {}).get('call_sell_range', 'market-appropriate')} OTM calls.",
            f"Risk management: {trading_decision['risk_assessment']['momentum_strength']} momentum, {trading_decision['risk_assessment']['trend_alignment']} trend alignment.",
            f"Position sizing: {trading_decision['position_sizing'].get('allocation', 'balanced')} with ₹{trading_decision['position_sizing'].get('max_loss_limit', '10,000')} max loss.",
            "Entry: Execute when technical filters align. Exit: Scale profits, cut losses decisively."
        ]

        return " ".join(reasoning_parts)
