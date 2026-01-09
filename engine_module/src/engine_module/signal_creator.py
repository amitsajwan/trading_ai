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
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import asdict

from .signal_monitor import TradingCondition, ConditionOperator

logger = logging.getLogger(__name__)


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


def create_signals_from_decision(
    analysis_result: Any,  # AnalysisResult
    instrument: str,
    technical_indicators: Optional[Dict[str, Any]] = None,
    current_price: Optional[float] = None,
    strategy_config: Optional[Dict[str, Any]] = None
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
    
    # Extract stop loss and take profit from details
    stop_loss = details.get("stop_loss") or entry_conditions.get("stop_loss")
    take_profit = details.get("take_profit") or entry_conditions.get("take_profit")
    
    # Extract entry price if available
    entry_price = details.get("entry_price") or entry_conditions.get("entry_price") or current_price
    
    # Determine strategy type
    strategy_type = "OPTIONS" if any(x in decision for x in ["CALL", "PUT", "IRON_CONDOR", "SPREAD"]) else "SPOT"
    
    # Extract conditions from reasoning
    parsed_conditions = extract_conditions_from_reasoning(reasoning, current_price)
    
    # If no conditions parsed, create default condition based on decision
    if not parsed_conditions:
        # Default condition: Execute immediately on next tick (price > 0)
        if current_price and current_price > 0:
            parsed_conditions = [{
                "indicator": "current_price",
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
    if parsed_conditions:
        primary_condition = parsed_conditions[0]
        additional_conditions = []
        
        # Convert additional conditions to proper format
        for cond in parsed_conditions[1:]:
            additional_conditions.append({
                "indicator": cond.get("indicator", ""),
                "operator": cond.get("operator").value if hasattr(cond.get("operator"), "value") else str(cond.get("operator")),
                "threshold": cond.get("threshold", 0)
            })
        
        # Determine action (BUY or SELL)
        action = "BUY"
        if "SELL" in decision or "PUT" in decision:
            action = "SELL"
        elif "BUY" in decision:
            action = "BUY"
        
        # Calculate position size based on confidence
        position_size = 1.0
        if confidence > 0.8:
            position_size = 2.0
        elif confidence > 0.6:
            position_size = 1.5
        elif confidence < 0.4:
            position_size = 0.5
        
        # Generate unique condition ID
        condition_id = f"{instrument}_{decision}_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
        
        # Set expiry (default: cycle interval minutes or 15 minutes)
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
            additional_conditions=additional_conditions,
            metadata=metadata,
            expires_at=expiry_time.isoformat(),
            is_active=True
        )
        
        signals.append(signal)
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
            "additional_conditions": signal.additional_conditions,
            "created_at": signal.created_at,
            "expires_at": signal.expires_at,
            "triggered_at": signal.triggered_at,
            "is_active": signal.is_active,
            "status": "pending",  # pending, triggered, expired, executed, cancelled
            "created_from": "orchestrator",
            "metadata": signal.metadata if hasattr(signal, 'metadata') and isinstance(signal.metadata, dict) else {"signal_source": "orchestrator_decision"}
        }
        
        result = collection.insert_one(signal_dict)
        signal_id = str(result.inserted_id)
        
        # Publish signal to Redis pub/sub for real-time updates (Socket.IO, UI, etc.)
        try:
            import redis
            import json
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
            
            # Add signal_id to signal_dict for pub/sub
            signal_dict["signal_id"] = signal_id
            
            # Publish to Redis pub/sub
            redis_client.publish("engine:signal", json.dumps(signal_dict))
            redis_client.publish(f"engine:signal:{signal.instrument}", json.dumps(signal_dict))
            logger.debug(f"Published signal {signal.condition_id} to Redis pub/sub")
        except Exception as pub_err:
            # Don't fail if Redis pub/sub fails
            logger.debug(f"Failed to publish signal to Redis pub/sub: {pub_err}")
        
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
        
        # Query active pending signals
        query = {
            "status": "pending",
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
