"""Signal Creation Module - Converts Orchestrator Decisions to TradingCondition Signals.

This module bridges the gap between orchestrator analysis cycles and real-time signal monitoring.
It extracts executable conditions from AnalysisResult and creates TradingCondition objects that
can be monitored and executed when conditions are met.
"""

import logging
import os
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from dataclasses import asdict

# IST timezone for Indian financial markets
IST = timezone(timedelta(hours=5, minutes=30))


def get_current_time(redis_client: Optional[Any] = None) -> datetime:
    """Get current time, considering virtual time mode for backtesting.

    In backtest/historical mode, uses virtual time from Redis if available.
    Otherwise uses real current time.

    Args:
        redis_client: Redis client to check for virtual time

    Returns:
        Current datetime (IST timezone)
    """
    if redis_client:
        try:
            # Check if virtual time is enabled
            virtual_enabled = redis_client.get("system:virtual_time:enabled")
            if virtual_enabled and virtual_enabled.decode() == "1":
                virtual_time_str = redis_client.get("system:virtual_time:current")
                if virtual_time_str:
                    virtual_time = datetime.fromisoformat(virtual_time_str.decode())
                    # Ensure it's in IST
                    if virtual_time.tzinfo is None:
                        virtual_time = virtual_time.replace(tzinfo=IST)
                    else:
                        virtual_time = virtual_time.astimezone(IST)
                    return virtual_time
        except Exception as e:
            # If Redis fails, fall back to real time
            pass

    # Default to real current time
    return datetime.now(IST)

from .signal_monitor import TradingCondition, ConditionOperator

# Import standardized indicator constants for consistency
try:
    from market_data.technical_indicators_constants import *
except ImportError:
    # Fallback definitions if market_data not available
    RSI_14 = "rsi_14"
    ADX_14 = "adx_14"
    RSI_9 = "rsi_9"
    SMA_20 = "sma_20"
    SMA_50 = "sma_50"
    EMA_12 = "ema_12"
    EMA_26 = "ema_26"
    MACD_VALUE = "macd_value"
    MACD_SIGNAL = "macd_signal"
    MACD_HISTOGRAM = "macd_histogram"
    BOLlinger_UPPER = "bollinger_upper"
    BOLlinger_LOWER = "bollinger_lower"
    ATR_14 = "atr_14"
    TREND_DIRECTION = "trend_direction"
    CURRENT_PRICE = "current_price"

logger = logging.getLogger(__name__)

def _parse_operator(op: Any) -> ConditionOperator:
    """Parse operator from various string/enum forms into ConditionOperator."""
    if isinstance(op, ConditionOperator):
        return op
    if op is None:
        return ConditionOperator.GREATER_THAN
    s = str(op).strip()
    # Accept both enum values (">") and enum names ("GREATER_THAN")
    mapping = {
        ">": ConditionOperator.GREATER_THAN,
        "<": ConditionOperator.LESS_THAN,
        ">=": ConditionOperator.GREATER_EQUAL,
        "<=": ConditionOperator.LESS_EQUAL,
        "==": ConditionOperator.EQUAL,
        "crosses_above": ConditionOperator.CROSSES_ABOVE,
        "crosses_below": ConditionOperator.CROSSES_BELOW,
        "GREATER_THAN": ConditionOperator.GREATER_THAN,
        "LESS_THAN": ConditionOperator.LESS_THAN,
        "GREATER_EQUAL": ConditionOperator.GREATER_EQUAL,
        "LESS_EQUAL": ConditionOperator.LESS_EQUAL,
        "EQUAL": ConditionOperator.EQUAL,
        "CROSSES_ABOVE": ConditionOperator.CROSSES_ABOVE,
        "CROSSES_BELOW": ConditionOperator.CROSSES_BELOW,
    }
    return mapping.get(s, mapping.get(s.lower(), ConditionOperator.GREATER_THAN))


def _extract_structured_signals(details: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract structured signal specs from decision details.

    Supported shapes:
    - details["signals"] = [ { ...signal spec... }, ... ]
    - details["entry_signals"] / details["exit_signals"]
    - details["judge"]["signals"] (if a judge nested payload is stored)
    """
    if not details or not isinstance(details, dict):
        return []

    # direct
    if isinstance(details.get("signals"), list):
        return [s for s in details["signals"] if isinstance(s, dict)]

    # split
    out: List[Dict[str, Any]] = []
    if isinstance(details.get("entry_signals"), list):
        out.extend([s for s in details["entry_signals"] if isinstance(s, dict)])
    if isinstance(details.get("exit_signals"), list):
        out.extend([s for s in details["exit_signals"] if isinstance(s, dict)])
    if out:
        return out

    # nested judge payload
    judge = details.get("judge")
    if isinstance(judge, dict) and isinstance(judge.get("signals"), list):
        return [s for s in judge["signals"] if isinstance(s, dict)]

    return []


async def _generate_options_strategy(strategy_type: str, instrument: str) -> Optional[Dict[str, Any]]:
    """Generate options strategy details using OptionsStrategyAgent."""
    try:
        logger.error(f"DEBUG: _generate_options_strategy called for {strategy_type} on {instrument}")
        # Import here to avoid circular imports
        from .agents.options_strategy_agent import OptionsStrategyAgent

        # Create agent instance
        agent = OptionsStrategyAgent()

        # Create context for options strategy generation
        context = {
            "instrument": instrument,
            "current_price": None,  # Will be fetched by agent
            "market_data": {},
            "indicators": {},
            "strategy_type": strategy_type.lower(),
            "is_backtest": True  # We're in signal creation context
        }

        logger.error(f"DEBUG: Calling OptionsStrategyAgent.analyze with context: {context}")
        # Generate the strategy
        result = await agent.analyze(context)
        logger.error(f"DEBUG: OptionsStrategyAgent returned result: {type(result)}")
        if result:
            logger.error(f"DEBUG: Result has options_strategy attr: {hasattr(result, 'options_strategy')}")
            if hasattr(result, 'options_strategy'):
                logger.error(f"DEBUG: options_strategy value: {result.options_strategy}")
                logger.error(f"DEBUG: options_strategy type: {type(result.options_strategy)}")

        if result and hasattr(result, 'options_strategy') and result.options_strategy:
            # Extract options strategy from agent result and convert to dict for MongoDB
            options_strategy = result.options_strategy
            logger.error(f"DEBUG: Converting options_strategy to dict: {options_strategy}")
            try:
                # Convert dataclass to dict
                strategy_dict = {
                    'strategy_type': options_strategy.strategy_type.value if hasattr(options_strategy.strategy_type, 'value') else str(options_strategy.strategy_type),
                    'underlying': options_strategy.underlying,
                    'expiry': options_strategy.expiry,
                    'legs': [
                        {
                            'action': getattr(leg, 'position', 'BUY'),  # Use position instead of action
                            'type': getattr(leg, 'option_type', 'CALL'),  # Use option_type instead of type
                            'strike': getattr(leg, 'strike_price', 0),  # Use strike_price instead of strike
                            'quantity': getattr(leg, 'quantity', 1),
                            'premium': getattr(leg, 'premium', 0.0),
                        }
                        for leg in options_strategy.legs
                    ],
                    'max_profit': getattr(options_strategy, 'max_profit', 0.0),
                    'max_loss': getattr(options_strategy, 'max_loss', 0.0),
                    'breakeven_points': getattr(options_strategy, 'breakeven_points', []),
                    'risk_reward_ratio': getattr(options_strategy, 'risk_reward_ratio', 0.0),
                    'margin_required': getattr(options_strategy, 'margin_required', 0.0),
                }
                logger.error(f"DEBUG: Converted strategy_dict: {strategy_dict}")
                return strategy_dict
            except Exception as e:
                logger.error(f"DEBUG: Error converting options_strategy: {e}")
                return None

        logger.warning(f"OptionsStrategyAgent failed to generate strategy for {strategy_type}")
        return None

    except Exception as e:
        logger.exception(f"Error generating options strategy: {e}")
        return None


def _create_signal_from_spec(
    spec: Dict[str, Any],
    instrument: str,
    default_confidence: float,
    default_valid_minutes: int,
    current_price: Optional[float],
) -> Optional[TradingCondition]:
    """Create TradingCondition from a structured signal spec."""
    try:
        action = str(spec.get("action") or spec.get("decision") or "").strip()
        if not action:
            return None

        confidence = float(spec.get("confidence", default_confidence))
        position_size = float(spec.get("position_size", 1.0))
        strategy_type = str(spec.get("strategy_type", "SPOT")).upper()
        execution_mode = str(spec.get("execution_mode", "CONDITIONAL")).upper()

        # Conditions: list[{indicator, operator, threshold}]
        conds = spec.get("conditions") or spec.get("entry_conditions") or []
        if not isinstance(conds, list) or not conds:
            # Backward compat: single condition fields
            conds = [{
                "indicator": spec.get("indicator") or "current_price",
                "operator": spec.get("operator") or ">",
                "threshold": spec.get("threshold", current_price if current_price else 0.0),
                "source": "structured_fallback"
            }]

        parsed_conditions: List[Dict[str, Any]] = []
        for c in conds:
            if not isinstance(c, dict):
                continue
            indicator = c.get("indicator") or c.get("name") or c.get("field")
            threshold = c.get("threshold")
            if indicator is None or threshold is None:
                continue
            try:
                threshold_f = float(threshold)
            except Exception:
                continue
            parsed_conditions.append({
                "indicator": str(indicator),
                "operator": _parse_operator(c.get("operator")),
                "threshold": threshold_f,
                "source": c.get("source", "structured")
            })

        if not parsed_conditions:
            return None

        primary = parsed_conditions[0]
        additional = []
        for c in parsed_conditions[1:]:
            additional.append({
                "indicator": c["indicator"],
                "operator": c["operator"].value,
                "threshold": c["threshold"],
            })

        # Risk params
        stop_loss = spec.get("stop_loss")
        take_profit = spec.get("take_profit")
        entry_price = spec.get("entry_price", current_price)

        # Validity
        valid_for_minutes = spec.get("valid_for_minutes", default_valid_minutes)
        try:
            valid_for_minutes = int(valid_for_minutes)
        except Exception:
            valid_for_minutes = default_valid_minutes

        # Use virtual time if available for backtesting
        now = get_current_time(redis_client)
        expires_at = (now + timedelta(minutes=valid_for_minutes)).isoformat()

        # Metadata
        metadata = spec.get("metadata") if isinstance(spec.get("metadata"), dict) else {}
        metadata = {
            **metadata,
            "signal_source": metadata.get("signal_source", "judge"),
            "execution_mode": execution_mode,
        }

        # Hash for dedupe/traceability
        import hashlib
        try:
            rh_src = json.dumps({
                "instrument": instrument,
                "action": action,
                "conditions": [
                    {"indicator": c["indicator"], "operator": c["operator"].value, "threshold": c["threshold"]}
                    for c in parsed_conditions
                ],
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "entry_price": entry_price,
            }, sort_keys=True)
            reason_hash = hashlib.sha1(rh_src.encode("utf-8")).hexdigest()[:12]
        except Exception:
            reason_hash = None

        condition_id = f"{instrument}_{action}_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"

        return TradingCondition(
            condition_id=condition_id,
            instrument=instrument,
            indicator=primary["indicator"],
            operator=primary["operator"],
            threshold=primary["threshold"],
            action=action,
            strategy_type=strategy_type,
            position_size=position_size,
            confidence=confidence,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_price=entry_price,
            additional_conditions=additional,
            metadata=metadata,
            execution_mode=execution_mode,
            reason_hash=reason_hash,
            parsed_conditions=[
                {"indicator": c["indicator"], "operator": c["operator"].value, "threshold": c["threshold"], "source": c.get("source")}
                for c in parsed_conditions
            ],
            expires_at=expires_at,
            is_active=True,
        )
    except Exception as e:
        logger.warning(f"Failed to create signal from structured spec: {e}")
        return None


def extract_conditions_from_reasoning(reasoning: str, current_price: Optional[float] = None) -> List[Dict[str, Any]]:
    """Extract trading conditions from agent/LLM reasoning text.
    
    Simple regex-based parsing for common patterns:
    - "RSI > 32", "RSI crosses above 30"
    - "price > 45000", "price < 44000"
    - "volume > 1000000"
    - "MACD crosses above signal"
    
    Args:
        reasoning: Text reasoning from agent or LLM
        current_price: Current market price for relative thresholds
        
    Returns:
        List of condition dictionaries with indicator, operator, threshold
    """
    conditions = []
    
    if not reasoning:
        return conditions
    
    reasoning_lower = reasoning.lower()
    
    # Pattern 1: RSI conditions
    rsi_patterns = [
        (r'rsi[_\s]*(\d+)?\s*>\s*(\d+(?:\.\d+)?)', 'rsi_14', ConditionOperator.GREATER_THAN),
        (r'rsi[_\s]*(\d+)?\s*<\s*(\d+(?:\.\d+)?)', 'rsi_14', ConditionOperator.LESS_THAN),
        (r'rsi[_\s]*(\d+)?\s*>=\s*(\d+(?:\.\d+)?)', 'rsi_14', ConditionOperator.GREATER_EQUAL),
        (r'rsi[_\s]*(\d+)?\s*<=\s*(\d+(?:\.\d+)?)', 'rsi_14', ConditionOperator.LESS_EQUAL),
        (r'rsi[_\s]*(\d+)?\s*crosses?\s*above\s*(\d+(?:\.\d+)?)', 'rsi_14', ConditionOperator.CROSSES_ABOVE),
        (r'rsi[_\s]*(\d+)?\s*crosses?\s*below\s*(\d+(?:\.\d+)?)', 'rsi_14', ConditionOperator.CROSSES_BELOW),
    ]
    
    for pattern, indicator, operator in rsi_patterns:
        matches = re.finditer(pattern, reasoning_lower, re.IGNORECASE)
        for match in matches:
            threshold = float(match.group(2))
            conditions.append({
                "indicator": indicator,
                "operator": operator,
                "threshold": threshold,
                "source": "reasoning_parse"
            })
    
    # Pattern 2: Price conditions
    price_patterns = [
        (r'price\s*>\s*(\d+(?:\.\d+)?)', 'current_price', ConditionOperator.GREATER_THAN),
        (r'price\s*<\s*(\d+(?:\.\d+)?)', 'current_price', ConditionOperator.LESS_THAN),
        (r'price\s*>=\s*(\d+(?:\.\d+)?)', 'current_price', ConditionOperator.GREATER_EQUAL),
        (r'price\s*<=\s*(\d+(?:\.\d+)?)', 'current_price', ConditionOperator.LESS_EQUAL),
        (r'above\s*(\d+(?:\.\d+)?)', 'current_price', ConditionOperator.GREATER_THAN),
        (r'below\s*(\d+(?:\.\d+)?)', 'current_price', ConditionOperator.LESS_THAN),
    ]
    
    for pattern, indicator, operator in price_patterns:
        matches = re.finditer(pattern, reasoning_lower, re.IGNORECASE)
        for match in matches:
            threshold = float(match.group(1))
            conditions.append({
                "indicator": indicator,
                "operator": operator,
                "threshold": threshold,
                "source": "reasoning_parse"
            })
    
    # Pattern 3: Volume conditions
    volume_patterns = [
        (r'volume\s*>\s*(\d+(?:\.\d+)?)', 'volume', ConditionOperator.GREATER_THAN),
        (r'volume\s*<\s*(\d+(?:\.\d+)?)', 'volume', ConditionOperator.LESS_THAN),
    ]
    
    for pattern, indicator, operator in volume_patterns:
        matches = re.finditer(pattern, reasoning_lower, re.IGNORECASE)
        for match in matches:
            threshold = float(match.group(1))
            conditions.append({
                "indicator": indicator,
                "operator": operator,
                "threshold": threshold,
                "source": "reasoning_parse"
            })
    
    return conditions


def _create_spot_trading_conditions(decision: str, technical_indicators: Dict[str, Any],
                                   current_price: float) -> List[Dict[str, Any]]:
    """Create appropriate conditions for spot trading strategies."""
    conditions = []

    rsi = technical_indicators.get(RSI_14, 50)

    if "BUY" in decision.upper():
        # For BUY signals, create condition based on current RSI
        if rsi < 40:  # Oversold - wait for recovery
            conditions.append({
                "indicator": RSI_14,
                "operator": ConditionOperator.GREATER_THAN,
                "threshold": 35.0,  # Exit oversold
                "source": "spot_buy_oversold"
            })
            logger.info(f"SignalCreator: Created SPOT BUY condition - RSI > 35 (current: {rsi})")
        else:  # Normal conditions - immediate execution
            conditions.append({
                "indicator": CURRENT_PRICE,
                "operator": ConditionOperator.GREATER_THAN,
                "threshold": current_price * 0.99,  # Small buffer for immediate execution
                "source": "spot_buy_immediate"
            })
            logger.info(f"SignalCreator: Created SPOT BUY immediate condition (current: {rsi})")

    elif "SELL" in decision.upper():
        # For SELL signals, create condition based on current RSI
        if rsi > 60:  # Overbought - wait for pullback
            conditions.append({
                "indicator": RSI_14,
                "operator": ConditionOperator.LESS_THAN,
                "threshold": 65.0,  # Exit overbought
                "source": "spot_sell_overbought"
            })
            logger.info(f"SignalCreator: Created SPOT SELL condition - RSI < 65 (current: {rsi})")
        else:  # Normal conditions - immediate execution
            conditions.append({
                "indicator": CURRENT_PRICE,
                "operator": ConditionOperator.LESS_THAN,
                "threshold": current_price * 1.01,  # Small buffer for immediate execution
                "source": "spot_sell_immediate"
            })
            logger.info(f"SignalCreator: Created SPOT SELL immediate condition (current: {rsi})")

    return conditions


def _create_options_strategy_conditions(decision: str, technical_indicators: Dict[str, Any],
                                       current_price: float) -> List[Dict[str, Any]]:
    """Create appropriate conditions for options strategies."""
    print(f"DEBUG: _create_options_strategy_conditions called with decision='{decision}'")
    conditions = []

    if "IRON_CONDOR" in decision:
        # Iron condor: Always create signal if orchestrator decided on it
        # Use simple condition to validate strategy remains appropriate
        rsi = technical_indicators.get(RSI_14, 50)

        logger.info(f"SignalCreator: IRON_CONDOR - RSI={rsi}")

        # Create condition based on current RSI level
        if rsi < 40:  # Oversold - wait for recovery
            conditions.append({
                "indicator": RSI_14,
                "operator": ConditionOperator.GREATER_THAN,
                "threshold": 35.0,  # Exit oversold
                "source": "iron_condor_entry"
            })
            logger.info(f"SignalCreator: Created IRON_CONDOR condition - RSI > 35 (current: {rsi})")
        elif rsi > 60:  # Overbought - wait for pullback
            conditions.append({
                "indicator": RSI_14,
                "operator": ConditionOperator.LESS_THAN,
                "threshold": 65.0,  # Exit overbought
                "source": "iron_condor_entry"
            })
            logger.info(f"SignalCreator: Created IRON_CONDOR condition - RSI < 65 (current: {rsi})")
        else:  # Neutral RSI - good for iron condor
            conditions.append({
                "indicator": RSI_14,
                "operator": ConditionOperator.GREATER_THAN,
                "threshold": 45.0,  # Stay in neutral zone
                "source": "iron_condor_neutral"
            })
            logger.info(f"SignalCreator: Created IRON_CONDOR condition - RSI > 45 (current: {rsi})")

    elif "BULL_CALL_SPREAD" in decision:
        # Bull call spread: Enter when market shows bullish potential
        rsi = technical_indicators.get(RSI_14, 50)
        current_price_val = technical_indicators.get(CURRENT_PRICE, current_price or 0)

        # Always create signal for BULL_CALL_SPREAD if orchestrator decided on it
        # Use entry condition based on current market state
        if rsi < 40:  # RSI still oversold - wait for bounce
            conditions.append({
                "indicator": RSI_14,
                "operator": ConditionOperator.GREATER_THAN,
                "threshold": 35.0,  # Exit oversold territory
                "source": "bull_call_spread_entry"
            })
        else:  # RSI not oversold - enter on bullish momentum
            conditions.append({
                "indicator": CURRENT_PRICE,
                "operator": ConditionOperator.GREATER_THAN,
                "threshold": current_price_val * 0.995,  # 0.5% up move
                "source": "bull_call_spread_momentum"
            })

    elif "BEAR_PUT_SPREAD" in decision:
        # Bear put spread: Enter on bearish signals (RSI overbought, downtrend)
        trend = technical_indicators.get(TREND_DIRECTION, 'SIDEWAYS')
        rsi = technical_indicators.get(RSI_14, 50)

        if trend == 'DOWN' and rsi > 60:  # Bearish trend with overbought RSI
            conditions.append({
                "indicator": RSI_14,
                "operator": ConditionOperator.GREATER_THAN,
                "threshold": 60.0,
                "source": "bear_put_entry"
            })

    # If no specific conditions created, use conservative default
    if not conditions and current_price:
        conditions.append({
            "indicator": CURRENT_PRICE,
            "operator": ConditionOperator.GREATER_THAN,
            "threshold": current_price * 0.995,  # 0.5% pullback for entry
            "source": "options_default"
        })

    return conditions


def create_signals_from_decision(
    analysis_result: Any,  # AnalysisResult
    instrument: str,
    technical_indicators: Optional[Dict[str, Any]] = None,
    current_price: Optional[float] = None,
    strategy_config: Optional[Dict[str, Any]] = None,
    redis_client: Optional[Any] = None
) -> List[TradingCondition]:
    """Create TradingCondition signals from orchestrator AnalysisResult.
    
    Args:
        analysis_result: AnalysisResult from orchestrator.run_cycle()
        instrument: Trading instrument (e.g., "BANKNIFTY")
        technical_indicators: Current technical indicator values (optional)
        current_price: Current market price (optional)
        strategy_config: Strategy configuration for options trades (optional)
        
    Returns:
        List of TradingCondition objects ready for monitoring
    """
    signals = []

    decision = analysis_result.decision.upper()
    confidence = analysis_result.confidence or 0.5
    details = analysis_result.details or {}

    # Ensure details is a dict (handle case where it might be a string or other type)
    if not isinstance(details, dict):
        logger.warning(f"details is not a dict, got {type(details)}: {details}")
        details = {}

    reasoning = details.get("reasoning", "") or details.get("reasoning_text", "") or ""

    # 1) Prefer structured signals (judge/agent produced) if present.
    structured = _extract_structured_signals(details)
    if structured:
        # Determine default validity
        default_valid_minutes = 15
        try:
            if details.get("valid_for_minutes") is not None:
                default_valid_minutes = int(details.get("valid_for_minutes"))
        except Exception:
            default_valid_minutes = 15

        for spec in structured:
            sig = _create_signal_from_spec(
                spec=spec,
                instrument=instrument,
                default_confidence=float(confidence) if confidence is not None else 0.5,
                default_valid_minutes=default_valid_minutes,
                current_price=current_price,
            )
            if sig is not None:
                signals.append(sig)

        if signals:
            for s in signals:
                logger.info(
                    f"Created structured signal {s.condition_id}: {s.action} {s.instrument} when "
                    f"{s.indicator} {s.operator.value} {s.threshold}"
                )
            return signals
    
    # Skip HOLD decisions
    if decision == "HOLD" or decision == "ERROR":
        logger.debug(f"Skipping signal creation for {decision} decision")
        return signals
    
    # Extract entry_conditions safely (handle both dict and string cases)
    entry_conditions = details.get("entry_conditions", {})
    if isinstance(entry_conditions, str):
        # If entry_conditions is a string, try to parse it or treat as empty dict
        logger.debug(f"entry_conditions is a string: {entry_conditions}")
        entry_conditions = {}
    elif not isinstance(entry_conditions, dict):
        entry_conditions = {}
    
    # Extract entry price if available
    entry_price = details.get("entry_price") or entry_conditions.get("entry_price") or current_price

    # Determine strategy type
    strategy_type = "OPTIONS" if any(x in decision for x in ["CALL", "PUT", "IRON_CONDOR", "SPREAD"]) else "SPOT"
    logger.info(f"SignalCreator: Decision '{decision}' -> Strategy type: {strategy_type}, technical_indicators available: {technical_indicators is not None}")

    # Extract stop loss and take profit from details
    stop_loss = details.get("stop_loss") or entry_conditions.get("stop_loss")
    take_profit = details.get("take_profit") or entry_conditions.get("take_profit")

    # For options strategies, set conservative risk management if not specified
    if strategy_type == "OPTIONS":
        if not stop_loss and current_price:
            # Options strategies: stop loss at 20% loss on premium paid
            stop_loss = current_price * 0.8 if "BUY" in decision else current_price * 1.2
        if not take_profit and current_price:
            # Take profit at 50% gain on premium
            take_profit = current_price * 1.5 if "BUY" in decision else current_price * 0.5

    # Extract conditions from reasoning (default approach)
    parsed_conditions = extract_conditions_from_reasoning(reasoning, current_price)

    # For options strategies, use specific market condition logic
    if strategy_type == "OPTIONS" and technical_indicators is not None:
        options_conditions = _create_options_strategy_conditions(
            decision, technical_indicators, current_price or 0
        )
        if options_conditions:
            parsed_conditions = options_conditions
            logger.info(f"Using {len(parsed_conditions)} specific conditions for {decision} strategy")
    # For spot trading strategies, create basic conditions if none extracted from reasoning
    elif strategy_type == "SPOT" and not parsed_conditions and technical_indicators is not None:
        spot_conditions = _create_spot_trading_conditions(
            decision, technical_indicators, current_price or 0
        )
        if spot_conditions:
            parsed_conditions = spot_conditions
            logger.info(f"Using {len(parsed_conditions)} spot trading conditions for {decision} strategy")

    # Validate signal creation requirements
    logger.info(f"Final parsed_conditions check: {len(parsed_conditions) if parsed_conditions else 0} conditions")
    if not parsed_conditions:
        logger.warning(f"No conditions found for {decision} signal - skipping creation")
        return signals

    # For options strategies, require at least one meaningful condition
    if strategy_type == "OPTIONS" and len(parsed_conditions) == 1:
        primary_condition = parsed_conditions[0]
        if (primary_condition.get('indicator') == CURRENT_PRICE and
            primary_condition.get('source') == 'options_default'):
            logger.warning(f"Options strategy {decision} only has default immediate condition - skipping")
            return signals

    # Determine execution mode: if we have explicit parsed conditions -> CONDITIONAL, else IMMEDIATE
    execution_mode = 'CONDITIONAL' if parsed_conditions else 'IMMEDIATE'

    # Attach parsed condition normalized forms for metadata
    normalized_conditions = []
    for cond in parsed_conditions:
        normalized_conditions.append({
            'indicator': cond.get('indicator'),
            'operator': cond.get('operator').value if hasattr(cond.get('operator'), 'value') else str(cond.get('operator')),
            'threshold': cond.get('threshold'),
            'source': cond.get('source')
        })

    
    # Validate and adjust thresholds for current_price conditions
    if parsed_conditions and current_price and current_price > 0:
        for cond in parsed_conditions:
            if cond.get("indicator") == CURRENT_PRICE and cond.get("threshold") is not None:
                threshold = float(cond["threshold"])
                if threshold < current_price * 0.9:
                    old_threshold = threshold
                    cond["threshold"] = current_price * 0.99
                    logger.info(f"Adjusted threshold from {old_threshold} to {cond['threshold']} for current_price condition (too low)")
                elif threshold > current_price * 1.1:
                    old_threshold = threshold
                    cond["threshold"] = current_price * 1.01
                    logger.info(f"Adjusted threshold from {old_threshold} to {cond['threshold']} for current_price condition (too high)")
    
    # If no conditions parsed, create default condition based on decision
    if not parsed_conditions:
        # Default condition: Execute immediately on next tick (price > 0)
        if current_price and current_price > 0:
            parsed_conditions = [{
                "indicator": CURRENT_PRICE,
                "operator": ConditionOperator.GREATER_THAN,
                "threshold": current_price * 0.99,  # 1% below current (triggers immediately)
                "source": "default"
            }]
        else:
            # Fallback: Use RSI oversold/overbought based on decision
            if "BUY" in decision:
                parsed_conditions = [{
                    "indicator": "rsi_14",
                    "operator": ConditionOperator.LESS_THAN,
                    "threshold": 35.0,  # Oversold condition
                    "source": "default_buy"
                }]
            elif "SELL" in decision:
                parsed_conditions = [{
                    "indicator": "rsi_14",
                    "operator": ConditionOperator.GREATER_THAN,
                    "threshold": 65.0,  # Overbought condition
                    "source": "default_sell"
                }]
    
    # Create signal for each primary condition
    # Primary condition is the first one; others become additional_conditions
    # DEBUG: show parsed conditions
    # print debug only in test runs where stdout is visible
    try:
        logger.debug("parsed_conditions: %s", parsed_conditions)
    except Exception:
        pass

    if parsed_conditions:
        logger.debug('entering creation block')
        primary_condition = parsed_conditions[0]
        logger.debug('primary_condition: %s', primary_condition)
        additional_conditions = []
        
        # Convert additional conditions to proper format
        for cond in parsed_conditions[1:]:
            logger.debug('extra cond: %s', cond)
            additional_conditions.append({
                "indicator": cond.get("indicator", ""),
                "operator": cond.get("operator").value if hasattr(cond.get("operator"), "value") else str(cond.get("operator")),
                "threshold": cond.get("threshold", 0)
            })
        logger.debug('after extra loop')
        # Determine action (BUY, SELL, or strategy name for options)
        if strategy_type == "OPTIONS":
            action = decision  # e.g., "IRON_CONDOR", "BUY_CALL", etc.
        else:
            action = "SELL" if "SELL" in decision or "PUT" in decision else "BUY"
        
        # Calculate position size based on confidence
        position_size = 1.0
        if confidence > 0.8:
            position_size = 2.0
        elif confidence > 0.6:
            position_size = 1.5
        elif confidence < 0.4:
            position_size = 0.5
        
        # Recompute reason_hash now that 'action' is known
        import hashlib
        try:
            reason_hash_src = json.dumps({
                'action': action,
                'instrument': instrument,
                'conditions': normalized_conditions,
                'reasoning': reasoning or '' ,
                'entry_price': entry_price
            }, sort_keys=True)
            reason_hash = hashlib.sha1(reason_hash_src.encode('utf-8')).hexdigest()[:12]
        except Exception:
            reason_hash = None

    # Prepare expiry and validity window
    now = datetime.now()
    # Resolution order: details.valid_for_minutes -> strategy_config.signal_valid_minutes -> default 15
    valid_minutes = None
    try:
        valid_minutes = int(details.get('valid_for_minutes')) if details and isinstance(details, dict) and details.get('valid_for_minutes') is not None else None
    except Exception:
        valid_minutes = None
    if not valid_minutes and strategy_config and isinstance(strategy_config, dict):
        try:
            valid_minutes = int(strategy_config.get('signal_valid_minutes')) if strategy_config.get('signal_valid_minutes') is not None else None
        except Exception:
            valid_minutes = None
    if not valid_minutes:
        valid_minutes = 15  # default one orchestrator cycle

    expiry_time = now + timedelta(minutes=valid_minutes)
    # Ensure expiry does not go beyond market close (3:30 PM)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if expiry_time > market_close:
        expiry_time = market_close

    # Prepare metadata (include options strategy summary if present in details)
    metadata: Dict[str, Any] = {"signal_source": "orchestrator_decision"}
    if details and isinstance(details, dict) and details.get('options_strategy'):
        osum = details.get('options_strategy')
        metadata['options_strategy_summary'] = {
            'strategy_type': osum.get('strategy_type'),
            'underlying': osum.get('underlying'),
            'expiry': osum.get('expiry'),
            'legs_count': len(osum.get('legs', [])),
            'max_profit': osum.get('max_profit'),
            'max_loss': osum.get('max_loss'),
            'margin_required': osum.get('margin_required')
        }
    
    # Include full options strategy details from AnalysisResult if present
    if hasattr(analysis_result, 'options_strategy') and analysis_result.options_strategy:
        metadata['options_strategy'] = analysis_result.options_strategy

    # Attach execution metadata
    metadata['execution_mode'] = execution_mode
    metadata['parsed_conditions'] = normalized_conditions
    # reason_hash may be computed later after action - leave placeholder for now
    if 'reason_hash' not in metadata:
        metadata['reason_hash'] = None


    # Now that reason_hash is computed, set it in metadata as well
    if reason_hash:
        metadata['reason_hash'] = reason_hash

    # Determine action-specific condition id, etc.
    condition_id = f"{instrument}_{decision}_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
    logger.debug('pre-signal: %s', {'action': action, 'position_size': position_size, 'condition_id': condition_id})

    # Create TradingCondition
    signal = TradingCondition(
        condition_id=condition_id,
        instrument=instrument,
        indicator=primary_condition.get("indicator", "rsi_14"),
        operator=primary_condition.get("operator", ConditionOperator.GREATER_THAN),
        threshold=primary_condition.get("threshold", 0.0),
        action=action,
        strategy_type=strategy_type,
        position_size=position_size,
        confidence=confidence,
        stop_loss=stop_loss,
        take_profit=take_profit,
        entry_price=entry_price,
        additional_conditions=additional_conditions,
        metadata=metadata,
        execution_mode=execution_mode,
        reason_hash=reason_hash if reason_hash else metadata.get('reason_hash'),
        parsed_conditions=normalized_conditions,
        expires_at=expiry_time.isoformat(),
        is_active=True
    )

    signals.append(signal)
    logger.debug('appended signal: %s', condition_id)
    logger.info(
        f"Created signal {condition_id}: {action} {instrument} when "
        f"{signal.indicator} {signal.operator.value} {signal.threshold}"
    )
    return signals


async def save_signal_to_mongodb(
    signal: TradingCondition,
    mongo_db: Any,
    collection_name: str = "signals"
) -> str:
    """Save TradingCondition signal to MongoDB.
    
    Args:
        signal: TradingCondition to save
        mongo_db: MongoDB database instance
        collection_name: Collection name (default: "signals")
        
    Returns:
        MongoDB document ID as string
    """
    try:
        collection = mongo_db[collection_name]
        
        # Get system context for run isolation
        from .system_context import get_system_context
        system_context = get_system_context()

        # Convert TradingCondition to dict, handling enums and special fields
        signal_dict = {
            "condition_id": signal.condition_id,
            "instrument": signal.instrument,
            "indicator": signal.indicator,
            "operator": signal.operator.value if hasattr(signal.operator, "value") else str(signal.operator),
            "threshold": signal.threshold,
            "action": signal.action,
            "strategy_type": signal.strategy_type,
            "position_size": signal.position_size,
            "confidence": signal.confidence,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "entry_price": signal.entry_price,
            "execution_mode": signal.execution_mode,
            "reason_hash": signal.reason_hash,
            "parsed_conditions": signal.parsed_conditions,
            "additional_conditions": signal.additional_conditions,
            "created_at": signal.created_at,
            "expires_at": signal.expires_at,
            "triggered_at": signal.triggered_at,
            "is_active": signal.is_active,
            "status": "pending",  # pending, triggered, expired, executed, cancelled
            "created_from": "orchestrator",
            "metadata": signal.metadata if hasattr(signal, 'metadata') and isinstance(signal.metadata, dict) else {"signal_source": "orchestrator_decision"}
        }

        # Add system context metadata for run isolation
        signal_dict.update(system_context.get_metadata())

        # Populate options strategy details if this is an OPTIONS strategy
        if signal_dict.get("strategy_type") == "OPTIONS":
            logger.error(f"DEBUG: Generating options strategy for {signal_dict['action']}")
            options_strategy = await _generate_options_strategy(signal_dict["action"], signal_dict["instrument"])
            logger.error(f"DEBUG: Generated options_strategy: {options_strategy}")
            if options_strategy:
                signal_dict["options_strategy"] = options_strategy
                logger.error(f"DEBUG: Saved options_strategy to signal_dict")
            else:
                logger.error(f"DEBUG: No options_strategy generated")

        # Check for recent similar pending signal to avoid duplicates (within dedupe window)
        # Reduced from 30 minutes to 5 minutes for more responsive trading
        try:
            dedupe_minutes = int(os.getenv('SIGNAL_DEDUPE_MINUTES', '5'))
            # Include run isolation in deduplication to prevent cross-run conflicts
            run_filter = system_context.get_db_filter()
            recent = collection.find_one({
                "instrument": signal.instrument,
                "action": signal.action,
                "status": "pending",
                "is_active": True,
                **run_filter  # Only check for duplicates within the same run
            }, sort=[("created_at", -1)])
            if recent:
                try:
                    recent_created = datetime.fromisoformat(recent.get('created_at'))
                except Exception:
                    recent_created = None
                if recent_created and recent_created >= (datetime.now() - timedelta(minutes=dedupe_minutes)):
                    logger.info(f"Found recent pending signal {recent.get('condition_id')} - skipping duplicate creation")
                    existing_id = str(recent.get('_id')) if recent.get('_id') is not None else recent.get('condition_id')
                    return existing_id
        except Exception:
            # If dedupe check fails for any reason, proceed with insertion
            pass

        result = collection.insert_one(signal_dict)
        signal_id = str(result.inserted_id)
        
        # Publish signal to Redis pub/sub for real-time updates (Socket.IO, UI, etc.)
        try:
            import redis
            import json
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

            # Test Redis connection
            redis_client.ping()
            logger.info("Redis connection test successful")

            # Add signal_id to signal_dict for pub/sub
            signal_dict["signal_id"] = str(signal_id)  # Convert ObjectId to string

            # Ensure all values are JSON serializable
            def make_json_serializable(obj):
                # First handle numpy types
                from .api_service import convert_numpy_types
                obj = convert_numpy_types(obj)

                if isinstance(obj, dict):
                    return {k: make_json_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [make_json_serializable(item) for item in obj]
                elif hasattr(obj, '__dict__'):
                    # Convert objects to dict
                    return str(obj)
                elif hasattr(obj, 'isoformat'):  # datetime objects
                    return obj.isoformat()
                elif str(type(obj)).endswith("ObjectId'>"):  # MongoDB ObjectId
                    return str(obj)
                else:
                    return obj

            # Check for recent similar pending signal to avoid duplicates (within dedupe window)
            try:
                dedupe_minutes = int(os.getenv('SIGNAL_DEDUPE_MINUTES', '5'))
                # Prefer reason_hash-based dedupe if available
                rh = signal_dict.get('reason_hash') or (signal_dict.get('metadata') or {}).get('reason_hash')
                if rh:
                    recent = collection.find_one({
                        "instrument": signal.instrument,
                        "action": signal.action,
                        "reason_hash": rh,
                        "status": "pending",
                        "is_active": True
                    }, sort=[("created_at", -1)])
                    if recent:
                        try:
                            recent_created = datetime.fromisoformat(recent.get('created_at'))
                        except Exception:
                            recent_created = None
                        if recent_created and recent_created >= (datetime.now() - timedelta(minutes=dedupe_minutes)):
                            logger.info(f"Found recent pending signal with same reason_hash {recent.get('condition_id')} - skipping duplicate creation")
                            existing_id = str(recent.get('_id')) if recent.get('_id') is not None else recent.get('condition_id')
                            return existing_id

                # Fallback dedupe by instrument+action (older behavior)
                recent = collection.find_one({
                    "instrument": signal.instrument,
                    "action": signal.action,
                    "status": "pending",
                    "is_active": True
                }, sort=[("created_at", -1)])
                if recent:
                    try:
                        recent_created = datetime.fromisoformat(recent.get('created_at'))
                    except Exception:
                        recent_created = None
                    if recent_created and recent_created >= (datetime.now() - timedelta(minutes=dedupe_minutes)):
                        logger.info(f"Found recent pending signal {recent.get('condition_id')} - skipping duplicate creation")
                        existing_id = str(recent.get('_id')) if recent.get('_id') is not None else recent.get('condition_id')
                        return existing_id
            except Exception:
                # If dedupe check fails for any reason, proceed with insertion
                pass

            # Make signal_dict JSON serializable
            json_signal_dict = make_json_serializable(signal_dict)

            # Debug: Print signal_dict to see what's causing JSON error
            logger.info(f"DEBUG signal_dict keys: {list(signal_dict.keys())}")
            logger.info(f"DEBUG signal_id type: {type(signal_dict.get('signal_id'))}")

            # Publish to Redis pub/sub
            logger.info(f"📊 Publishing signal to Redis channels: engine:signal, engine:signal:{signal.instrument}")
            result1 = redis_client.publish("engine:signal", json.dumps(json_signal_dict))
            result2 = redis_client.publish(f"engine:signal:{signal.instrument}", json.dumps(json_signal_dict))
            logger.info(f"[OK] Published signal {signal.condition_id} to Redis pub/sub: {result1} + {result2} subscribers")
        except Exception as pub_err:
            # Don't fail if Redis pub/sub fails
            logger.error(f"❌ Failed to publish signal to Redis pub/sub: {pub_err}", exc_info=True)
        
        logger.info(f"Saved signal {signal.condition_id} to MongoDB with ID {signal_id}")
        return signal_id
        
    except Exception as e:
        logger.error(f"Failed to save signal {signal.condition_id} to MongoDB: {e}", exc_info=True)
        raise


async def delete_pending_signals(
    mongo_db: Any,
    instrument: Optional[str] = None,
    collection_name: str = "signals"
) -> int:
    """Delete all pending (non-executed) signals from MongoDB.
    
    This is called at the start of each orchestrator cycle to clear old signals.
    
    Args:
        mongo_db: MongoDB database instance
        instrument: Optional instrument filter (if None, deletes all instruments)
        collection_name: Collection name (default: "signals")
        
    Returns:
        Number of signals deleted
    """
    try:
        collection = mongo_db[collection_name]
        
        # Build query: delete pending signals that are not executed
        query = {
            "status": {"$in": ["pending", "expired"]},
            "is_active": True
        }
        
        if instrument:
            query["instrument"] = instrument.upper()
        
        result = collection.delete_many(query)
        deleted_count = result.deleted_count
        
        logger.info(f"Deleted {deleted_count} pending signals from MongoDB" + (f" for {instrument}" if instrument else ""))
        return deleted_count
        
    except Exception as e:
        logger.error(f"Failed to delete pending signals: {e}", exc_info=True)
        return 0


async def cancel_pending_signals(
    mongo_db: Any,
    instrument: Optional[str] = None,
    collection_name: str = "signals",
    reason: str = "cycle_invalidation",
) -> int:
    """Cancel (invalidate) all pending signals for an instrument.

    This is preferred over deleting: it preserves history while ensuring the system
    treats previous-cycle intents as no longer actionable.

    It marks matching documents:
      - status = "cancelled"
      - is_active = False
      - cancelled_at = now
      - cancel_reason = reason

    Args:
        mongo_db: MongoDB database instance
        instrument: Optional instrument filter (if None, cancels all instruments)
        collection_name: Collection name (default: "signals")
        reason: Reason for cancellation (stored for audit)

    Returns:
        Number of signals cancelled
    """
    try:
        collection = mongo_db[collection_name]
        query: Dict[str, Any] = {
            "status": {"$in": ["pending", "expired"]},
            "is_active": True,
        }
        if instrument:
            query["instrument"] = instrument.upper()

        update = {
            "$set": {
                "status": "cancelled",
                "is_active": False,
                "cancelled_at": datetime.now().isoformat(),
                "cancel_reason": reason,
            }
        }

        # Some test fakes won't implement update_many; in that case, fall back to delete.
        if hasattr(collection, "update_many"):
            res = collection.update_many(query, update)
            cancelled_count = getattr(res, "modified_count", 0) or 0
            logger.info(
                f"Cancelled {cancelled_count} pending signals"
                + (f" for {instrument}" if instrument else "")
            )
            return cancelled_count

        # Fallback
        return await delete_pending_signals(mongo_db, instrument=instrument, collection_name=collection_name)
    except Exception as e:
        logger.error(f"Failed to cancel pending signals: {e}", exc_info=True)
        return 0


async def sync_signals_to_monitor(
    mongo_db: Any,
    signal_monitor: Any,  # SignalMonitor instance
    instrument: Optional[str] = None,
    collection_name: str = "signals"
) -> int:
    """Sync MongoDB signals to SignalMonitor active signals.
    
    Reads all active signals from MongoDB and adds them to SignalMonitor.
    Called on service startup and after signal creation.
    
    Args:
        mongo_db: MongoDB database instance
        signal_monitor: SignalMonitor instance
        instrument: Optional instrument filter
        collection_name: Collection name (default: "signals")
        
    Returns:
        Number of signals synced
    """
    try:
        collection = mongo_db[collection_name]
        
        # Query active pending and monitoring signals
        query = {
            "status": {"$in": ["pending", "monitoring"]},
            "is_active": True
        }
        
        if instrument:
            query["instrument"] = instrument.upper()
        
        signals = list(collection.find(query))
        
        synced_count = 0
        for signal_doc in signals:
            try:
                # Convert MongoDB document back to TradingCondition
                condition = _convert_doc_to_trading_condition(signal_doc)
                if condition:
                    signal_monitor.add_signal(condition)
                    synced_count += 1
            except Exception as e:
                logger.warning(f"Failed to sync signal {signal_doc.get('condition_id')}: {e}")
        
        logger.info(f"Synced {synced_count} signals to SignalMonitor" + (f" for {instrument}" if instrument else ""))
        return synced_count
        
    except Exception as e:
        logger.error(f"Failed to sync signals to SignalMonitor: {e}", exc_info=True)
        return 0


def _convert_doc_to_trading_condition(signal_doc: Dict[str, Any]) -> Optional[TradingCondition]:
    """Convert MongoDB document to TradingCondition object.
    
    Args:
        signal_doc: MongoDB document dictionary
        
    Returns:
        TradingCondition object or None if conversion fails
    """
    try:
        # Convert operator string back to ConditionOperator enum
        operator_str = signal_doc.get("operator", ">")
        operator_map = {
            ">": ConditionOperator.GREATER_THAN,
            "<": ConditionOperator.LESS_THAN,
            ">=": ConditionOperator.GREATER_EQUAL,
            "<=": ConditionOperator.LESS_EQUAL,
            "==": ConditionOperator.EQUAL,
            "crosses_above": ConditionOperator.CROSSES_ABOVE,
            "crosses_below": ConditionOperator.CROSSES_BELOW,
        }
        operator = operator_map.get(operator_str, ConditionOperator.GREATER_THAN)
        
        condition = TradingCondition(
            condition_id=signal_doc.get("condition_id", ""),
            instrument=signal_doc.get("instrument", ""),
            indicator=signal_doc.get("indicator", "rsi_14"),
            operator=operator,
            threshold=float(signal_doc.get("threshold", 0)),
            action=signal_doc.get("action", "BUY"),
            strategy_type=signal_doc.get("strategy_type", "SPOT"),
            position_size=float(signal_doc.get("position_size", 1.0)),
            confidence=float(signal_doc.get("confidence", 0.5)),
            stop_loss=signal_doc.get("stop_loss"),
            take_profit=signal_doc.get("take_profit"),
            entry_price=signal_doc.get("entry_price"),
            execution_mode=signal_doc.get("execution_mode"),
            reason_hash=signal_doc.get("reason_hash"),
            parsed_conditions=signal_doc.get("parsed_conditions", []),
            additional_conditions=signal_doc.get("additional_conditions", []),
            created_at=signal_doc.get("created_at", datetime.now().isoformat()),
            expires_at=signal_doc.get("expires_at"),
            triggered_at=signal_doc.get("triggered_at"),
            is_active=bool(signal_doc.get("is_active", True))
        )
        
        return condition
        
    except Exception as e:
        logger.error(f"Failed to convert MongoDB doc to TradingCondition: {e}", exc_info=True)
        return None


async def mark_signal_status(signal_id: str, status: str, mongo_db: Any = None, extra: Optional[Dict[str, Any]] = None) -> bool:
    """Update a signal's status in MongoDB and publish a lightweight update to Redis.

    Args:
        signal_id: condition_id or Mongo _id
        status: One of 'pending', 'triggered', 'executed', 'expired', 'cancelled'
        mongo_db: Optional MongoDB database instance; if None, `get_mongo_client()` will be used
        extra: Optional dictionary of extra fields to set on the document

    Returns:
        True if update succeeded, False otherwise
    """
    try:
        # Lazy import to avoid circular imports
        from .api_service import get_redis_client, get_mongo_client
    except Exception:
        # api_service may not be available in some test contexts
        get_redis_client = None
        get_mongo_client = None

    try:
        # Resolve mongo_db
        if mongo_db is None:
            if get_mongo_client is None:
                return False
            mongo_client = get_mongo_client()
            db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
            mongo_db = mongo_client[db_name]

        collection = mongo_db["signals"]

        # Try ObjectId first
        query = None
        try:
            from bson import ObjectId
            query = {"_id": ObjectId(signal_id)}
        except Exception:
            query = {"condition_id": signal_id}

        update_fields = {"status": status}
        if extra and isinstance(extra, dict):
            update_fields.update(extra)

        update = {"$set": update_fields}
        collection.update_one(query, update)

        # Publish update to Redis for UI + gateway
        try:
            if get_redis_client:
                redis_client = get_redis_client()
                payload = {
                    "signal_id": signal_id,
                    "status": status,
                    **({k: v for k, v in (extra or {}).items()} if extra else {})
                }
                import json
                redis_client.publish("engine:signal", json.dumps(payload))
                # If we can get instrument from the doc, also publish instrument specific channel
                try:
                    doc = collection.find_one(query)
                    instr = doc.get("instrument") if doc else None
                    if instr:
                        redis_client.publish(f"engine:signal:{instr}", json.dumps(payload))
                except Exception:
                    # best-effort, don't fail
                    pass
        except Exception:
            pass

        return True
    except Exception as e:
        logger.error(f"Failed to update signal status {signal_id} to {status}: {e}", exc_info=True)
        return False
