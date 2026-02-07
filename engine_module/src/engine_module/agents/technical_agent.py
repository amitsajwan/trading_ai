"""Technical agent implementing engine_module Agent contract.

This is a migration of the legacy technical_agent into the new module and
exposes an async `analyze(context)` method returning `AnalysisResult`.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import asdict
import pandas as pd
import pandas_ta as ta

from engine_module.contracts import Agent, AnalysisResult, create_valid_analysis_result
from engine_module.api_service import DataValidator

logger = logging.getLogger(__name__)


class TechnicalAgent(Agent):
    """Simple technical agent that computes indicators and returns an AnalysisResult."""

    def __init__(self):
        """Initialize technical agent."""
        self._agent_name = "TechnicalAgent"

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze context and return AnalysisResult.

        Expected context keys:
        - 'ohlc': list[dict] where each dict has open/high/low/close[, timestamp]
        - 'technical_indicators': dict with pre-calculated indicators from Redis
        - optional 'current_price'
        - 'instrument': symbol name
        """
        ohlc = context.get("ohlc", [])
        technical_indicators = context.get("technical_indicators", {})
        instrument = context.get("instrument", "BANKNIFTY").upper()
        current_time = context.get("timestamp", datetime.now())

        # STEP 1: Try to get pre-calculated indicators from Redis first
        redis_indicators = await self._get_redis_indicators(instrument, current_time)

        # STEP 2: Validate data availability and freshness
        data_validation = self._validate_technical_data(ohlc, redis_indicators, current_time)

        if not data_validation["data_available"]:
            return AnalysisResult(
                decision="EXCLUDED",
                confidence=0.0,
                details=data_validation,
                excluded=True,
                exclusion_reason=data_validation["exclusion_reason"]
            )

        # STEP 3: Merge Redis indicators with calculated indicators
        if redis_indicators:
            # Use pre-calculated indicators as primary source
            indicators = redis_indicators.copy()
            logger.info(f"[OK] Using {len(redis_indicators)} pre-calculated indicators from Redis for {instrument}")

            # Add any additional calculations if needed
            indicators.update(self._enhance_indicators_with_ohlc(ohlc, indicators))
        else:
            # Fallback to calculating indicators from OHLC data
            logger.warning(f"⚠️ No Redis indicators available for {instrument}, calculating from OHLC data")
            df = pd.DataFrame(ohlc)

            # Ensure required columns
            for col in ("open", "high", "low", "close"):
                if col not in df.columns:
                    return AnalysisResult(decision="HOLD", confidence=0.0, details={"note": f"MISSING_COLUMN_{col}"})

            # Clean and coerce types
            df["open"] = pd.to_numeric(df["open"], errors="coerce")
            df["high"] = pd.to_numeric(df["high"], errors="coerce")
            df["low"] = pd.to_numeric(df["low"], errors="coerce")
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

            if df.empty:
                return AnalysisResult(decision="HOLD", confidence=0.0, details={"note": "EMPTY_AFTER_CLEAN"})

            indicators = self._calculate_indicators(df)

        # STEP 4: Use enhanced indicator set for decision making
        return await self._make_decision_with_enhanced_indicators(indicators, context)

    async def _get_redis_indicators(self, instrument: str, current_time: datetime) -> Dict[str, Any]:
        """Get pre-calculated technical indicators from Redis."""
        try:
            # Import Redis provider
            from engine_module.redis_providers import build_redis_technical_data_provider
            redis_client = None

            # Try to get Redis client
            try:
                from engine_module.api_service import get_redis_client
                redis_client = get_redis_client()
            except:
                pass

            if not redis_client:
                logger.warning("No Redis client available for technical indicators")
                return {}

            # Get technical data provider
            provider = build_redis_technical_data_provider(redis_client)

            # Get indicators for the instrument
            indicators_data = await provider.get_technical_indicators(instrument, periods=100)

            if not indicators_data:
                logger.debug(f"No technical indicators found in Redis for {instrument}")
                return {}

            # Convert to dict format expected by analysis
            indicators = {}

            # Map Redis data to our expected format
            if hasattr(indicators_data, 'rsi_14'):
                indicators['rsi'] = indicators_data.rsi_14
                indicators['rsi_14'] = indicators_data.rsi_14
                indicators['rsi_status'] = (
                    "OVERSOLD" if indicators_data.rsi_14 < 30 else
                    "OVERBOUGHT" if indicators_data.rsi_14 > 70 else
                    "NEUTRAL"
                )

            if hasattr(indicators_data, 'adx_14'):
                indicators['adx'] = indicators_data.adx_14
                indicators['adx_14'] = indicators_data.adx_14

            if hasattr(indicators_data, 'trend_direction'):
                indicators['trend_direction'] = indicators_data.trend_direction

            if hasattr(indicators_data, 'trend_strength'):
                indicators['trend_strength'] = indicators_data.trend_strength

            # Add all available indicators
            indicator_fields = [
                'macd_value', 'macd_signal', 'macd_histogram',
                'bollinger_upper', 'bollinger_middle', 'bollinger_lower', 'bollinger_width', 'bollinger_percent_b',
                'atr_14', 'atr_20',
                'cci_20', 'mfi_14', 'roc_12', 'momentum_10',
                'volume_sma_20', 'volume_rsi_14', 'cmf_20',
                'pivot_point', 'pivot_r1', 'pivot_r2', 'pivot_s1', 'pivot_s2',
                'high_20', 'low_20', 'range_20'
            ]

            for field in indicator_fields:
                if hasattr(indicators_data, field):
                    indicators[field] = getattr(indicators_data, field)

            # Validate data freshness (should be from last 5 minutes)
            if hasattr(indicators_data, 'timestamp') and indicators_data.timestamp:
                try:
                    from dateutil import parser
                    import pytz
                    from datetime import timezone

                    if isinstance(indicators_data.timestamp, str):
                        indicator_time = parser.parse(indicators_data.timestamp)
                    else:
                        indicator_time = indicators_data.timestamp

                    # Ensure both datetimes are timezone-aware
                    if indicator_time.tzinfo is None:
                        # If indicator_time is naive, assume it's UTC
                        indicator_time = indicator_time.replace(tzinfo=timezone.utc)
                    if current_time.tzinfo is None:
                        # If current_time is naive, assume it's UTC
                        current_time = current_time.replace(tzinfo=timezone.utc)

                    time_diff_minutes = (current_time - indicator_time).total_seconds() / 60
                    if time_diff_minutes > 5:
                        # Check if we're in backtest mode - indicators are expected to be "old"
                        import redis
                        redis_client = redis.Redis()
                        mode = redis_client.get('trading_mode')
                        is_backtest = mode and mode.decode('utf-8') == 'backtest'
                        
                        if not is_backtest:
                            logger.warning(f"Redis indicators for {instrument} are {time_diff_minutes:.1f} minutes old")
                        # Still use them but mark as stale
                        indicators['_data_freshness'] = f"STALE_{time_diff_minutes:.1f}MIN"
                    else:
                        indicators['_data_freshness'] = "FRESH"
                except Exception as e:
                    logger.warning(f"Could not validate indicator timestamp: {e}")
                    indicators['_data_freshness'] = "UNKNOWN"

            logger.info(f"Retrieved {len(indicators)} indicators from Redis for {instrument}")
            return indicators

        except Exception as e:
            logger.exception(f"Error retrieving Redis indicators for {instrument}: {e}")
            return {}

    def _validate_technical_data(self, ohlc: List[Dict], redis_indicators: Dict, current_time: datetime) -> Dict[str, Any]:
        """Validate technical data using centralized DataValidator."""

        # Use centralized validation for OHLC data
        ohlc_validation = DataValidator.validate_ohlc_data(ohlc, current_time)

        # Use centralized validation for indicators
        indicators_validation = DataValidator.validate_technical_indicators(redis_indicators, current_time)

        # Combine results
        if not ohlc_validation["valid"] and not indicators_validation["valid"]:
            return {
                "data_available": False,
                "exclusion_reason": "No valid technical data available for analysis",
                "ohlc_validation": ohlc_validation,
                "indicators_validation": indicators_validation
            }

        return {
            "data_available": True,
            "ohlc_validation": ohlc_validation,
            "indicators_validation": indicators_validation,
            "data_sources": {
                "ohlc": ohlc_validation["valid"],
                "redis_indicators": indicators_validation["valid"]
            }
        }

    def _enhance_indicators_with_ohlc(self, ohlc: List[Dict], base_indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Add OHLC-based calculations to complement Redis indicators."""
        enhancements = {}

        try:
            if ohlc and len(ohlc) > 0:
                df = pd.DataFrame(ohlc)

                # Clean data
                for col in ("open", "high", "low", "close"):
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

                if not df.empty:
                    current_price = df["close"].iloc[-1]

                    # Add current price if not in indicators
                    if 'current_price' not in base_indicators:
                        enhancements['current_price'] = current_price

                    # Calculate support/resistance if not available from Redis
                    if 'pivot_point' not in base_indicators and len(df) >= 20:
                        lookback = min(20, len(df))
                        recent_lows = df["low"].tail(lookback).min()
                        recent_highs = df["high"].tail(lookback).max()
                        enhancements["support_level"] = float(recent_lows)
                        enhancements["resistance_level"] = float(recent_highs)

                    # Add ATR if not from Redis
                    if 'atr_14' not in base_indicators and len(df) >= 14:
                        try:
                            atr = ta.atr(df["high"], df["low"], df["close"], length=14)
                            if not atr.empty and pd.notna(atr.iloc[-1]):
                                enhancements["atr"] = float(atr.iloc[-1])
                        except:
                            pass

        except Exception as e:
            logger.warning(f"Error enhancing indicators with OHLC: {e}")

        return enhancements

    async def _make_decision_with_enhanced_indicators(self, indicators: Dict[str, Any], context: Dict[str, Any]) -> AnalysisResult:
        """Make trading decision using comprehensive technical analysis with 15+ indicators."""

        # Extract key indicators with fallbacks
        trend = indicators.get("trend_direction", "SIDEWAYS")
        trend_strength = indicators.get("trend_strength", 0) or 0

        rsi_val = indicators.get("rsi") or indicators.get("rsi_14")
        rsi_status = indicators.get("rsi_status", "NEUTRAL")

        # MACD analysis
        macd_value = indicators.get("macd_value")
        macd_signal = indicators.get("macd_signal")
        macd_histogram = indicators.get("macd_histogram")

        # Bollinger Bands
        bb_upper = indicators.get("bollinger_upper")
        bb_middle = indicators.get("bollinger_middle")
        bb_lower = indicators.get("bollinger_lower")
        bb_width = indicators.get("bollinger_width")
        bb_percent = indicators.get("bollinger_percent_b")

        # ADX for trend strength
        adx = indicators.get("adx") or indicators.get("adx_14", 20)

        # Volatility indicators
        atr = indicators.get("atr") or indicators.get("atr_14")

        # Oscillators
        cci = indicators.get("cci_20")
        mfi = indicators.get("mfi_14")
        roc = indicators.get("roc_12")

        # Volume indicators
        volume_sma = indicators.get("volume_sma_20")
        volume_rsi = indicators.get("volume_rsi_14")

        # Support/Resistance
        support = indicators.get("support_level") or indicators.get("pivot_s1")
        resistance = indicators.get("resistance_level") or indicators.get("pivot_r1")
        pivot = indicators.get("pivot_point")

        current_price = indicators.get("current_price") or context.get("current_price", 0)

        # MULTI-FACTOR DECISION ALGORITHM (40% trend, 30% momentum, 20% volatility, 10% volume)
        decision = "HOLD"
        confidence = 0.5
        signal_strength = 0

        # TREND ANALYSIS (40% weight)
        trend_score = 0
        if trend == "UP":
            trend_score = min(40, trend_strength / 2.5)  # Convert to 0-40 scale
        elif trend == "DOWN":
            trend_score = max(-40, -trend_strength / 2.5)
        else:
            trend_score = 0  # Sideways

        # Strengthen trend signal with ADX
        if adx > 25:  # Strong trend
            trend_score *= 1.2
        elif adx < 20:  # Weak trend
            trend_score *= 0.8

        # MOMENTUM ANALYSIS (30% weight)
        momentum_score = 0

        # RSI component
        if rsi_val is not None:
            if rsi_val < 30:
                momentum_score += 15  # Oversold bounce potential
            elif rsi_val > 70:
                momentum_score -= 15  # Overbought reversal potential
            elif rsi_val > 60:
                momentum_score -= 5   # Bullish but watch
            elif rsi_val < 40:
                momentum_score += 5   # Bearish but watch

        # MACD component
        if macd_value is not None and macd_signal is not None:
            macd_diff = macd_value - macd_signal
            momentum_score += min(10, max(-10, macd_diff * 2))

        # Oscillators
        if cci is not None:
            if cci > 100:
                momentum_score -= 5
            elif cci < -100:
                momentum_score += 5

        if mfi is not None:
            if mfi > 80:
                momentum_score -= 5
            elif mfi < 20:
                momentum_score += 5

        # VOLATILITY ANALYSIS (20% weight)
        volatility_score = 0

        # Bollinger Bands
        if bb_percent is not None:
            if bb_percent > 1.0:  # Price above upper band
                volatility_score -= 10
            elif bb_percent < 0.0:  # Price below lower band
                volatility_score += 10
            elif bb_percent > 0.8:  # Near upper band
                volatility_score -= 5
            elif bb_percent < 0.2:  # Near lower band
                volatility_score += 5

        # ATR for volatility context
        if atr and current_price:
            atr_percent = (atr / current_price) * 100
            if atr_percent > 2.0:
                volatility_score = volatility_score * 1.1  # Amplify signals in high vol
            elif atr_percent < 0.5:
                volatility_score = volatility_score * 0.9  # Dampen signals in low vol

        # VOLUME ANALYSIS (10% weight)
        volume_score = 0

        if volume_rsi is not None:
            if volume_rsi > 70:
                volume_score += 5  # High volume confirms trend
            elif volume_rsi < 30:
                volume_score -= 5  # Low volume weakens signal

        # CALCULATE TOTAL SCORE
        total_score = trend_score + (momentum_score * 0.75) + (volatility_score * 0.5) + volume_score

        # MAKE DECISION
        if total_score > 25:
            decision = "BUY"
            confidence = min(0.9, 0.5 + abs(total_score) / 100)
            signal_strength = abs(total_score)
        elif total_score < -25:
            decision = "SELL"
            confidence = min(0.9, 0.5 + abs(total_score) / 100)
            signal_strength = abs(total_score)
        else:
            decision = "HOLD"
            confidence = max(0.3, 0.5 - abs(total_score) / 50)

        # GENERATE COMPREHENSIVE REASONING
        reasoning_parts = []
        analysis_summary = []

        # Trend Analysis
        if trend == "UP":
            reasoning_parts.append(f"Strong upward trend detected with {trend_strength:.1f}% strength (ADX: {adx:.1f})")
            analysis_summary.append(f"UPTREND_{trend_strength:.0f}%")
        elif trend == "DOWN":
            reasoning_parts.append(f"Downward trend identified with {trend_strength:.1f}% strength (ADX: {adx:.1f})")
            analysis_summary.append(f"DOWNTREND_{trend_strength:.0f}%")
        else:
            reasoning_parts.append(f"Sideways/consolidation pattern (ADX: {adx:.1f})")
            analysis_summary.append("SIDEWAYS")

        # Momentum Analysis
        momentum_signals = []
        if rsi_val is not None:
            if rsi_val < 30:
                momentum_signals.append(f"RSI {rsi_val:.1f} (oversold)")
                analysis_summary.append("RSI_OVERSOLD")
            elif rsi_val > 70:
                momentum_signals.append(f"RSI {rsi_val:.1f} (overbought)")
                analysis_summary.append("RSI_OVERBOUGHT")
            else:
                momentum_signals.append(f"RSI {rsi_val:.1f} (neutral)")

        if macd_value is not None and macd_signal is not None:
            macd_status = "bullish" if macd_value > macd_signal else "bearish"
            momentum_signals.append(f"MACD {macd_status} (signal: {macd_signal:.2f})")
            analysis_summary.append(f"MACD_{macd_status.upper()}")

        if momentum_signals:
            reasoning_parts.append(f"Momentum indicators: {', '.join(momentum_signals)}")

        # Volatility Analysis
        if bb_percent is not None:
            if bb_percent > 1.0:
                reasoning_parts.append(f"Price significantly above Bollinger upper band ({bb_percent:.2f}) - potential reversal")
                analysis_summary.append("BB_OVERBOUGHT")
            elif bb_percent < 0.0:
                reasoning_parts.append(f"Price significantly below Bollinger lower band ({bb_percent:.2f}) - potential bounce")
                analysis_summary.append("BB_OVERSOLD")
            else:
                reasoning_parts.append(f"Bollinger Band position: {bb_percent:.2f}")

        # Volume Confirmation
        if volume_rsi is not None:
            volume_status = "high" if volume_rsi > 60 else "low" if volume_rsi < 40 else "moderate"
            reasoning_parts.append(f"Volume momentum: {volume_status} (VRSI: {volume_rsi:.1f})")

        # Key Levels
        if support and resistance and current_price:
            dist_to_support = ((current_price - support) / support) * 100
            dist_to_resistance = ((resistance - current_price) / resistance) * 100
            reasoning_parts.append(f"Key levels: Support Rs.{support:,.0f} ({dist_to_support:+.1f}%), Resistance Rs.{resistance:,.0f} ({dist_to_resistance:.1f}%)")

        # Decision Rationale
        if decision == "BUY":
            reasoning_parts.append(f"BUY signal: Bullish trend aligned with momentum indicators. Total score: +{total_score:.1f}")
        elif decision == "SELL":
            reasoning_parts.append(f"SELL signal: Bearish trend confirmed by momentum indicators. Total score: {total_score:.1f}")
        else:
            reasoning_parts.append(f"HOLD: Mixed signals with total score: {total_score:.1f}. Waiting for clearer direction.")

        # Risk Assessment
        if atr and current_price:
            risk_pct = (atr / current_price) * 100
            reasoning_parts.append(f"Risk assessment: ATR suggests {risk_pct:.1f}% average move. Position accordingly.")

        # COMPILE FINAL ANALYSIS
        details = indicators.copy()
        details.update({
            "reasoning": " ".join(reasoning_parts),
            "decision_basis": f"multi-factor_score={total_score:.1f}",
            "analysis_summary": f"Technical analysis: {' | '.join(analysis_summary)}. {decision} with {confidence:.1f} confidence.",
            "signal_strength": signal_strength,
            "key_levels": {
                "support": float(support) if support else None,
                "resistance": float(resistance) if resistance else None,
                "pivot": float(pivot) if pivot else None,
                "current_price": float(current_price) if current_price else None
            },
            "indicator_scores": {
                "trend": trend_score,
                "momentum": momentum_score,
                "volatility": volatility_score,
                "volume": volume_score,
                "total": total_score
            },
            "data_sources": {
                "redis_indicators": len([k for k in indicators.keys() if not k.startswith('_')]),
                "calculated_indicators": len([k for k in indicators.keys() if k.startswith('_calc_')]),
                "data_freshness": indicators.get('_data_freshness', 'UNKNOWN')
            }
        })

        return create_valid_analysis_result(
            decision=decision,
            confidence=confidence,
            details=details,
            min_confidence=0.15  # Higher threshold for comprehensive analysis
        )

    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate a small set of technical indicators."""
        indicators: Dict[str, Any] = {}
        data_length = len(df)

        try:
            # RSI (default 14 or shorter if insufficient data)
            rsi_period = min(14, max(2, data_length - 1))
            if data_length >= 2:
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
                indicators["rsi"] = None
                indicators["rsi_status"] = "NEUTRAL"
        except Exception as e:
            logger.warning(f"RSI calc failed: {e}")
            indicators["rsi"] = None
            indicators["rsi_status"] = "NEUTRAL"

        try:
            # ATR
            atr_period = min(14, max(2, data_length - 1))
            if data_length >= 2:
                atr = ta.atr(df["high"], df["low"], df["close"], length=atr_period)
                indicators["atr"] = float(atr.iloc[-1]) if not atr.empty and pd.notna(atr.iloc[-1]) else None
            else:
                indicators["atr"] = None
        except Exception as e:
            logger.warning(f"ATR calc failed: {e}")
            indicators["atr"] = None

        try:
            current_price = df["close"].iloc[-1]
            lookback = min(20, max(2, data_length))
            recent_lows = df["low"].tail(lookback).min()
            recent_highs = df["high"].tail(lookback).max()
            indicators["support_level"] = float(recent_lows)
            indicators["resistance_level"] = float(recent_highs)

            # Trend using EMA crossover
            if data_length >= 21:
                ema9 = ta.ema(df["close"], length=9)
                ema21 = ta.ema(df["close"], length=21)
                if not ema9.empty and not ema21.empty and pd.notna(ema9.iloc[-1]) and pd.notna(ema21.iloc[-1]):
                    ema9_val = float(ema9.iloc[-1])
                    ema21_val = float(ema21.iloc[-1])
                    diff_pct = (ema9_val - ema21_val) / ema21_val * 100
                    if diff_pct > 0.5:
                        indicators["trend_direction"] = "UP"
                        indicators["trend_strength"] = min(100, abs(diff_pct) * 2)
                    elif diff_pct < -0.5:
                        indicators["trend_direction"] = "DOWN"
                        indicators["trend_strength"] = min(100, abs(diff_pct) * 2)
                    else:
                        indicators["trend_direction"] = "SIDEWAYS"
                        indicators["trend_strength"] = 30.0
                else:
                    indicators["trend_direction"] = "SIDEWAYS"
                    indicators["trend_strength"] = 30.0
            else:
                # Fallback to SMA-based trend
                if data_length >= 5:
                    sma_period = min(20, max(5, data_length // 2))
                    sma = df["close"].tail(sma_period).mean()
                    if current_price > sma * 1.01:
                        indicators["trend_direction"] = "UP"
                        indicators["trend_strength"] = min(100, ((current_price - sma) / sma * 100) * 2)
                    elif current_price < sma * 0.99:
                        indicators["trend_direction"] = "DOWN"
                        indicators["trend_strength"] = min(100, ((sma - current_price) / current_price * 100) * 2)
                    else:
                        indicators["trend_direction"] = "SIDEWAYS"
                        indicators["trend_strength"] = 30.0
                else:
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
            logger.warning(f"Support/res calc failed: {e}")
            indicators["trend_direction"] = "SIDEWAYS"
            indicators["trend_strength"] = 30.0

        return indicators

