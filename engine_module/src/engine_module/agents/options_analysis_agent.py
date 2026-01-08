"""Options Analysis Agent - Analyzes options chain data for trading strategies.

This agent specializes in:
- Options chain analysis (OI, volume, PCR)
- Greeks analysis (delta, gamma, vega, theta)
- IV analysis and skew
- Max pain calculation
- Recommending specific multi-leg strategies
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class OptionsLeg:
    """Represents one leg of an options strategy."""
    side: str  # BUY or SELL
    option_type: str  # CE or PE
    strike: float
    premium: float
    quantity: int
    oi: Optional[int] = None
    iv: Optional[float] = None
    delta: Optional[float] = None


@dataclass
class OptionsStrategy:
    """Complete options strategy recommendation."""
    strategy_name: str  # e.g., "Iron Condor", "Bull Call Spread"
    legs: List[OptionsLeg]
    net_debit_credit: float  # Positive = debit, Negative = credit
    max_profit: float
    max_loss: float
    breakeven: List[float]
    reasoning: str
    confidence: float


class OptionsAnalysisAgent(Agent):
    """Agent that analyzes options chain data and recommends multi-leg strategies."""

    def __init__(self):
        """Initialize options analysis agent."""
        self._agent_name = "OptionsAnalysisAgent"

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze options chain and recommend strategy.

        Expected context keys:
        - 'calls': list of call options with strike, premium, oi, iv, delta
        - 'puts': list of put options with strike, premium, oi, iv, delta  
        - 'underlying_price': current spot price
        - 'pcr': Put-Call Ratio
        - 'max_pain': max pain strike
        - 'consensus_direction': BUY/SELL/HOLD from other agents
        """
        calls = context.get("calls", [])
        puts = context.get("puts", [])
        underlying_price = context.get("underlying_price")
        pcr = context.get("pcr", 1.0)
        max_pain = context.get("max_pain")
        consensus = context.get("consensus_direction", "HOLD")

        if not calls or not puts or not underlying_price:
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={
                    "note": "INSUFFICIENT_OPTIONS_DATA",
                    "strategy": None
                }
            )

        # Analyze options chain
        analysis = self._analyze_options_chain(calls, puts, underlying_price, pcr, max_pain)
        
        # Recommend strategy based on consensus and options analysis
        strategy = self._recommend_strategy(
            consensus=consensus,
            analysis=analysis,
            calls=calls,
            puts=puts,
            underlying_price=underlying_price
        )

        if not strategy:
            return AnalysisResult(
                decision="HOLD",
                confidence=0.3,
                details={
                    **analysis,
                    "strategy": None,
                    "note": "NO_SUITABLE_STRATEGY"
                }
            )

        # Convert strategy to decision
        decision = self._strategy_to_decision(strategy.strategy_name)

        details = {
            **analysis,
            "strategy_name": strategy.strategy_name,
            "legs": [
                {
                    "side": leg.side,
                    "option_type": leg.option_type,
                    "strike": leg.strike,
                    "premium": leg.premium,
                    "quantity": leg.quantity,
                    "oi": leg.oi,
                    "iv": leg.iv,
                    "delta": leg.delta
                }
                for leg in strategy.legs
            ],
            "net_debit_credit": strategy.net_debit_credit,
            "max_profit": strategy.max_profit,
            "max_loss": strategy.max_loss,
            "breakeven": strategy.breakeven,
            "reasoning": strategy.reasoning
        }

        return AnalysisResult(
            decision=decision,
            confidence=strategy.confidence,
            details=details
        )

    def _analyze_options_chain(self, calls: List[Dict], puts: List[Dict],
                               underlying_price: float, pcr: float,
                               max_pain: Optional[float]) -> Dict[str, Any]:
        """Analyze options chain metrics."""
        analysis = {}

        # Find ATM strike
        atm_strike = self._find_atm_strike(calls, puts, underlying_price)
        analysis["atm_strike"] = atm_strike

        # Analyze OI distribution
        call_oi_total = sum(c.get("oi", 0) for c in calls)
        put_oi_total = sum(p.get("oi", 0) for p in puts)
        analysis["call_oi_total"] = call_oi_total
        analysis["put_oi_total"] = put_oi_total
        analysis["pcr"] = pcr

        # Find max OI strikes
        max_call_oi_strike = max(calls, key=lambda x: x.get("oi", 0), default={}).get("strike")
        max_put_oi_strike = max(puts, key=lambda x: x.get("oi", 0), default={}).get("strike")
        analysis["max_call_oi_strike"] = max_call_oi_strike
        analysis["max_put_oi_strike"] = max_put_oi_strike

        # PCR interpretation
        if pcr > 1.3:
            analysis["pcr_signal"] = "BULLISH"  # More puts = bullish
        elif pcr < 0.7:
            analysis["pcr_signal"] = "BEARISH"  # More calls = bearish
        else:
            analysis["pcr_signal"] = "NEUTRAL"

        # Max pain analysis
        if max_pain:
            analysis["max_pain"] = max_pain
            distance_from_max_pain = abs(underlying_price - max_pain) / underlying_price
            analysis["max_pain_distance_pct"] = distance_from_max_pain * 100
            
            if distance_from_max_pain < 0.005:  # Within 0.5%
                analysis["max_pain_signal"] = "RANGE_BOUND"
            elif underlying_price > max_pain:
                analysis["max_pain_signal"] = "ABOVE_MAX_PAIN_BULLISH"
            else:
                analysis["max_pain_signal"] = "BELOW_MAX_PAIN_BEARISH"

        # IV analysis (if available)
        call_ivs = [c.get("iv") for c in calls if c.get("iv")]
        put_ivs = [p.get("iv") for p in puts if p.get("iv")]
        
        if call_ivs:
            avg_call_iv = sum(call_ivs) / len(call_ivs)
            analysis["avg_call_iv"] = avg_call_iv
        if put_ivs:
            avg_put_iv = sum(put_ivs) / len(put_ivs)
            analysis["avg_put_iv"] = avg_put_iv

        # IV skew
        if call_ivs and put_ivs:
            iv_skew = (sum(put_ivs) / len(put_ivs)) - (sum(call_ivs) / len(call_ivs))
            analysis["iv_skew"] = iv_skew
            if iv_skew > 5:
                analysis["iv_skew_signal"] = "PUT_SKEW_BEARISH"
            elif iv_skew < -5:
                analysis["iv_skew_signal"] = "CALL_SKEW_BULLISH"
            else:
                analysis["iv_skew_signal"] = "BALANCED"

        return analysis

    def _find_atm_strike(self, calls: List[Dict], puts: List[Dict], spot: float) -> Optional[float]:
        """Find ATM strike closest to spot price."""
        all_strikes = set()
        for c in calls:
            if c.get("strike"):
                all_strikes.add(c["strike"])
        for p in puts:
            if p.get("strike"):
                all_strikes.add(p["strike"])
        
        if not all_strikes:
            return None
            
        return min(all_strikes, key=lambda x: abs(x - spot))

    def _recommend_strategy(self, consensus: str, analysis: Dict[str, Any],
                           calls: List[Dict], puts: List[Dict],
                           underlying_price: float) -> Optional[OptionsStrategy]:
        """Recommend specific multi-leg options strategy."""
        
        pcr_signal = analysis.get("pcr_signal", "NEUTRAL")
        max_pain_signal = analysis.get("max_pain_signal", "RANGE_BOUND")
        atm_strike = analysis.get("atm_strike", underlying_price)

        # Strategy selection logic
        if consensus == "BUY" and pcr_signal == "BULLISH":
            return self._build_bull_call_spread(calls, atm_strike)
        
        elif consensus == "SELL" and pcr_signal == "BEARISH":
            return self._build_bear_put_spread(puts, atm_strike)
        
        elif consensus == "HOLD" and max_pain_signal == "RANGE_BOUND":
            return self._build_iron_condor(calls, puts, atm_strike, underlying_price)
        
        elif pcr_signal == "NEUTRAL" and max_pain_signal == "RANGE_BOUND":
            return self._build_short_straddle(calls, puts, atm_strike)
        
        else:
            # Default to bull call spread if bullish, bear put if bearish
            if consensus == "BUY":
                return self._build_bull_call_spread(calls, atm_strike)
            elif consensus == "SELL":
                return self._build_bear_put_spread(puts, atm_strike)
        
        return None

    def _build_bull_call_spread(self, calls: List[Dict], atm_strike: float) -> Optional[OptionsStrategy]:
        """Build a bull call spread (buy lower strike, sell higher strike)."""
        # Find ATM and OTM strikes
        atm_call = next((c for c in calls if c.get("strike") == atm_strike), None)
        if not atm_call or not atm_call.get("price"):
            return None

        # Find next higher strike for short leg
        higher_strikes = [c for c in calls if c.get("strike", 0) > atm_strike and c.get("price")]
        if not higher_strikes:
            return None
        
        otm_call = min(higher_strikes, key=lambda x: x["strike"])

        buy_leg = OptionsLeg(
            side="BUY",
            option_type="CE",
            strike=atm_call["strike"],
            premium=atm_call["price"],
            quantity=25,  # BANKNIFTY lot size
            oi=atm_call.get("oi"),
            iv=atm_call.get("iv"),
            delta=atm_call.get("delta")
        )

        sell_leg = OptionsLeg(
            side="SELL",
            option_type="CE",
            strike=otm_call["strike"],
            premium=otm_call["price"],
            quantity=25,
            oi=otm_call.get("oi"),
            iv=otm_call.get("iv"),
            delta=otm_call.get("delta")
        )

        net_debit = (buy_leg.premium - sell_leg.premium) * buy_leg.quantity
        max_profit = (sell_leg.strike - buy_leg.strike - (buy_leg.premium - sell_leg.premium)) * buy_leg.quantity
        max_loss = net_debit
        breakeven = buy_leg.strike + (buy_leg.premium - sell_leg.premium)

        return OptionsStrategy(
            strategy_name="Bull Call Spread",
            legs=[buy_leg, sell_leg],
            net_debit_credit=net_debit,
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=[breakeven],
            reasoning=f"Bullish outlook: Buy {buy_leg.strike} CE, Sell {sell_leg.strike} CE. "
                     f"Net debit: ₹{net_debit:.2f}, Max profit: ₹{max_profit:.2f}",
            confidence=0.75
        )

    def _build_bear_put_spread(self, puts: List[Dict], atm_strike: float) -> Optional[OptionsStrategy]:
        """Build a bear put spread (buy higher strike, sell lower strike)."""
        atm_put = next((p for p in puts if p.get("strike") == atm_strike), None)
        if not atm_put or not atm_put.get("price"):
            return None

        # Find next lower strike for short leg
        lower_strikes = [p for p in puts if p.get("strike", 0) < atm_strike and p.get("price")]
        if not lower_strikes:
            return None
        
        otm_put = max(lower_strikes, key=lambda x: x["strike"])

        buy_leg = OptionsLeg(
            side="BUY",
            option_type="PE",
            strike=atm_put["strike"],
            premium=atm_put["price"],
            quantity=25,
            oi=atm_put.get("oi"),
            iv=atm_put.get("iv"),
            delta=atm_put.get("delta")
        )

        sell_leg = OptionsLeg(
            side="SELL",
            option_type="PE",
            strike=otm_put["strike"],
            premium=otm_put["price"],
            quantity=25,
            oi=otm_put.get("oi"),
            iv=otm_put.get("iv"),
            delta=otm_put.get("delta")
        )

        net_debit = (buy_leg.premium - sell_leg.premium) * buy_leg.quantity
        max_profit = (buy_leg.strike - sell_leg.strike - (buy_leg.premium - sell_leg.premium)) * buy_leg.quantity
        max_loss = net_debit
        breakeven = buy_leg.strike - (buy_leg.premium - sell_leg.premium)

        return OptionsStrategy(
            strategy_name="Bear Put Spread",
            legs=[buy_leg, sell_leg],
            net_debit_credit=net_debit,
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=[breakeven],
            reasoning=f"Bearish outlook: Buy {buy_leg.strike} PE, Sell {sell_leg.strike} PE. "
                     f"Net debit: ₹{net_debit:.2f}, Max profit: ₹{max_profit:.2f}",
            confidence=0.75
        )

    def _build_iron_condor(self, calls: List[Dict], puts: List[Dict],
                          atm_strike: float, spot: float) -> Optional[OptionsStrategy]:
        """Build an iron condor (sell OTM call spread + sell OTM put spread)."""
        # Find OTM strikes for both sides
        otm_calls = [c for c in calls if c.get("strike", 0) > spot * 1.01 and c.get("price")]
        otm_puts = [p for p in puts if p.get("strike", 0) < spot * 0.99 and p.get("price")]

        if len(otm_calls) < 2 or len(otm_puts) < 2:
            return None

        # Sort and pick strikes
        otm_calls_sorted = sorted(otm_calls, key=lambda x: x["strike"])
        otm_puts_sorted = sorted(otm_puts, key=lambda x: x["strike"], reverse=True)

        # Sell closer OTM, buy further OTM
        sell_call = otm_calls_sorted[0]
        buy_call = otm_calls_sorted[1]
        sell_put = otm_puts_sorted[0]
        buy_put = otm_puts_sorted[1]

        legs = [
            OptionsLeg("SELL", "CE", sell_call["strike"], sell_call["price"], 25, sell_call.get("oi")),
            OptionsLeg("BUY", "CE", buy_call["strike"], buy_call["price"], 25, buy_call.get("oi")),
            OptionsLeg("SELL", "PE", sell_put["strike"], sell_put["price"], 25, sell_put.get("oi")),
            OptionsLeg("BUY", "PE", buy_put["strike"], buy_put["price"], 25, buy_put.get("oi"))
        ]

        net_credit = ((sell_call["price"] - buy_call["price"]) + 
                     (sell_put["price"] - buy_put["price"])) * 25
        
        call_spread_width = buy_call["strike"] - sell_call["strike"]
        put_spread_width = sell_put["strike"] - buy_put["strike"]
        max_loss = max(call_spread_width, put_spread_width) * 25 - net_credit
        max_profit = net_credit

        return OptionsStrategy(
            strategy_name="Iron Condor",
            legs=legs,
            net_debit_credit=-net_credit,  # Negative = credit received
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=[sell_put["strike"] - net_credit/25, sell_call["strike"] + net_credit/25],
            reasoning=f"Range-bound market: Sell {sell_call['strike']} CE, Buy {buy_call['strike']} CE, "
                     f"Sell {sell_put['strike']} PE, Buy {buy_put['strike']} PE. Net credit: ₹{net_credit:.2f}",
            confidence=0.70
        )

    def _build_short_straddle(self, calls: List[Dict], puts: List[Dict],
                             atm_strike: float) -> Optional[OptionsStrategy]:
        """Build a short straddle (sell ATM call + ATM put)."""
        atm_call = next((c for c in calls if c.get("strike") == atm_strike and c.get("price")), None)
        atm_put = next((p for p in puts if p.get("strike") == atm_strike and p.get("price")), None)

        if not atm_call or not atm_put:
            return None

        legs = [
            OptionsLeg("SELL", "CE", atm_call["strike"], atm_call["price"], 25, atm_call.get("oi")),
            OptionsLeg("SELL", "PE", atm_put["strike"], atm_put["price"], 25, atm_put.get("oi"))
        ]

        net_credit = (atm_call["price"] + atm_put["price"]) * 25
        
        return OptionsStrategy(
            strategy_name="Short Straddle",
            legs=legs,
            net_debit_credit=-net_credit,
            max_profit=net_credit,
            max_loss=float('inf'),  # Unlimited
            breakeven=[atm_strike - (atm_call["price"] + atm_put["price"]),
                      atm_strike + (atm_call["price"] + atm_put["price"])],
            reasoning=f"Low volatility expected: Sell {atm_strike} CE + PE. Net credit: ₹{net_credit:.2f}",
            confidence=0.65
        )

    def _strategy_to_decision(self, strategy_name: str) -> str:
        """Convert strategy name to decision signal."""
        if "Bull" in strategy_name or "Call" in strategy_name:
            return "BUY"
        elif "Bear" in strategy_name or "Put" in strategy_name:
            return "SELL"
        else:
            return "HOLD"

