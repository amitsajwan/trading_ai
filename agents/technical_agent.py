"""Technical Analysis Agent."""

import logging
import pandas as pd
import pandas_ta as ta
from typing import Dict, Any
from agents.base_agent import BaseAgent
from agents.state import AgentState
from pathlib import Path

logger = logging.getLogger(__name__)


class TechnicalAnalysisAgent(BaseAgent):
    """Technical analysis agent for chart patterns and momentum signals."""
    
    def __init__(self):
        """Initialize technical analysis agent."""
        prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "technical_analysis.txt"
        system_prompt = prompt_path.read_text() if prompt_path.exists() else self._get_default_prompt()
        super().__init__("technical", system_prompt)
    
    def _get_default_prompt(self) -> str:
        """Get default system prompt."""
        return """You are the Technical Analysis Agent for a {instrument_name} trading system.
Your role: Extract chart patterns and momentum signals from market data.
Analyze OHLC data and provide structured technical analysis."""
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate technical indicators from OHLC data."""
        indicators = {}
        
        if df.empty:
            logger.warning("DataFrame is empty, cannot calculate indicators")
            return indicators
        
        # Use adaptive period based on available data
        data_length = len(df)
        rsi_period = min(14, max(2, data_length - 1))  # At least 2, but prefer 14
        atr_period = min(14, max(2, data_length - 1))
        
        if data_length < 2:
            logger.warning(f"Insufficient data: only {data_length} candles available (need at least 2)")
            return indicators
        
        try:
            # RSI - use shorter period if not enough data
            if data_length >= rsi_period:
                rsi = ta.rsi(df["close"], length=rsi_period)
                indicators["rsi"] = float(rsi.iloc[-1]) if not rsi.empty and pd.notna(rsi.iloc[-1]) else None
                if indicators["rsi"] is not None:
                    indicators["rsi_status"] = (
                        "OVERSOLD" if indicators["rsi"] < 30 else
                        "OVERBOUGHT" if indicators["rsi"] > 70 else
                        "NEUTRAL"
                    )
                else:
                    indicators["rsi_status"] = "NEUTRAL"
            else:
                logger.debug(f"Not enough data for RSI (have {data_length}, need {rsi_period})")
                indicators["rsi"] = None
                indicators["rsi_status"] = "NEUTRAL"
        except Exception as e:
            logger.warning(f"Error calculating RSI: {e}")
            indicators["rsi"] = None
            indicators["rsi_status"] = "NEUTRAL"
        
        try:
            # MACD - needs at least 26 periods, but we'll try with available data
            if data_length >= 26:
                macd_data = ta.macd(df["close"])
                if not macd_data.empty and "MACD_12_26_9" in macd_data.columns:
                    macd_line = macd_data["MACD_12_26_9"].iloc[-1]
                    signal_line = macd_data["MACDs_12_26_9"].iloc[-1] if "MACDs_12_26_9" in macd_data.columns else None
                    indicators["macd"] = float(macd_line) if pd.notna(macd_line) else None
                    indicators["macd_status"] = (
                        "BULLISH" if signal_line and pd.notna(macd_line) and macd_line > signal_line else
                        "BEARISH" if signal_line and pd.notna(macd_line) and macd_line < signal_line else
                        "NEUTRAL"
                    )
                else:
                    indicators["macd"] = None
                    indicators["macd_status"] = "NEUTRAL"
            else:
                logger.debug(f"Not enough data for MACD (have {data_length}, need 26)")
                indicators["macd"] = None
                indicators["macd_status"] = "NEUTRAL"
        except Exception as e:
            logger.warning(f"Error calculating MACD: {e}")
            indicators["macd"] = None
            indicators["macd_status"] = "NEUTRAL"
        
        try:
            # ATR - use shorter period if not enough data
            if data_length >= atr_period:
                atr = ta.atr(df["high"], df["low"], df["close"], length=atr_period)
                indicators["atr"] = float(atr.iloc[-1]) if not atr.empty and pd.notna(atr.iloc[-1]) else None
                if indicators["atr"] is not None and not df.empty:
                    current_price = df["close"].iloc[-1]
                    indicators["volatility_level"] = (
                        "HIGH" if indicators["atr"] > current_price * 0.02 else
                        "LOW" if indicators["atr"] < current_price * 0.01 else
                        "MEDIUM"
                    )
                else:
                    indicators["volatility_level"] = "MEDIUM"
            else:
                logger.debug(f"Not enough data for ATR (have {data_length}, need {atr_period})")
                indicators["atr"] = None
                indicators["volatility_level"] = "MEDIUM"
        except Exception as e:
            logger.warning(f"Error calculating ATR: {e}")
            indicators["atr"] = None
            indicators["volatility_level"] = "MEDIUM"
        
        # Support and Resistance (simplified: recent lows and highs)
        try:
            current_price = df["close"].iloc[-1]
            
            # Use available data (at least 2 candles, prefer 20)
            lookback = min(20, max(2, data_length))
            recent_lows = df["low"].tail(lookback).min()
            recent_highs = df["high"].tail(lookback).max()
            
            indicators["support_level"] = float(recent_lows) if pd.notna(recent_lows) else current_price * 0.98
            indicators["resistance_level"] = float(recent_highs) if pd.notna(recent_highs) else current_price * 1.02
            
            # Trend direction - use available data
            if data_length >= 5:
                # Use shorter SMA if not enough data
                sma_period = min(20, max(5, data_length // 2))
                sma = df["close"].tail(sma_period).mean()
                
                if current_price > sma * 1.01:  # 1% above SMA
                    indicators["trend_direction"] = "UP"
                    indicators["trend_strength"] = min(100, ((current_price - sma) / sma * 100) * 2)
                elif current_price < sma * 0.99:  # 1% below SMA
                    indicators["trend_direction"] = "DOWN"
                    indicators["trend_strength"] = min(100, ((sma - current_price) / current_price * 100) * 2)
                else:
                    indicators["trend_direction"] = "SIDEWAYS"
                    indicators["trend_strength"] = 30.0
            else:
                # Not enough data for trend - use price change
                if data_length >= 2:
                    price_change = (df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0]
                    if price_change > 0.01:
                        indicators["trend_direction"] = "UP"
                        indicators["trend_strength"] = min(100, abs(price_change) * 1000)
                    elif price_change < -0.01:
                        indicators["trend_direction"] = "DOWN"
                        indicators["trend_strength"] = min(100, abs(price_change) * 1000)
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
            if not df.empty:
                current_price = df["close"].iloc[-1]
                indicators["support_level"] = current_price * 0.98
                indicators["resistance_level"] = current_price * 1.02
        
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
                    "note": "INSUFFICIENT_DATA",
                    "confidence_score": 0.0,
                    "rsi": 0.0,
                    "macd": 0.0,
                    "atr": 0.0,
                    "support_level": 0.0,
                    "resistance_level": 0.0,
                    "trend_direction": "UNKNOWN",
                    "trend_strength": 0.0
                }
                self.update_state(state, output, "No OHLC data available")
                return state
            
            # Convert to DataFrame
            df = pd.DataFrame(ohlc_data)
            
            # Check if we have required columns
            required_columns = ["open", "high", "low", "close"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                logger.error(f"OHLC data missing required columns: {missing_columns}")
                logger.debug(f"Available columns: {list(df.columns)}")
                logger.debug(f"Sample data: {df.head() if not df.empty else 'Empty DataFrame'}")
                output = {
                    "note": f"INVALID_DATA_FORMAT: Missing columns {missing_columns}",
                    "confidence_score": 0.0,
                    "available_columns": list(df.columns),
                    "rsi": 0.0,
                    "macd": 0.0,
                    "atr": 0.0,
                    "support_level": 0.0,
                    "resistance_level": 0.0,
                    "trend_direction": "UNKNOWN",
                    "trend_strength": 0.0
                }
                self.update_state(state, output, f"Invalid OHLC data format: missing {missing_columns}")
                return state
            
            # Sort by timestamp if available
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors='coerce')
                df = df.sort_values("timestamp").dropna(subset=["timestamp"])
            
            # Ensure numeric types
            for col in required_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Remove rows with NaN values in required columns
            df = df.dropna(subset=required_columns)
            
            if df.empty:
                logger.warning("OHLC DataFrame is empty after cleaning")
                output = {
                    "note": "INSUFFICIENT_DATA",
                    "confidence_score": 0.0,
                    "rsi": 0.0,
                    "macd": 0.0,
                    "atr": 0.0,
                    "support_level": 0.0,
                    "resistance_level": 0.0,
                    "trend_direction": "UNKNOWN",
                    "trend_strength": 0.0
                }
                self.update_state(state, output, "OHLC data is empty after cleaning (skipping indicators)")
                return state
            
            logger.info(f"Processing {len(df)} OHLC candles for technical analysis")
            
            # Calculate indicators
            indicators = self._calculate_indicators(df)
            
            # Check if we got at least some indicators (support/resistance/trend are always calculated if we have data)
            # RSI/MACD/ATR might be None if insufficient data, but that's OK - we still have trend/support/resistance
            has_basic_indicators = any([
                indicators.get('support_level') is not None,
                indicators.get('resistance_level') is not None,
                indicators.get('trend_direction') is not None
            ])
            
            if not has_basic_indicators:
                logger.warning(f"Failed to calculate any indicators. DataFrame shape: {df.shape}, columns: {list(df.columns)}")
                logger.debug(f"First few rows:\n{df.head()}")
                output = {
                    "note": "INDICATOR_CALCULATION_FAILED",
                    "confidence_score": 0.0,
                    "data_shape": df.shape,
                    "data_columns": list(df.columns),
                    "data_length": len(df),
                    "rsi": 0.0,
                    "macd": 0.0,
                    "atr": 0.0,
                    "support_level": 0.0,
                    "resistance_level": 0.0,
                    "trend_direction": "UNKNOWN",
                    "trend_strength": 0.0
                }
                self.update_state(state, output, f"Skipped indicator calculation (only {len(df)} candles available)")
                return state
            
            # Log what we calculated
            calculated = [k for k, v in indicators.items() if v is not None]
            logger.info(f"Calculated indicators: {calculated} (from {len(df)} candles)")
            
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
            
            # Build human-readable explanation with points and reasoning
            trend_dir = output.get('trend_direction', 'UNKNOWN')
            trend_strength = output.get('trend_strength', 0)
            rsi_status = output.get('rsi_status', 'NEUTRAL')
            rsi_value = output.get('rsi')
            macd_status = output.get('macd_status', 'NEUTRAL')
            volatility = output.get('volatility_level', 'UNKNOWN')
            support = output.get('support_level')
            resistance = output.get('resistance_level')
            confidence = output.get('confidence_score', 0.0)
            
            points = [
                ("Trend Direction", trend_dir,
                 f"Trend strength: {trend_strength:.0f}%"),
                ("RSI Status", f"{rsi_status} ({rsi_value:.1f})" if rsi_value else rsi_status,
                 f"RSI indicates {'overbought' if rsi_status == 'OVERBOUGHT' else 'oversold' if rsi_status == 'OVERSOLD' else 'neutral'} conditions"),
                ("MACD Signal", macd_status,
                 f"Momentum indicator {'bullish' if macd_status == 'BULLISH' else 'bearish' if macd_status == 'BEARISH' else 'neutral'}"),
                ("Volatility", volatility,
                 f"ATR-based volatility assessment"),
                ("Support Level", f"{support:.2f}" if support else "N/A",
                 f"Key support level below current price"),
                ("Resistance Level", f"{resistance:.2f}" if resistance else "N/A",
                 f"Key resistance level above current price"),
                ("Confidence", f"{confidence:.0%}",
                 f"Analysis confidence based on data quality and pattern clarity")
            ]
            
            # Add pattern information if available
            reversal = output.get('reversal_pattern')
            continuation = output.get('continuation_pattern')
            if reversal:
                points.append(("Reversal Pattern", reversal, "Potential trend reversal signal"))
            if continuation:
                points.append(("Continuation Pattern", continuation, "Trend continuation signal"))
            
            summary = f"Overall: {trend_dir} trend with {rsi_status} RSI and {macd_status} MACD"
            
            explanation = self.format_explanation("Technical Analysis", points, summary)
            self.update_state(state, output, explanation)
            
        except Exception as e:
            logger.error(f"Error in technical analysis: {e}")
            output = {
                "error": str(e),
                "confidence_score": 0.0
            }
            self.update_state(state, output, f"Error: {e}")
        
        return state

