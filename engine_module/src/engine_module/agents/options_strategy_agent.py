"""Options Strategy Agent: Generates condor and spread strategies for Bank Nifty."""

from typing import Dict, Any, List
from engine_module.contracts import Agent, AnalysisResult, OptionsStrategy, OptionsStrategyDetails, OptionsLeg
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OptionsStrategyAgent(Agent):
    """Agent specialized in options strategies for Bank Nifty futures."""

    def __init__(self):
        self.underlying = "BANKNIFTY26JANFUT"
        self.expiry = "2026-01-30"  # January expiry

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze market conditions and generate options strategy."""
        try:
            technical = context.get('technical_indicators', {})
            current_price = context.get('current_price', 0)
            volatility = technical.get('volatility', 0.15)  # Default 15% vol

            if not current_price:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={"reason": "NO_PRICE_DATA"}
                )

            # Analyze market conditions
            trend = technical.get('trend_direction', 'SIDEWAYS')
            rsi = technical.get('rsi', 50)
            adx = technical.get('adx', 20)

            # Strategy selection logic
            if trend == 'UP' and rsi < 70:  # Bullish but not overbought
                strategy = self._create_bull_call_spread(current_price, volatility)
                confidence = 0.7
            elif trend == 'DOWN' and rsi > 30:  # Bearish but not oversold
                strategy = self._create_bear_put_spread(current_price, volatility)
                confidence = 0.7
            elif adx < 25 and abs(rsi - 50) < 20:  # Range-bound market
                strategy = self._create_iron_condor(current_price, volatility)
                confidence = 0.8
            else:
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.6,
                    details={"reason": "UNCLEAR_MARKET_CONDITIONS", "trend": trend, "rsi": rsi}
                )

            return AnalysisResult(
                decision=strategy.strategy_type.value,
                confidence=confidence,
                options_strategy=strategy,
                details={
                    "strategy": strategy.strategy_type.value,
                    "underlying": strategy.underlying,
                    "expiry": strategy.expiry,
                    "max_profit": strategy.max_profit,
                    "max_loss": strategy.max_loss,
                    "margin_required": strategy.margin_required,
                    "legs_count": len(strategy.legs)
                }
            )

        except Exception as e:
            logger.exception("Options strategy analysis failed")
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={"error": str(e)}
            )

    def _create_bull_call_spread(self, spot_price: float, volatility: float) -> OptionsStrategyDetails:
        """Create a bull call spread strategy."""
        # Strike selection: Buy ITM call, Sell OTM call
        lower_strike = round(spot_price * 0.98 / 100) * 100  # Slightly ITM
        upper_strike = round(spot_price * 1.05 / 100) * 100  # OTM

        legs = [
            OptionsLeg(
                strike_price=lower_strike,
                option_type="CE",
                position="BUY",
                quantity=1
            ),
            OptionsLeg(
                strike_price=upper_strike,
                option_type="CE",
                position="SELL",
                quantity=1
            )
        ]

        max_profit = upper_strike - lower_strike
        max_loss = lower_strike - spot_price  # Net debit paid

        return OptionsStrategyDetails(
            strategy_type=OptionsStrategy.BULL_CALL_SPREAD,
            underlying=self.underlying,
            expiry=self.expiry,
            legs=legs,
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven_points=[lower_strike + max_loss],
            risk_reward_ratio=max_profit / max_loss if max_loss > 0 else 0,
            margin_required=max_loss * 100  # Rough estimate
        )

    def _create_bear_put_spread(self, spot_price: float, volatility: float) -> OptionsStrategyDetails:
        """Create a bear put spread strategy."""
        # Strike selection: Buy OTM put, Sell ITM put
        upper_strike = round(spot_price * 1.02 / 100) * 100  # Slightly ITM
        lower_strike = round(spot_price * 0.95 / 100) * 100  # OTM

        legs = [
            OptionsLeg(
                strike_price=upper_strike,
                option_type="PE",
                position="BUY",
                quantity=1
            ),
            OptionsLeg(
                strike_price=lower_strike,
                option_type="PE",
                position="SELL",
                quantity=1
            )
        ]

        max_profit = upper_strike - lower_strike
        max_loss = spot_price - upper_strike  # Net debit paid

        return OptionsStrategyDetails(
            strategy_type=OptionsStrategy.BEAR_PUT_SPREAD,
            underlying=self.underlying,
            expiry=self.expiry,
            legs=legs,
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven_points=[upper_strike - max_loss],
            risk_reward_ratio=max_profit / max_loss if max_loss > 0 else 0,
            margin_required=max_loss * 100
        )

    def _create_iron_condor(self, spot_price: float, volatility: float) -> OptionsStrategyDetails:
        """Create an iron condor strategy (neutral condor)."""
        # Wide range for low volatility environment
        range_width = int(spot_price * 0.05)  # 5% range

        lower_put_strike = round((spot_price - range_width) / 100) * 100
        upper_put_strike = round((spot_price - range_width * 0.3) / 100) * 100
        lower_call_strike = round((spot_price + range_width * 0.3) / 100) * 100
        upper_call_strike = round((spot_price + range_width) / 100) * 100

        legs = [
            # Sell put spread
            OptionsLeg(strike_price=lower_put_strike, option_type="PE", position="SELL", quantity=1),
            OptionsLeg(strike_price=upper_put_strike, option_type="PE", position="BUY", quantity=1),
            # Sell call spread
            OptionsLeg(strike_price=lower_call_strike, option_type="CE", position="SELL", quantity=1),
            OptionsLeg(strike_price=upper_call_strike, option_type="CE", position="BUY", quantity=1)
        ]

        # Iron condor profit is the net premium received
        # Max loss is the wing width minus premium received
        wing_width = upper_put_strike - lower_put_strike
        max_loss = wing_width
        max_profit = wing_width * 0.3  # Estimate 30% of max loss as premium

        return OptionsStrategyDetails(
            strategy_type=OptionsStrategy.IRON_CONDOR,
            underlying=self.underlying,
            expiry=self.expiry,
            legs=legs,
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven_points=[lower_put_strike - max_profit, upper_call_strike + max_profit],
            risk_reward_ratio=max_profit / max_loss if max_loss > 0 else 0,
            margin_required=max_loss * 100
        )