"""Technical Analysis Agent."""

import logging
import pandas as pd
import pandas_ta as ta
from typing import Dict, Any
from agents.base_agent import BaseAgent
from agents.state import AgentState
from pathlib import Path
from config.settings import settings

logger = logging.getLogger(__name__)


class TechnicalAnalysisAgent(BaseAgent):
    """Technical analysis agent for chart patterns and momentum signals."""
    
    def __init__(self):
        """Initialize technical analysis agent."""
        # Use dynamic prompt so system is instrument-decoupled (crypto vs indices, etc.)
        super().__init__("technical", self._get_default_prompt())
    
    def _get_default_prompt(self) -> str:
        """Get default system prompt."""
        instrument_name = settings.instrument_name
        return f"""You are the Technical Analysis Agent for a {instrument_name} trading system.
Your role: Extract chart patterns and momentum signals from market data.
Analyze OHLC data and provide structured technical analysis."""
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate technical indicators from OHLC data."""
        if df.empty or len(df) < 14:
            return {}
        
        indicators = {}
        
        try:
            # RSI
            rsi = ta.rsi(df["close"], length=14)
            indicators["rsi"] = float(rsi.iloc[-1]) if not rsi.empty else None
            indicators["rsi_status"] = (
                "OVERSOLD" if indicators["rsi"] < 30 else
                "OVERBOUGHT" if indicators["rsi"] > 70 else
                "NEUTRAL"
            )
        except Exception as e:
            logger.warning(f"Error calculating RSI: {e}")
            indicators["rsi"] = None
        
        try:
            # MACD
            macd_data = ta.macd(df["close"])
            if not macd_data.empty and "MACD_12_26_9" in macd_data.columns:
                macd_line = macd_data["MACD_12_26_9"].iloc[-1]
                signal_line = macd_data["MACDs_12_26_9"].iloc[-1] if "MACDs_12_26_9" in macd_data.columns else None
                indicators["macd"] = float(macd_line) if pd.notna(macd_line) else None
                indicators["macd_status"] = (
                    "BULLISH" if signal_line and macd_line > signal_line else
                    "BEARISH" if signal_line and macd_line < signal_line else
                    "NEUTRAL"
                )
        except Exception as e:
            logger.warning(f"Error calculating MACD: {e}")
            indicators["macd"] = None
        
        try:
            # ATR
            atr = ta.atr(df["high"], df["low"], df["close"], length=14)
            indicators["atr"] = float(atr.iloc[-1]) if not atr.empty else None
            indicators["volatility_level"] = (
                "HIGH" if indicators["atr"] and indicators["atr"] > df["close"].iloc[-1] * 0.02 else
                "LOW" if indicators["atr"] and indicators["atr"] < df["close"].iloc[-1] * 0.01 else
                "MEDIUM"
            )
        except Exception as e:
            logger.warning(f"Error calculating ATR: {e}")
            indicators["atr"] = None
        
        # Support and Resistance (simplified: recent lows and highs)
        try:
            recent_lows = df["low"].tail(20).min()
            recent_highs = df["high"].tail(20).max()
            current_price = df["close"].iloc[-1]
            
            indicators["support_level"] = float(recent_lows)
            indicators["resistance_level"] = float(recent_highs)
            
            # Trend direction
            if len(df) >= 20:
                sma_20 = df["close"].tail(20).mean()
                sma_50 = df["close"].tail(min(50, len(df))).mean() if len(df) >= 50 else sma_20
                
                if current_price > sma_20 > sma_50:
                    indicators["trend_direction"] = "UP"
                    indicators["trend_strength"] = min(100, ((current_price - sma_20) / sma_20 * 100) * 2)
                elif current_price < sma_20 < sma_50:
                    indicators["trend_direction"] = "DOWN"
                    indicators["trend_strength"] = min(100, ((sma_20 - current_price) / current_price * 100) * 2)
                else:
                    indicators["trend_direction"] = "SIDEWAYS"
                    indicators["trend_strength"] = 30.0
            else:
                indicators["trend_direction"] = "SIDEWAYS"
                indicators["trend_strength"] = 30.0
        except Exception as e:
            logger.warning(f"Error calculating support/resistance: {e}")
            indicators["trend_direction"] = "SIDEWAYS"
            indicators["trend_strength"] = 30.0
        
        return indicators
    
    def process(self, state: AgentState) -> AgentState:
        """Process technical analysis."""
        logger.info("Processing technical analysis...")
        
        try:
            # Convert OHLC data to DataFrame
            ohlc_data = state.ohlc_5min if state.ohlc_5min else state.ohlc_1min
            if not ohlc_data:
                logger.warning("No OHLC data available for technical analysis")
                output = {
                    "error": "INSUFFICIENT_DATA",
                    "confidence_score": 0.0
                }
                self.update_state(state, output, "No OHLC data available")
                return state
            
            # Convert to DataFrame
            df = pd.DataFrame(ohlc_data)
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.sort_values("timestamp")
            
            # Calculate indicators
            indicators = self._calculate_indicators(df)
            
            # Prepare prompt with data
            current_price = state.current_price or (df["close"].iloc[-1] if not df.empty else 0.0)
            
            prompt = f"""
Current Price: {current_price}
OHLC 5-min data: {len(ohlc_data)} candles
Technical Indicators:
- RSI: {indicators.get('rsi', 'N/A')}
- MACD: {indicators.get('macd', 'N/A')}
- ATR: {indicators.get('atr', 'N/A')}
- Support Level: {indicators.get('support_level', 'N/A')}
- Resistance Level: {indicators.get('resistance_level', 'N/A')}
- Trend: {indicators.get('trend_direction', 'N/A')} ({indicators.get('trend_strength', 0)}% strength)

Analyze the technical patterns and provide your assessment.
"""
            
            # Use calculated indicators as primary - they're more reliable
            # Only use LLM for pattern recognition that can't be calculated programmatically
            output = {
                **indicators,  # All calculated indicators (RSI, MACD, ATR, support, resistance, trend)
            }
            
            # Only call LLM for advanced pattern recognition (optional enhancement)
            try:
                response_format = {
                    "reversal_pattern": "string or null",
                    "continuation_pattern": "string or null",
                    "candlestick_pattern": "string or null",
                    "volume_confirmation": "boolean",
                    "divergence_detected": "boolean",
                    "divergence_type": "string",
                    "confidence_score": "float (0-1)"
                }
                
                analysis = self._call_llm_structured(prompt, response_format)
                
                # Add LLM pattern recognition to output (but don't override calculated values)
                output.update({
                    "reversal_pattern": analysis.get("reversal_pattern"),
                    "continuation_pattern": analysis.get("continuation_pattern"),
                    "candlestick_pattern": analysis.get("candlestick_pattern"),
                    "volume_confirmation": analysis.get("volume_confirmation", False),
                    "divergence_detected": analysis.get("divergence_detected", False),
                    "divergence_type": analysis.get("divergence_type"),
                    "confidence_score": analysis.get("confidence_score", 0.7)
                })
            except Exception as e:
                logger.warning(f"LLM pattern recognition failed, using calculated indicators only: {e}")
                # Use calculated indicators only
                output["confidence_score"] = 0.7  # Default confidence for calculated indicators
            
            explanation = f"Technical analysis: {output.get('trend_direction', 'UNKNOWN')} trend, "
            explanation += f"RSI {output.get('rsi_status', 'NEUTRAL')}, "
            explanation += f"confidence {output.get('confidence_score', 0.0):.2f}"
            
            self.update_state(state, output, explanation)
            
        except Exception as e:
            logger.error(f"Error in technical analysis: {e}")
            output = {
                "error": str(e),
                "confidence_score": 0.0
            }
            self.update_state(state, output, f"Error: {e}")
        
        return state

