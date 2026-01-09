"""Enhanced Technical Agent - Interprets pre-calculated technical indicators.

This agent CONSUMES indicators from TechnicalIndicatorsService rather than
calculating them. It provides multiple analytical perspectives:
- Momentum signals
- Trend following signals  
- Volume confirmation signals
- Mean reversion signals

The agent aggregates these perspectives into a single trading decision.
"""

import logging
import sys
import os
from typing import Dict, Any, Optional
from engine_module.contracts import Agent, AnalysisResult

logger = logging.getLogger(__name__)


class EnhancedTechnicalAgent(Agent):
    """Enhanced technical agent that interprets pre-calculated indicators.
    
    This agent does NOT calculate indicators. It consumes them from
    TechnicalIndicatorsService and provides multiple analytical perspectives.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize enhanced technical agent.
        
        Args:
            config: Optional configuration for signal thresholds
        """
        self._agent_name = "EnhancedTechnicalAgent"
        self.config = config or {
            # Signal weight configuration
            "momentum_weight": 1.5,
            "trend_weight": 1.5,
            "volume_weight": 1.5,
            "mean_reversion_weight": 1.0,
            
            # Thresholds
            "strong_trend_adx": 25,
            "volume_spike_threshold": 1.5,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
        }
    
    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze market using pre-calculated technical indicators.
        
        Expected context keys:
        - 'indicators': Pre-calculated TechnicalIndicators object or dict
        - OR 'instrument': Will fetch indicators from service
        
        Returns:
            AnalysisResult with multi-perspective technical analysis
        """
        # Get indicators from context or service
        indicators = context.get("indicators")
        
        if indicators is None:
            # Try to get from technical service
            instrument = context.get("instrument", "BANKNIFTY")
            try:
                try:
                    from market_data.technical_indicators_service import get_technical_service
                except ImportError:
                    # Fallback: ensure market_data/src is in path
                    market_data_src = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'market_data', 'src'))
                    if os.path.exists(market_data_src) and market_data_src not in sys.path:
                        sys.path.insert(0, market_data_src)
                    from market_data.technical_indicators_service import get_technical_service
                tech_service = get_technical_service()
                indicators = tech_service.get_indicators_dict(instrument)
            except Exception as e:
                logger.warning(f"Could not fetch indicators from service: {e}")
                return AnalysisResult(
                    decision="HOLD",
                    confidence=0.0,
                    details={
                        "error": "NO_INDICATORS_AVAILABLE",
                        "agent": self._agent_name
                    }
                )
        
        # Convert to dict if needed
        if hasattr(indicators, 'to_dict'):
            indicators = indicators.to_dict()
        
        if not indicators or not isinstance(indicators, dict):
            return AnalysisResult(
                decision="HOLD",
                confidence=0.0,
                details={
                    "error": "INVALID_INDICATORS_FORMAT",
                    "agent": self._agent_name
                }
            )
        
        # Generate multiple perspectives
        perspectives = {
            "momentum": self._analyze_momentum(indicators),
            "trend": self._analyze_trend(indicators),
            "volume": self._analyze_volume(indicators),
            "mean_reversion": self._analyze_mean_reversion(indicators)
        }
        
        # Aggregate perspectives into final decision
        final_decision = self._aggregate_perspectives(perspectives, indicators)
        
        return AnalysisResult(
            decision=final_decision["decision"],
            confidence=final_decision["confidence"],
            details={
                "agent": self._agent_name,
                "indicators": indicators,
                "perspectives": perspectives,
                "reasoning": final_decision["reasoning"],
                "weighted_scores": final_decision["weighted_scores"]
            }
        )
    
    def _analyze_momentum(self, ind: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze momentum signals from RSI + MACD + Volume.
        
        Args:
            ind: Dictionary of technical indicators
            
        Returns:
            Momentum perspective with signal, confidence, reasoning
        """
        rsi = ind.get("rsi_14")
        macd_value = ind.get("macd_value")
        macd_signal = ind.get("macd_signal")
        volume_ratio = ind.get("volume_ratio", 1.0)
        
        # Default
        signal = "HOLD"
        confidence = 0.5
        reasons = []
        
        # RSI momentum
        if rsi is not None:
            if rsi > self.config["rsi_overbought"]:
                reasons.append(f"RSI overbought at {rsi:.1f}")
                signal = "SELL" if volume_ratio > 1.2 else "HOLD"
                confidence = min(0.85, 0.5 + (rsi - 70) / 100)
            elif rsi < self.config["rsi_oversold"]:
                reasons.append(f"RSI oversold at {rsi:.1f}")
                signal = "BUY" if volume_ratio > 1.2 else "HOLD"
                confidence = min(0.85, 0.5 + (30 - rsi) / 100)
            elif 40 < rsi < 60:
                reasons.append(f"RSI neutral at {rsi:.1f}")
            elif rsi > 60:
                reasons.append(f"RSI bullish at {rsi:.1f}")
                signal = "BUY"
                confidence = 0.65
            elif rsi < 40:
                reasons.append(f"RSI bearish at {rsi:.1f}")
                signal = "SELL"
                confidence = 0.65
        
        # MACD confirmation
        if macd_value is not None and macd_signal is not None:
            macd_diff = macd_value - macd_signal
            if macd_diff > 0 and signal != "SELL":
                reasons.append(f"MACD bullish crossover")
                signal = "BUY"
                confidence = min(0.9, confidence + 0.15)
            elif macd_diff < 0 and signal != "BUY":
                reasons.append(f"MACD bearish crossover")
                signal = "SELL"
                confidence = min(0.9, confidence + 0.15)
        
        # Volume confirmation
        if volume_ratio > self.config["volume_spike_threshold"]:
            reasons.append(f"Volume spike {volume_ratio:.2f}x average")
            confidence = min(0.95, confidence + 0.1)
        
        return {
            "signal": signal,
            "confidence": confidence,
            "reasoning": "; ".join(reasons) if reasons else "Neutral momentum",
            "rsi": rsi,
            "macd_crossover": "bullish" if macd_value and macd_signal and macd_value > macd_signal else "bearish",
            "volume_confirmation": volume_ratio > 1.2
        }
    
    def _analyze_trend(self, ind: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze trend following signals from SMA + ADX.
        
        Args:
            ind: Dictionary of technical indicators
            
        Returns:
            Trend perspective with signal, confidence, reasoning
        """
        current_price = ind.get("current_price", 0)
        sma_20 = ind.get("sma_20")
        sma_50 = ind.get("sma_50")
        adx = ind.get("adx_14")
        trend_direction = ind.get("trend_direction", "SIDEWAYS")
        trend_strength = ind.get("trend_strength", 0)
        
        signal = "HOLD"
        confidence = 0.5
        reasons = []
        
        # Trend direction from SMA
        if sma_20 and current_price:
            if current_price > sma_20:
                reasons.append(f"Price above SMA20 ({sma_20:.0f})")
                signal = "BUY"
                confidence = 0.65
            elif current_price < sma_20:
                reasons.append(f"Price below SMA20 ({sma_20:.0f})")
                signal = "SELL"
                confidence = 0.65
        
        # SMA crossover
        if sma_20 and sma_50:
            if sma_20 > sma_50:
                reasons.append("Golden cross (SMA20 > SMA50)")
                signal = "BUY"
                confidence = min(0.8, confidence + 0.15)
            elif sma_20 < sma_50:
                reasons.append("Death cross (SMA20 < SMA50)")
                signal = "SELL"
                confidence = min(0.8, confidence + 0.15)
        
        # ADX trend strength confirmation
        if adx is not None:
            if adx > self.config["strong_trend_adx"]:
                reasons.append(f"Strong trend (ADX {adx:.1f})")
                confidence = min(0.9, confidence + 0.1)
            else:
                reasons.append(f"Weak trend (ADX {adx:.1f})")
                confidence = max(0.3, confidence - 0.1)
        
        # Use trend_direction as final confirmation
        if trend_direction == "UP" and signal != "SELL":
            signal = "BUY"
        elif trend_direction == "DOWN" and signal != "BUY":
            signal = "SELL"
        
        return {
            "signal": signal,
            "confidence": confidence,
            "reasoning": "; ".join(reasons) if reasons else "No clear trend",
            "trend_direction": trend_direction,
            "trend_strength": trend_strength,
            "adx": adx
        }
    
    def _analyze_volume(self, ind: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze volume confirmation signals.
        
        Args:
            ind: Dictionary of technical indicators
            
        Returns:
            Volume perspective with signal, confidence, reasoning
        """
        volume_ratio = ind.get("volume_ratio", 1.0)
        trend_direction = ind.get("trend_direction", "SIDEWAYS")
        rsi = ind.get("rsi_14")
        
        signal = "HOLD"
        confidence = 0.5
        reasons = []
        
        # Volume spike analysis
        if volume_ratio > self.config["volume_spike_threshold"]:
            reasons.append(f"Volume spike {volume_ratio:.2f}x average")
            
            # Direction depends on trend
            if trend_direction == "UP":
                signal = "BUY"
                confidence = 0.75
                reasons.append("Volume confirms uptrend")
            elif trend_direction == "DOWN":
                signal = "SELL"
                confidence = 0.75
                reasons.append("Volume confirms downtrend")
            else:
                signal = "HOLD"
                confidence = 0.6
                reasons.append("Volume spike without clear direction")
        elif volume_ratio < 0.7:
            reasons.append(f"Low volume {volume_ratio:.2f}x average")
            confidence = 0.3
            reasons.append("Low conviction - wait for volume")
        else:
            reasons.append(f"Normal volume {volume_ratio:.2f}x average")
        
        return {
            "signal": signal,
            "confidence": confidence,
            "reasoning": "; ".join(reasons) if reasons else "Normal volume activity",
            "volume_ratio": volume_ratio,
            "volume_confirmation": volume_ratio > 1.2
        }
    
    def _analyze_mean_reversion(self, ind: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze mean reversion signals from Bollinger Bands + RSI extremes.
        
        Args:
            ind: Dictionary of technical indicators
            
        Returns:
            Mean reversion perspective with signal, confidence, reasoning
        """
        current_price = ind.get("current_price", 0)
        bb_upper = ind.get("bollinger_upper")
        bb_middle = ind.get("bollinger_middle")
        bb_lower = ind.get("bollinger_lower")
        rsi = ind.get("rsi_14")
        
        signal = "HOLD"
        confidence = 0.5
        reasons = []
        
        # Bollinger Band analysis
        if bb_upper and bb_lower and bb_middle and current_price:
            if current_price >= bb_upper:
                reasons.append(f"Price at upper Bollinger Band")
                signal = "SELL"  # Expect reversion
                confidence = 0.65
                if rsi and rsi > 70:
                    reasons.append("RSI also overbought")
                    confidence = min(0.85, confidence + 0.2)
            elif current_price <= bb_lower:
                reasons.append(f"Price at lower Bollinger Band")
                signal = "BUY"  # Expect reversion
                confidence = 0.65
                if rsi and rsi < 30:
                    reasons.append("RSI also oversold")
                    confidence = min(0.85, confidence + 0.2)
            elif abs(current_price - bb_middle) / bb_middle < 0.002:  # Near middle
                reasons.append("Price near Bollinger middle - neutral")
                signal = "HOLD"
        
        # RSI extreme reversion
        if rsi is not None:
            if rsi > 80:  # Extreme overbought
                reasons.append(f"Extreme RSI {rsi:.1f} - reversion expected")
                signal = "SELL"
                confidence = min(0.9, confidence + 0.25)
            elif rsi < 20:  # Extreme oversold
                reasons.append(f"Extreme RSI {rsi:.1f} - reversion expected")
                signal = "BUY"
                confidence = min(0.9, confidence + 0.25)
        
        return {
            "signal": signal,
            "confidence": confidence,
            "reasoning": "; ".join(reasons) if reasons else "No reversion setup",
            "bb_position": "upper" if current_price and bb_upper and current_price >= bb_upper else 
                          "lower" if current_price and bb_lower and current_price <= bb_lower else "middle",
            "rsi_extreme": rsi > 80 or rsi < 20 if rsi else False
        }
    
    def _aggregate_perspectives(self, perspectives: Dict[str, Dict], 
                                indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate multiple perspectives into final decision using weighted voting.
        
        Args:
            perspectives: Dictionary of perspective analyses
            indicators: Original indicators for context
            
        Returns:
            Final decision with reasoning
        """
        weights = {
            "momentum": self.config["momentum_weight"],
            "trend": self.config["trend_weight"],
            "volume": self.config["volume_weight"],
            "mean_reversion": self.config["mean_reversion_weight"]
        }
        
        buy_score = 0.0
        sell_score = 0.0
        hold_score = 0.0
        
        reasoning_parts = []
        
        for perspective_name, perspective in perspectives.items():
            weight = weights.get(perspective_name, 1.0)
            signal = perspective["signal"]
            confidence = perspective["confidence"]
            weighted_confidence = confidence * weight
            
            if signal == "BUY":
                buy_score += weighted_confidence
            elif signal == "SELL":
                sell_score += weighted_confidence
            else:
                hold_score += weighted_confidence
            
            reasoning_parts.append(
                f"{perspective_name.capitalize()}: {signal} ({confidence:.0%}, weight {weight}x) - {perspective['reasoning']}"
            )
        
        total_score = buy_score + sell_score + hold_score
        
        # Determine final decision
        if buy_score > sell_score and buy_score > hold_score:
            decision = "BUY"
            confidence = buy_score / total_score if total_score > 0 else 0.5
        elif sell_score > buy_score and sell_score > hold_score:
            decision = "SELL"
            confidence = sell_score / total_score if total_score > 0 else 0.5
        else:
            decision = "HOLD"
            confidence = hold_score / total_score if total_score > 0 else 0.5
        
        return {
            "decision": decision,
            "confidence": min(0.95, confidence),
            "reasoning": "\n".join(reasoning_parts),
            "weighted_scores": {
                "buy": buy_score,
                "sell": sell_score,
                "hold": hold_score,
                "total": total_score
            }
        }

