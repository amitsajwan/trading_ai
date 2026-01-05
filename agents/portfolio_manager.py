"""Portfolio Manager Agent - Final Decision Maker."""

import logging
from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from agents.state import AgentState, SignalType, TrendSignal
from config.settings import settings

logger = logging.getLogger(__name__)


class PortfolioManagerAgent(BaseAgent):
    """Portfolio manager agent that synthesizes all agent outputs and makes final decisions."""
    
    def __init__(self):
        """Initialize portfolio manager agent."""
        super().__init__("portfolio_manager", self._get_default_prompt())

    def _llm_execution_veto(
        self,
        scenario_paths: Dict[str, Any],
        signal: SignalType,
        bullish_score: float,
        bearish_score: float,
        entry_price: float,
        environment_bias: str
    ) -> Dict[str, str]:
        """Ask LLM for a light-touch execution veto or size adjustment based on scenarios.

        Returns: {"decision": EXECUTE|REDUCE|HOLD, "reason": str}
        Fallback: EXECUTE if anything fails.
        """
        try:
            if signal != SignalType.BUY:
                return {"decision": "EXECUTE", "reason": "Non-BUY signal"}

            base_case = scenario_paths.get("base_case", {})
            bull_case = scenario_paths.get("bull_case", {})
            bear_case = scenario_paths.get("bear_case", {})

            prompt = f"""
You are the portfolio risk co-pilot. Decide if we should EXECUTE, REDUCE, or HOLD a BUY based on forward scenarios.

Inputs:
- Environment bias: {environment_bias}
- Bullish score: {bullish_score:.2f}
- Bearish score: {bearish_score:.2f}
- Planned entry price: {entry_price}

Scenario paths:
BASE: prob={base_case.get('probability', 'NA')} target15m={base_case.get('target_15m', 'NA')} target60m={base_case.get('target_60m', 'NA')}
BULL: prob={bull_case.get('probability', 'NA')} target15m={bull_case.get('target_15m', 'NA')} target60m={bull_case.get('target_60m', 'NA')}
BEAR: prob={bear_case.get('probability', 'NA')} target15m={bear_case.get('target_15m', 'NA')} target60m={bear_case.get('target_60m', 'NA')}

Rules of thumb (be concise):
- If bear prob is high (>0.45) or upside is tiny (<0.25%), prefer HOLD.
- If upside is modest (0.25%-0.60%) or bear prob is moderate (0.35-0.45), pick REDUCE.
- Otherwise EXECUTE.

Respond ONLY as JSON on one line like: {"decision": "EXECUTE", "reason": "..."}
"""

            raw = self._call_llm(prompt, temperature=0.1)
            if not raw:
                return {"decision": "EXECUTE", "reason": "LLM empty"}
            import json
            try:
                data = json.loads(raw.strip())
                decision = str(data.get("decision", "EXECUTE")).upper()
                reason = str(data.get("reason", "LLM provided"))
                if decision not in {"EXECUTE", "REDUCE", "HOLD"}:
                    decision = "EXECUTE"
                return {"decision": decision, "reason": reason}
            except Exception:
                return {"decision": "EXECUTE", "reason": "LLM parse fail"}
        except Exception as e:
            logger.debug(f"LLM veto failed: {e}")
            return {"decision": "EXECUTE", "reason": "LLM error"}
    
    def _detect_option_strategies(self, state: AgentState) -> List[Dict[str, Any]]:
        """Detect viable option strategies from chain data."""
        strategies = []
        if not state.options_chain or not state.options_chain.get("available"):
            return strategies
        
        try:
            strikes = state.options_chain.get("strikes", {})
            fut_price = state.options_chain.get("futures_price", 0)
            if not strikes or not fut_price:
                return strategies
            
            strike_list = sorted([int(s) for s in strikes.keys()])
            atm_idx = min(range(len(strike_list)), key=lambda i: abs(strike_list[i] - fut_price))
            
            # Iron Condor detection (sell ATM, buy OTM)
            if len(strike_list) >= 4 and atm_idx >= 2 and atm_idx < len(strike_list) - 2:
                sell_put_strike = strike_list[atm_idx - 1]
                buy_put_strike = strike_list[atm_idx - 2]
                sell_call_strike = strike_list[atm_idx + 1]
                buy_call_strike = strike_list[atm_idx + 2]
                
                sell_put_premium = strikes[str(sell_put_strike)].get("pe_ltp", 0)
                buy_put_premium = strikes[str(buy_put_strike)].get("pe_ltp", 0)
                sell_call_premium = strikes[str(sell_call_strike)].get("ce_ltp", 0)
                buy_call_premium = strikes[str(buy_call_strike)].get("ce_ltp", 0)
                
                net_credit = sell_put_premium + sell_call_premium - buy_put_premium - buy_call_premium
                if net_credit > 0:
                    strategies.append({
                        "type": "iron_condor",
                        "strikes": [buy_put_strike, sell_put_strike, sell_call_strike, buy_call_strike],
                        "net_credit": net_credit,
                        "confidence": 0.7 if net_credit > fut_price * 0.005 else 0.5
                    })
        except Exception as exc:
            logger.debug(f"Option strategy detection failed: {exc}")
        
        return strategies
    
    def _pre_trade_risk_check(self, signal: SignalType, position_size: int, entry_price: float) -> Dict[str, Any]:
        """Pre-trade risk validation."""
        checks = {"passed": True, "warnings": [], "errors": []}
        
        try:
            # Position size check
            if position_size <= 0:
                checks["errors"].append("Invalid position size")
                checks["passed"] = False
            
            # Price sanity check
            if entry_price <= 0:
                checks["errors"].append("Invalid entry price")
                checks["passed"] = False
            
            # Circuit breaker: max daily loss (check MongoDB for today's PnL)
            # Placeholder - implement if needed
            
        except Exception as exc:
            logger.error(f"Risk check failed: {exc}")
            checks["errors"].append(f"Risk check error: {exc}")
            checks["passed"] = False
        
        return checks
    
    def _get_default_prompt(self) -> str:
        """Get default system prompt."""
        instrument_name = settings.instrument_name
        return f"""You are the Portfolio Manager Agent for a {instrument_name} trading system.
Your role: Synthesize all agent analyses and make final trading decisions.
You receive inputs from technical, fundamental, sentiment, macro, bull/bear researchers, and risk agents.
You have access to order-flow data, options chain (if available), and detected strategy opportunities.
Make decisions based on consensus, risk management, and market microstructure."""
    
    def _generate_strategy_description(
        self, signal, signal_strength, trend_signal, bullish_score, bearish_score,
        technical, fundamental, sentiment, macro, position_size, entry_price, stop_loss, take_profit
    ) -> str:
        """Generate human-readable strategy description."""
        if signal.value == "HOLD":
            if trend_signal.value == "BULLISH":
                return "WAIT_FOR_BULLISH_ENTRY - Bullish trend but insufficient conviction. Waiting for stronger signals or better entry."
            elif trend_signal.value == "BEARISH":
                return "WAIT_FOR_BEARISH_ENTRY - Bearish trend but insufficient conviction. Waiting for stronger signals or better entry."
            else:
                return "NEUTRAL_HOLD - Mixed signals, no clear direction. Waiting for market clarity."
        
        elif signal.value == "BUY":
            trend_info = f"Trend: {trend_signal.value}"
            tech_info = f"Technical: {technical.get('trend_direction', 'UNKNOWN')}"
            strength_info = f"Strength: {signal_strength}"
            
            if signal_strength == "STRONG_BUY":
                return f"AGGRESSIVE_LONG - {strength_info}, {trend_info}, {tech_info}. High conviction entry."
            elif signal_strength == "BUY":
                return f"MODERATE_LONG - {strength_info}, {trend_info}, {tech_info}. Standard entry."
            else:  # WEAK_BUY
                return f"CAUTIOUS_LONG - {strength_info}, {trend_info}, {tech_info}. Reduced size entry."
        
        elif signal.value == "SELL":
            trend_info = f"Trend: {trend_signal.value}"
            tech_info = f"Technical: {technical.get('trend_direction', 'UNKNOWN')}"
            strength_info = f"Strength: {signal_strength}"
            
            if signal_strength == "STRONG_SELL":
                return f"AGGRESSIVE_SHORT - {strength_info}, {trend_info}, {tech_info}. High conviction entry."
            elif signal_strength == "SELL":
                return f"MODERATE_SHORT - {strength_info}, {trend_info}, {tech_info}. Standard entry."
            else:  # WEAK_SELL
                return f"CAUTIOUS_SHORT - {strength_info}, {trend_info}, {tech_info}. Reduced size entry."
        
        return "UNKNOWN_STRATEGY"
    
    def _generate_executive_summary(
        self,
        signal, signal_strength, trend_signal, bullish_score, bearish_score,
        technical: Dict[str, Any], fundamental: Dict[str, Any],
        sentiment: Dict[str, Any], macro: Dict[str, Any],
        bull_thesis: str, bear_thesis: str,
        position_size: int, entry_price: float, stop_loss: float, take_profit: float
    ) -> str:
        """Generate LLM-powered executive summary synthesizing all agent analyses."""
        try:
            instrument_name = settings.instrument_name
            current_price = entry_price  # Use entry price as current
            
            # Helper function to safely get numeric values
            def safe_num(value, default=0.0):
                """Safely convert value to number, handling None."""
                if value is None:
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default
            
            # Build comprehensive context for LLM
            prompt = f"""You are a Portfolio Manager synthesizing multi-agent trading analysis for {instrument_name}.

**Current Market Context:**
- Current Price: ${current_price:,.2f}
- Market Trend: {trend_signal.value}
- Bullish Score: {bullish_score:.2f} | Bearish Score: {bearish_score:.2f}

**Technical Analysis:**
- Trend: {technical.get('trend_direction', 'UNKNOWN')} (Strength: {safe_num(technical.get('trend_strength'), 0):.0f}%)
- RSI: {safe_num(technical.get('rsi'), 50):.1f} ({technical.get('rsi_status', 'NEUTRAL')})
- MACD: {technical.get('macd_signal', 'NEUTRAL')}
- Support: ${safe_num(technical.get('support_level'), 0):,.2f} | Resistance: ${safe_num(technical.get('resistance_level'), 0):,.2f}

**Fundamental Analysis:**
- Market Strength: {fundamental.get('market_strength', 'UNKNOWN')}
- Bullish Probability: {safe_num(fundamental.get('bullish_probability'), 0.5):.0%}
- Bearish Probability: {safe_num(fundamental.get('bearish_probability'), 0.5):.0%}

**Sentiment Analysis:**
- Retail Sentiment: {safe_num(sentiment.get('retail_sentiment'), 0.0):.2f}
- Institutional Sentiment: {safe_num(sentiment.get('institutional_sentiment'), 0.0):.2f}
- Fear & Greed Index: {int(safe_num(sentiment.get('fear_greed_index'), 50))}

**Macro Environment:**
- Regime: {macro.get('macro_regime', 'UNKNOWN')}
- Sector Headwind Score: {safe_num(macro.get('sector_headwind_score'), 0.0):.2f}

**Bull Thesis:** {bull_thesis[:200] if bull_thesis else 'Not available'}...

**Bear Thesis:** {bear_thesis[:200] if bear_thesis else 'Not available'}...

**Trading Decision:**
- Signal: {signal.value} ({signal_strength})
- Position Size: {position_size}
- Entry: ${entry_price:,.2f} | Stop Loss: ${stop_loss:,.2f} | Target: ${take_profit:,.2f}

**Your Task:**
Write a concise, actionable executive summary (3-4 sentences) that:
1. States the trading decision and conviction level
2. Highlights the 2-3 most critical factors driving this decision
3. Provides clear risk/reward context
4. Mentions any key concerns or opportunities

Write in professional trader language. Be direct and actionable. Focus on what matters most for trading decisions.

Executive Summary:"""

            # Call LLM for summary generation.
            # BaseAgent._call_llm only supports (user_message, temperature).
            # We enforce brevity via instructions + post-trim.
            response = self._call_llm(prompt, temperature=0.7)
            
            if response and len(response.strip()) > 20:
                text = response.strip()
                # Hard cap to keep UI tight even if model ignores instructions
                if len(text) > 900:
                    text = text[:900].rsplit(" ", 1)[0] + "..."
                return text
            else:
                # Fallback summary
                return f"{signal.value} signal ({signal_strength}) based on {trend_signal.value} trend. Bullish score: {bullish_score:.2f}, Bearish: {bearish_score:.2f}. Position size: {position_size}."
                
        except Exception as e:
            logger.error(f"Error generating executive summary: {e}", exc_info=True)
            # Fallback to simple summary
            return f"{signal.value} ({signal_strength}) - {trend_signal.value} trend. Bull/Bear: {bullish_score:.2f}/{bearish_score:.2f}"
    
    def _create_adaptive_strategy(
        self,
        signal, signal_strength, trend_signal, bullish_score, bearish_score,
        technical, fundamental, sentiment, macro,
        position_size, entry_price, stop_loss, take_profit,
        volatility_factor, state
    ) -> Dict[str, Any]:
        """Create comprehensive adaptive strategy with entry/exit conditions."""
        from datetime import datetime, timedelta
        
        # Determine market regime
        macro_regime = macro.get("macro_regime", "MIXED")
        trend_direction = technical.get("trend_direction", "SIDEWAYS")
        
        # Create entry conditions
        entry_conditions = []
        if signal.value != "HOLD":
            # Price-based conditions
            if signal.value == "BUY":
                entry_conditions.append({
                    "type": "price_above",
                    "value": entry_price * 0.995,  # 0.5% below entry
                    "timeframe": "1min"
                })
                entry_conditions.append({
                    "type": "price_below",
                    "value": entry_price * 1.005,  # 0.5% above entry
                    "timeframe": "1min"
                })
            elif signal.value == "SELL":
                entry_conditions.append({
                    "type": "price_below",
                    "value": entry_price * 1.005,
                    "timeframe": "1min"
                })
                entry_conditions.append({
                    "type": "price_above",
                    "value": entry_price * 0.995,
                    "timeframe": "1min"
                })
            
            # Technical conditions
            rsi = technical.get("rsi")
            if rsi:
                if signal.value == "BUY":
                    entry_conditions.append({
                        "type": "rsi_between",
                        "min": 40,
                        "max": 70,
                        "timeframe": "5min"
                    })
                elif signal.value == "SELL":
                    entry_conditions.append({
                        "type": "rsi_between",
                        "min": 30,
                        "max": 60,
                        "timeframe": "5min"
                    })
            
            # Multi-timeframe confluence
            entry_conditions.append({
                "type": "multi_timeframe_confluence",
                "timeframes": ["5min", "15min"],
                "condition": f"both_trending_{trend_direction.lower()}"
            })
        
        # Create adaptive rules
        adaptive_rules = []
        
        # Regime change detection
        adaptive_rules.append({
            "trigger": "regime_transition_detected",
            "action": "reduce_position_size",
            "new_size_pct": 0.5,
            "description": "Reduce position size if market regime changes"
        })
        
        # Volume spike
        adaptive_rules.append({
            "trigger": "volume_spike",
            "action": "increase_conviction",
            "confidence_boost": 0.1,
            "description": "Increase conviction on volume spikes"
        })
        
        # Stop-loss hit
        adaptive_rules.append({
            "trigger": "stop_loss_hit",
            "action": "review_entry_conditions",
            "update_frequency": "immediate",
            "description": "Review entry conditions if stop-loss hit"
        })
        
        # Multi-timeframe analysis
        multi_timeframe = {
            "1min": {
                "trend": technical.get("trend_direction", "SIDEWAYS"),
                "strength": technical.get("trend_strength", 0) / 100,
                "use": "ENTRY_TIMING"
            },
            "5min": {
                "trend": technical.get("trend_direction", "SIDEWAYS"),
                "strength": technical.get("trend_strength", 0) / 100,
                "use": "SHORT_TERM"
            },
            "15min": {
                "trend": technical.get("trend_direction", "SIDEWAYS"),
                "strength": technical.get("trend_strength", 0) / 100,
                "use": "MEDIUM_TERM"
            }
        }
        
        strategy = {
            "strategy_id": f"adaptive_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "type": "ADAPTIVE",
            "market_regime": {
                "current": macro_regime,
                "confidence": (bullish_score + bearish_score) / 2,
                "trend": trend_direction
            },
            "multi_timeframe_analysis": multi_timeframe,
            "entry_conditions": entry_conditions,
            "exit_conditions": {
                "stop_loss": stop_loss,
                "take_profit": [take_profit],
                "trailing_stop": False
            },
            "position_sizing": {
                "base_size": position_size,
                "risk_pct": abs((entry_price - stop_loss) / entry_price * 100) if entry_price > 0 else 2.0,
                "max_positions": 2
            },
            "adaptive_rules": adaptive_rules,
            "agent_reasoning": {
                "bullish_score": bullish_score,
                "bearish_score": bearish_score,
                "confidence": (bullish_score + bearish_score) / 2,
                "key_factors": self._extract_key_factors(technical, fundamental, sentiment, macro),
                "signal_strength": signal_strength
            }
        }
        
        return strategy
    
    def _generate_scenario_paths(
        self,
        current_price: float,
        technical: Dict[str, Any],
        fundamental: Dict[str, Any],
        sentiment: Dict[str, Any],
        macro: Dict[str, Any],
        bull_thesis: str,
        bear_thesis: str,
        bull_confidence: float,
        bear_confidence: float
    ) -> Dict[str, Any]:
        """Generate base/bull/bear scenario paths for next 15-60 minutes."""
        # Get key technical levels
        support = technical.get("support_level", current_price * 0.98)
        resistance = technical.get("resistance_level", current_price * 1.02)
        atr = technical.get("atr", current_price * 0.01)
        
        # Base case: most likely path based on current trend
        trend = technical.get("trend_direction", "SIDEWAYS")
        if trend == "UP":
            base_target = current_price * 1.005  # +0.5%
            base_probability = 0.5
        elif trend == "DOWN":
            base_target = current_price * 0.995  # -0.5%
            base_probability = 0.5
        else:
            base_target = current_price  # Sideways
            base_probability = 0.6
        
        # Bull case: optimistic scenario
        bull_target_15m = min(resistance, current_price * 1.01)  # 1% or resistance
        bull_target_60m = resistance * 1.005  # Slightly above resistance
        bull_probability = bull_confidence * 0.8  # Conservative estimate
        
        # Bear case: pessimistic scenario
        bear_target_15m = max(support, current_price * 0.99)  # -1% or support
        bear_target_60m = support * 0.995  # Slightly below support
        bear_probability = bear_confidence * 0.8  # Conservative estimate
        
        return {
            "base_case": {
                "scenario": "Base Case",
                "description": f"Continuation of {trend} trend",
                "target_15m": round(base_target, 2),
                "target_60m": round(base_target * (1.01 if trend == "UP" else 0.99 if trend == "DOWN" else 1.0), 2),
                "probability": round(base_probability, 2),
                "key_levels": [round(current_price, 2), round(base_target, 2)],
                "catalysts": [f"{trend} technical trend", "Current momentum"]
            },
            "bull_case": {
                "scenario": "Bull Case",
                "description": bull_thesis[:150] if bull_thesis else "Bullish breakout scenario",
                "target_15m": round(bull_target_15m, 2),
                "target_60m": round(bull_target_60m, 2),
                "probability": round(bull_probability, 2),
                "key_levels": [round(current_price, 2), round(resistance, 2), round(bull_target_60m, 2)],
                "catalysts": fundamental.get("key_catalysts", [])[:2] or ["Bullish momentum", "Positive sentiment"]
            },
            "bear_case": {
                "scenario": "Bear Case",
                "description": bear_thesis[:150] if bear_thesis else "Bearish breakdown scenario",
                "target_15m": round(bear_target_15m, 2),
                "target_60m": round(bear_target_60m, 2),
                "probability": round(bear_probability, 2),
                "key_levels": [round(current_price, 2), round(support, 2), round(bear_target_60m, 2)],
                "catalysts": fundamental.get("key_risk_factors", [])[:2] or ["Bearish pressure", "Negative sentiment"]
            },
            "volatility_range": {
                "atr": round(atr, 2),
                "expected_range_15m": [round(current_price - atr * 0.5, 2), round(current_price + atr * 0.5, 2)],
                "expected_range_60m": [round(current_price - atr * 1.5, 2), round(current_price + atr * 1.5, 2)]
            }
        }
    
    def _extract_key_factors(
        self,
        technical: Dict[str, Any],
        fundamental: Dict[str, Any],
        sentiment: Dict[str, Any],
        macro: Dict[str, Any]
    ) -> List[str]:
        """Extract key factors from agent analyses."""
        factors = []
        
        # Technical factors
        trend = technical.get("trend_direction")
        if trend and trend != "SIDEWAYS":
            factors.append(f"Strong {trend} trend")
        
        rsi_status = technical.get("rsi_status")
        if rsi_status and rsi_status != "NEUTRAL":
            factors.append(f"RSI {rsi_status}")
        
        # Fundamental factors
        sector_strength = fundamental.get("sector_strength")
        if sector_strength:
            factors.append(f"{sector_strength} sector strength")
        
        # Sentiment factors
        retail_sentiment = sentiment.get("retail_sentiment", 0)
        if abs(retail_sentiment) > 0.3:
            factors.append(f"Strong {'positive' if retail_sentiment > 0 else 'negative'} sentiment")
        
        # Macro factors
        macro_regime = macro.get("macro_regime")
        if macro_regime:
            factors.append(f"{macro_regime} macro regime")
        
        return factors[:5]  # Top 5 factors
    
    def process(self, state: AgentState) -> AgentState:
        """Process portfolio management decision."""
        logger.info("Processing portfolio manager decision...")
        
        try:            # Detect option strategies if chain available
            detected_strats = self._detect_option_strategies(state)
            state.detected_strategies = detected_strats
            if detected_strats:
                logger.info(f"Detected {len(detected_strats)} option strategies")
                        # Gather all inputs
            technical = state.technical_analysis
            fundamental = state.fundamental_analysis
            sentiment = state.sentiment_analysis
            macro = state.macro_analysis
            
            bull_confidence = state.bull_confidence
            bear_confidence = state.bear_confidence
            
            aggressive_risk = state.aggressive_risk_recommendation
            conservative_risk = state.conservative_risk_recommendation
            neutral_risk = state.neutral_risk_recommendation
            
            current_price = state.current_price
            
            # Calculate bullish/bearish scores
            bullish_score = 0.0
            bearish_score = 0.0
            
            # Technical analysis contribution (30% weight)
            if technical.get("trend_direction") == "UP":
                bullish_score += 0.3 * (technical.get("trend_strength", 50) / 100)
            elif technical.get("trend_direction") == "DOWN":
                bearish_score += 0.3 * (technical.get("trend_strength", 50) / 100)
            
            # Fundamental analysis contribution (25% weight)
            bullish_score += 0.25 * fundamental.get("bullish_probability", 0.5)
            bearish_score += 0.25 * fundamental.get("bearish_probability", 0.5)
            
            # Sentiment analysis contribution (15% weight)
            retail_sentiment = sentiment.get("retail_sentiment", 0.0)
            if retail_sentiment > 0:
                bullish_score += 0.15 * retail_sentiment
            else:
                bearish_score += 0.15 * abs(retail_sentiment)
            
            # Macro analysis contribution (15% weight)
            headwind_score = macro.get("sector_headwind_score", 0.0)
            if headwind_score > 0:
                bullish_score += 0.15 * headwind_score
            else:
                bearish_score += 0.15 * abs(headwind_score)
            
            # Bull/Bear debate contribution (15% weight)
            bullish_score += 0.15 * bull_confidence
            bearish_score += 0.15 * bear_confidence
            
            # Calculate trend signal based on bullish/bearish scores
            # Trend signal is independent of trading signal - it shows overall market direction
            trend_signal = TrendSignal.NEUTRAL
            trend_threshold = 0.15  # Minimum difference to determine trend
            
            if bullish_score - bearish_score > trend_threshold:
                trend_signal = TrendSignal.BULLISH
            elif bearish_score - bullish_score > trend_threshold:
                trend_signal = TrendSignal.BEARISH
            else:
                trend_signal = TrendSignal.NEUTRAL

            # Derive an overall environment bias combining
            # multi-agent scores for the next 15 minutes.
            if bullish_score - bearish_score > 0.05:
                environment_bias = "BULLISH"
            elif bearish_score - bullish_score > 0.05:
                environment_bias = "BEARISH"
            else:
                environment_bias = "NEUTRAL"
            
            # Decision logic with adaptive thresholds and tiered signals
            signal = SignalType.HOLD
            position_size = 0
            entry_price = current_price
            stop_loss = current_price
            take_profit = current_price
            signal_strength = "NEUTRAL"
            
            # Use neutral risk recommendation by default
            risk_rec = neutral_risk if neutral_risk else aggressive_risk
            
            # Calculate volatility for adaptive thresholds (using ATR if available)
            volatility_factor = 1.0
            if technical.get("atr"):
                # Higher volatility = higher thresholds (more conservative)
                atr_pct = (technical.get("atr", 0) / current_price) * 100 if current_price > 0 else 0
                if atr_pct > 2.0:  # High volatility (>2% ATR)
                    volatility_factor = 1.15  # Increase thresholds by 15%
                elif atr_pct < 0.5:  # Low volatility (<0.5% ATR)
                    volatility_factor = 0.9  # Decrease thresholds by 10%
            
            # Adaptive thresholds based on volatility
            strong_threshold = 0.70 * volatility_factor
            moderate_threshold = 0.60 * volatility_factor
            weak_threshold = 0.55 * volatility_factor
            opposite_threshold = 0.35 / volatility_factor  # Inverse relationship
            
            # Tiered signal generation
            if bullish_score > strong_threshold and bearish_score < opposite_threshold:
                signal = SignalType.BUY
                signal_strength = "STRONG_BUY"
                position_size = risk_rec.get("position_size", 0)
                stop_loss = risk_rec.get("stop_loss_price", current_price * 0.985)
                take_profit = current_price * 1.03  # 3% target
                
            elif bullish_score > moderate_threshold and bearish_score < (1 - moderate_threshold):
                signal = SignalType.BUY
                signal_strength = "BUY"
                position_size = risk_rec.get("position_size", 0)
                stop_loss = risk_rec.get("stop_loss_price", current_price * 0.985)
                take_profit = current_price * 1.03  # 3% target
                
            elif bullish_score > weak_threshold and bearish_score < (1 - weak_threshold):
                signal = SignalType.BUY
                signal_strength = "WEAK_BUY"
                # Reduce position size for weak signals
                position_size = int(risk_rec.get("position_size", 0) * 0.7)
                stop_loss = risk_rec.get("stop_loss_price", current_price * 0.985)
                take_profit = current_price * 1.02  # 2% target (more conservative)
                
            elif bearish_score > strong_threshold and bullish_score < opposite_threshold:
                signal = SignalType.SELL
                signal_strength = "STRONG_SELL"
                position_size = risk_rec.get("position_size", 0)
                stop_loss = risk_rec.get("stop_loss_price", current_price * 1.015)
                take_profit = current_price * 0.97  # 3% target
                
            elif bearish_score > moderate_threshold and bullish_score < (1 - moderate_threshold):
                signal = SignalType.SELL
                signal_strength = "SELL"
                position_size = risk_rec.get("position_size", 0)
                stop_loss = risk_rec.get("stop_loss_price", current_price * 1.015)
                take_profit = current_price * 0.97  # 3% target
                
            elif bearish_score > weak_threshold and bullish_score < (1 - weak_threshold):
                signal = SignalType.SELL
                signal_strength = "WEAK_SELL"
                # Reduce position size for weak signals
                position_size = int(risk_rec.get("position_size", 0) * 0.7)
                stop_loss = risk_rec.get("stop_loss_price", current_price * 1.015)
                take_profit = current_price * 0.98  # 2% target (more conservative)
            
            # Generate scenario paths (base/bull/bear)
            scenario_paths = self._generate_scenario_paths(
                current_price, technical, fundamental, sentiment, macro,
                state.bull_thesis, state.bear_thesis,
                state.bull_confidence, state.bear_confidence
            )
            
            # Scenario-aware gating (LLM-first, then deterministic backstop)
            gating_reasons = []
            try:
                if signal == SignalType.BUY and scenario_paths:
                    # LLM veto head: EXECUTE / REDUCE / HOLD
                    veto = self._llm_execution_veto(
                        scenario_paths,
                        signal,
                        bullish_score,
                        bearish_score,
                        entry_price,
                        environment_bias
                    )
                    decision = veto.get("decision", "EXECUTE")
                    reason = veto.get("reason", "")
                    if decision == "HOLD":
                        gating_reasons.append(f"LLM veto -> HOLD: {reason}")
                        signal = SignalType.HOLD
                        signal_strength = "FILTERED_HOLD"
                        position_size = 0
                    elif decision == "REDUCE":
                        gating_reasons.append(f"LLM veto -> REDUCE: {reason}")
                        position_size = int(position_size * 0.5)
                        signal_strength = f"REDUCED_{signal_strength}"

                    # Deterministic backstop (safety net)
                    bear_case = scenario_paths.get("bear_case") or {}
                    bull_case = scenario_paths.get("bull_case") or {}
                    bear_prob = float(bear_case.get("probability") or 0.0)
                    bull_target_15m = bull_case.get("target_15m")

                    bear_prob_threshold = 0.45   # stricter than before
                    min_bull_upside_pct = 0.0025  # 0.25%

                    if bear_prob > bear_prob_threshold:
                        gating_reasons.append(
                            f"Backstop HOLD: bear_case.probability={bear_prob:.2f} > {bear_prob_threshold:.2f}"
                        )
                        signal = SignalType.HOLD
                        signal_strength = "FILTERED_HOLD"
                        position_size = 0

                    if signal == SignalType.BUY and bull_target_15m is not None and entry_price:
                        try:
                            upside_pct = (float(bull_target_15m) - float(entry_price)) / float(entry_price)
                            if upside_pct < min_bull_upside_pct:
                                gating_reasons.append(
                                    f"Backstop HOLD: bull_case 15m upside={upside_pct:.4f} < {min_bull_upside_pct:.4f}"
                                )
                                signal = SignalType.HOLD
                                signal_strength = "FILTERED_HOLD"
                                position_size = 0
                        except Exception:
                            pass
            except Exception as e:
                logger.debug(f"Scenario gating failed, ignoring gating step: {e}")

            # Update state with (potentially gated) decision
            state.final_signal = signal
            state.trend_signal = trend_signal
            state.position_size = position_size
            state.entry_price = entry_price
            state.stop_loss = stop_loss
            state.take_profit = take_profit
            
            # Generate strategy description
            strategy_description = self._generate_strategy_description(
                signal, signal_strength, trend_signal, bullish_score, bearish_score,
                technical, fundamental, sentiment, macro, position_size, entry_price, stop_loss, take_profit
            )
            
            # Create comprehensive adaptive strategy
            adaptive_strategy = self._create_adaptive_strategy(
                signal, signal_strength, trend_signal, bullish_score, bearish_score,
                technical, fundamental, sentiment, macro,
                position_size, entry_price, stop_loss, take_profit,
                volatility_factor, state
            )
            
            output = {
                "signal": signal.value,
                "trend_signal": trend_signal.value,  # BULLISH, BEARISH, or NEUTRAL
                "signal_strength": signal_strength,
                "strategy": strategy_description,
                "adaptive_strategy": adaptive_strategy,  # Comprehensive strategy for execution
                "scenario_paths": scenario_paths,  # Base/bull/bear future scenarios
                "gating_reasons": gating_reasons,
                "bullish_score": bullish_score,
                "bearish_score": bearish_score,
                 "environment_bias": environment_bias,
                 "time_horizon": "INTRADAY_15M",
                "position_size": position_size,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "risk_recommendation_used": "neutral",
                "volatility_factor": volatility_factor
            }

            # Persist full PM output in a "real" state field so it survives LangGraph reductions/copies.
            # This is later stored to MongoDB and used by the dashboard/history views.
            try:
                state.decision_audit_trail["portfolio_manager_output"] = dict(output)
            except Exception:
                pass
            
            # Build human-readable explanation with points and reasoning
            points = [
                ("Decision", f"{signal.value} ({signal_strength})",
                 f"Final trading decision based on multi-agent consensus"),
                ("Strategy", strategy_description,
                 f"Trading strategy and approach"),
                ("Market Trend", trend_signal.value,
                 f"Overall market trend assessment"),
                ("Bullish Score", f"{bullish_score:.2f}",
                 f"Aggregated bullish factors from all agents"),
                ("Bearish Score", f"{bearish_score:.2f}",
                 f"Aggregated bearish factors from all agents"),
                ("Position Size", f"{position_size}",
                 f"Recommended position size (0 = no position)"),
                ("Volatility Factor", f"{volatility_factor:.2f}",
                 f"Volatility adjustment factor for risk management")
            ]
            
            if position_size > 0:
                points.extend([
                    ("Entry Price", f"{entry_price:.2f}",
                     f"Recommended entry price level"),
                    ("Stop Loss", f"{stop_loss:.2f} ({abs((stop_loss/entry_price - 1) * 100):.2f}%)",
                     f"Stop loss level to limit downside"),
                    ("Take Profit", f"{take_profit:.2f} ({abs((take_profit/entry_price - 1) * 100):.2f}%)",
                     f"Take profit target level")
                ])
            
            summary = f"Portfolio Decision: {signal.value} ({signal_strength}) - {strategy_description}"
            
            explanation = self.format_explanation("Portfolio Manager", points, summary)
            self.update_state(state, output, explanation)
            
            # Generate LLM-powered executive summary
            try:
                executive_summary = self._generate_executive_summary(
                    signal, signal_strength, trend_signal, bullish_score, bearish_score,
                    technical, fundamental, sentiment, macro,
                    state.bull_thesis, state.bear_thesis,
                    position_size, entry_price, stop_loss, take_profit
                )
                output["executive_summary"] = executive_summary
                state.update_agent_output(self.agent_name, output)  # Update with summary
                try:
                    state.decision_audit_trail["executive_summary"] = executive_summary
                    state.decision_audit_trail["portfolio_manager_output"] = dict(output)
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Could not generate executive summary: {e}")
                # Fallback to simple summary
                output["executive_summary"] = summary
                state.update_agent_output(self.agent_name, output)
                try:
                    state.decision_audit_trail["executive_summary"] = summary
                    state.decision_audit_trail["portfolio_manager_output"] = dict(output)
                except Exception:
                    pass
            
        except Exception as e:
            logger.error(f"Error in portfolio management: {e}")
            state.final_signal = SignalType.HOLD
            output = {
                "error": str(e),
                "signal": "HOLD"
            }
            self.update_state(state, output, f"Error: {e}")
        
        return state

