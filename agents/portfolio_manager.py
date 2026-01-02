"""Portfolio Manager Agent - Final Decision Maker."""

import logging
from typing import Dict, Any
from agents.base_agent import BaseAgent
from agents.state import AgentState, SignalType, TrendSignal
from config.settings import settings

logger = logging.getLogger(__name__)


class PortfolioManagerAgent(BaseAgent):
    """Portfolio manager agent that synthesizes all agent outputs and makes final decisions."""
    
    def __init__(self):
        """Initialize portfolio manager agent."""
        super().__init__("portfolio_manager", self._get_default_prompt())
    
    def _get_default_prompt(self) -> str:
        """Get default system prompt."""
        return """You are the Portfolio Manager Agent for a Bank Nifty trading system.
Your role: Synthesize all agent analyses and make final trading decisions.
You receive inputs from technical, fundamental, sentiment, macro, bull/bear researchers, and risk agents.
Make decisions based on consensus and risk management."""
    
    def process(self, state: AgentState) -> AgentState:
        """Process portfolio management decision."""
        logger.info("Processing portfolio manager decision...")
        
        try:
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
            
            # Update state
            state.final_signal = signal
            state.trend_signal = trend_signal
            state.position_size = position_size
            state.entry_price = entry_price
            state.stop_loss = stop_loss
            state.take_profit = take_profit
            
            output = {
                "signal": signal.value,
                "trend_signal": trend_signal.value,  # BULLISH, BEARISH, or NEUTRAL
                "signal_strength": signal_strength,
                "bullish_score": bullish_score,
                "bearish_score": bearish_score,
                "position_size": position_size,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "risk_recommendation_used": "neutral",
                "volatility_factor": volatility_factor
            }
            
            explanation = f"Portfolio decision: {signal.value} ({signal_strength}), "
            explanation += f"Trend: {trend_signal.value}, "
            explanation += f"bullish_score={bullish_score:.2f}, bearish_score={bearish_score:.2f}, "
            explanation += f"position_size={position_size}, volatility_factor={volatility_factor:.2f}"
            
            self.update_state(state, output, explanation)
            
        except Exception as e:
            logger.error(f"Error in portfolio management: {e}")
            state.final_signal = SignalType.HOLD
            output = {
                "error": str(e),
                "signal": "HOLD"
            }
            self.update_state(state, output, f"Error: {e}")
        
        return state

