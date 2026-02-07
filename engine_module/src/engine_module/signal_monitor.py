"""Real-time Signal Monitor - Converts conditional signals to trades.

This component monitors technical indicators in REAL-TIME and triggers trades
when conditions are met, rather than waiting for the next orchestrator cycle.

Example Use Case:
    Agent Analysis (15-min cycle): "BUY when RSI crosses above 32"
    Signal Monitor: Watches RSI on EVERY tick, executes trade when RSI > 32

Architecture:
    TechnicalIndicatorsService → updates on every tick (100-200ms)
                ↓
    SignalMonitor → checks active signals against latest indicators
                ↓
    Trade Execution → when condition met
"""

import asyncio
import logging
import sys
import os
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum

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

logger = logging.getLogger(__name__)


class ConditionOperator(Enum):
    """Comparison operators for conditions."""
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    EQUAL = "=="
    CROSSES_ABOVE = "crosses_above"  # Value crosses from below to above threshold
    CROSSES_BELOW = "crosses_below"  # Value crosses from above to below threshold


@dataclass
class TradingCondition:
    """Represents a conditional trading signal.
    
    Example: "BUY when RSI > 32"
    - indicator: "rsi_14"
    - operator: GREATER_THAN
    - threshold: 32
    - action: "BUY"
    """
    
    condition_id: str
    instrument: str
    indicator: str  # e.g., "rsi_14", "sma_20", "macd_value"
    operator: ConditionOperator
    threshold: float
    action: str  # "BUY" or "SELL"
    
    # Optional fields
    strategy_type: str = "SPOT"  # or "OPTIONS"
    position_size: float = 1.0
    confidence: float = 0.75
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    entry_price: Optional[float] = None
    
    # Multi-condition support (AND logic)
    additional_conditions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Execution and provenance
    execution_mode: Optional[str] = None  # 'IMMEDIATE' or 'CONDITIONAL'
    reason_hash: Optional[str] = None
    parsed_conditions: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None  # Auto-cancel after this time
    triggered_at: Optional[str] = None
    is_active: bool = True
    
    # Previous value for cross detection
    _previous_value: Optional[float] = None


@dataclass
class SignalTriggerEvent:
    """Event triggered when a signal condition is met."""
    
    condition_id: str
    instrument: str
    action: str  # BUY/SELL
    triggered_at: str
    
    # Indicator values at trigger
    indicator_name: str
    indicator_value: float
    threshold: float
    
    # Trade parameters
    current_price: float
    position_size: float
    confidence: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy_type: str = "SPOT"
    
    # Context
    all_indicators: Dict[str, Any] = field(default_factory=dict)


class SignalMonitor:
    """Monitors technical indicators in real-time and triggers trades when conditions are met.
    
    This component bridges the gap between periodic agent analysis (15-min cycles)
    and real-time trade execution (tick-by-tick).
    
    Usage:
        monitor = SignalMonitor()
        
        # Agent creates conditional signal during 15-min analysis
        condition = TradingCondition(
            condition_id="rsi_oversold_buy_001",
            instrument="BANKNIFTY",
            indicator="rsi_14",
            operator=ConditionOperator.GREATER_THAN,
            threshold=32,
            action="BUY",
            position_size=1.0,
            stop_loss=44900,
            take_profit=45300
        )
        
        # Register signal with monitor
        monitor.add_signal(condition)
        
        # Monitor checks on every tick (automatic via service integration)
        # When RSI crosses 32, monitor triggers trade execution
    """
    
    def __init__(self, technical_service=None):
        """Initialize optimized signal monitor.

        Args:
            technical_service: Optional TechnicalIndicatorsService instance.
                              If None, will fetch via get_technical_service()
        """
        self._active_signals: Dict[str, TradingCondition] = {}
        self._triggered_signals: List[SignalTriggerEvent] = []
        self._technical_service = technical_service

        # Redis client for persisted previous values
        try:
            from engine_module.api_service import get_redis_client
            # Use get_redis_client if available; tests sometimes monkeypatch this function
            self._redis_client = get_redis_client() if callable(get_redis_client) else None
        except Exception:
            self._redis_client = None

        # Callbacks for trade execution
        self._on_signal_triggered: Optional[Callable] = None

        # Performance statistics
        self._stats_signals_checked = 0
        self._stats_signals_triggered = 0
        self._stats_last_reset = datetime.now()

        logger.info("Optimized SignalMonitor initialized")
    
    def add_signal(self, condition: TradingCondition) -> str:
        """Add a conditional signal to monitor.
        
        Args:
            condition: Trading condition to monitor
            
        Returns:
            condition_id for tracking
        """
        self._active_signals[condition.condition_id] = condition
        logger.info(
            f"Added signal {condition.condition_id}: "
            f"{condition.action} {condition.instrument} when "
            f"{condition.indicator} {condition.operator.value} {condition.threshold}"
        )
        return condition.condition_id
    
    def remove_signal(self, condition_id: str) -> bool:
        """Remove a signal from monitoring.
        
        Args:
            condition_id: ID of condition to remove
            
        Returns:
            True if removed, False if not found
        """
        if condition_id in self._active_signals:
            del self._active_signals[condition_id]
            logger.info(f"Removed signal {condition_id}")
            return True
        return False

    def remove_signals_for_instrument(self, instrument: str) -> int:
        """Remove all active signals for an instrument.

        This is used to support the 15-min cadence lifecycle where a new cycle
        invalidates the previous signal set for the instrument.

        Args:
            instrument: Instrument whose signals should be removed

        Returns:
            Number of signals removed
        """
        if not instrument:
            return 0

        to_remove = [cid for cid, cond in self._active_signals.items() if cond.instrument == instrument]
        for cid in to_remove:
            try:
                del self._active_signals[cid]
            except Exception:
                pass
        if to_remove:
            logger.info(f"Removed {len(to_remove)} active signal(s) for instrument {instrument}")
        return len(to_remove)
    
    def get_active_signals(self, instrument: Optional[str] = None) -> List[TradingCondition]:
        """Get all active signals, optionally filtered by instrument.
        
        Args:
            instrument: Optional instrument filter
            
        Returns:
            List of active trading conditions
        """
        signals = list(self._active_signals.values())
        if instrument:
            signals = [s for s in signals if s.instrument == instrument]
        return signals
    
    def get_triggered_signals(self, limit: int = 100) -> List[SignalTriggerEvent]:
        """Get recently triggered signals.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of triggered signal events (most recent first)
        """
        return self._triggered_signals[-limit:][::-1]
    
    def set_execution_callback(self, callback: Callable[[SignalTriggerEvent], None]):
        """Set callback function to execute when signal triggers.
        
        Args:
            callback: Async function that takes SignalTriggerEvent and executes trade
            
        Example:
            async def execute_trade(event: SignalTriggerEvent):
                # Place order via broker API
                order = await broker.place_order(
                    instrument=event.instrument,
                    action=event.action,
                    quantity=event.position_size,
                    price=event.current_price
                )
            
            monitor.set_execution_callback(execute_trade)
        """
        self._on_signal_triggered = callback
        logger.info("Execution callback registered")
    
    async def check_signals(self, instrument: str) -> List[SignalTriggerEvent]:
        """Check all active signals for an instrument against latest indicators.
        
        This should be called on EVERY tick update (integrated with TechnicalIndicatorsService).
        
        Args:
            instrument: Instrument to check
            
        Returns:
            List of triggered events (if any)
        """
        # Get latest indicators from Redis
        from engine_module.redis_providers import RedisTechnicalDataProvider
        from engine_module.api_service import get_redis_client

        if self._technical_service is None:
            redis_client = get_redis_client()
            self._technical_service = RedisTechnicalDataProvider(redis_client)

        indicators_dict = await self._technical_service.get_indicators(instrument)
        if not indicators_dict:
            return []
        
        triggered_events = []
        
        # Check each active signal for this instrument
        signals_to_remove = []
        
        for condition_id, condition in list(self._active_signals.items()):
            if condition.instrument != instrument:
                continue
            
            if not condition.is_active:
                continue
            
            # Check if expired
            if condition.expires_at:
                current_time = get_current_time(self._redis_client)
                if current_time.isoformat() > condition.expires_at:
                    # Mark expired in MongoDB and publish update
                    try:
                        from .signal_creator import mark_signal_status
                        await mark_signal_status(condition.condition_id, "expired")
                    except Exception:
                        pass
                    signals_to_remove.append(condition_id)
                    logger.info(f"Signal {condition_id} expired")
                    continue
            
            # Evaluate condition
            triggered = self._evaluate_condition(condition, indicators_dict)
            
            if triggered:
                # Create trigger event
                event = SignalTriggerEvent(
                    condition_id=condition.condition_id,
                    instrument=condition.instrument,
                    action=condition.action,
                    triggered_at=datetime.now().isoformat(),
                    indicator_name=condition.indicator,
                    indicator_value=indicators_dict.get(condition.indicator, 0),
                    threshold=condition.threshold,
                    current_price=indicators_dict.get("current_price", 0),
                    position_size=condition.position_size,
                    confidence=condition.confidence,
                    stop_loss=condition.stop_loss,
                    take_profit=condition.take_profit,
                    strategy_type=condition.strategy_type,
                    all_indicators=indicators_dict
                )
                
                triggered_events.append(event)
                self._triggered_signals.append(event)
                
                # Mark condition as triggered
                condition.triggered_at = event.triggered_at
                condition.is_active = False
                signals_to_remove.append(condition_id)
                
                logger.info(
                    f"🔔 Signal triggered: {condition_id} - "
                    f"{condition.action} {condition.instrument} at "
                    f"{condition.indicator}={event.indicator_value:.2f} "
                    f"(threshold: {condition.threshold})"
                )

                # Mark status in DB and publish (best-effort)
                try:
                    from .signal_creator import mark_signal_status
                    await mark_signal_status(condition.condition_id, "triggered", extra={"triggered_at": event.triggered_at, "indicator_value": event.indicator_value})
                except Exception:
                    logger.debug("Failed to mark signal triggered in DB")
                
                # Execute callback if registered
                if self._on_signal_triggered:
                    try:
                        await self._on_signal_triggered(event)
                    except Exception as e:
                        logger.error(f"Error in execution callback: {e}")
        
        # Remove triggered/expired signals
        for condition_id in signals_to_remove:
            self.remove_signal(condition_id)
        
        return triggered_events

    def _create_trigger_event(self, condition: TradingCondition, indicators_dict: Dict[str, Any],
                             current_time: str) -> SignalTriggerEvent:
        """Optimized trigger event creation."""
        return SignalTriggerEvent(
            condition_id=condition.condition_id,
            instrument=condition.instrument,
            action=condition.action,
            triggered_at=current_time,
            indicator_name=condition.indicator,
            indicator_value=indicators_dict.get(condition.indicator, 0),
            threshold=condition.threshold,
            current_price=indicators_dict.get("current_price", 0),
            position_size=condition.position_size,
            confidence=condition.confidence,
            stop_loss=condition.stop_loss,
            take_profit=condition.take_profit,
            strategy_type=condition.strategy_type,
            all_indicators=indicators_dict
        )

    async def _batch_mark_expired(self, expired_signal_ids: List[str]):
        """Batch mark multiple signals as expired."""
        try:
            from .signal_creator import mark_signal_status
            # Mark all expired signals in parallel
            tasks = [mark_signal_status(signal_id, "expired") for signal_id in expired_signal_ids]
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.debug(f"Batch expire marking failed: {e}")

    async def _batch_mark_triggered(self, triggered_events: List[SignalTriggerEvent]):
        """Batch mark multiple signals as triggered."""
        try:
            from .signal_creator import mark_signal_status
            # Mark all triggered signals in parallel
            tasks = []
            for event in triggered_events:
                extra = {
                    "triggered_at": event.triggered_at,
                    "indicator_value": event.indicator_value
                }
                tasks.append(mark_signal_status(event.condition_id, "triggered", extra=extra))

            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.debug(f"Batch trigger marking failed: {e}")

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for monitoring."""
        return {
            "signals_checked": self._stats_signals_checked,
            "signals_triggered": self._stats_signals_triggered,
            "active_signals": len(self._active_signals),
            "trigger_rate": self._stats_signals_triggered / max(self._stats_signals_checked, 1),
            "last_reset": self._stats_last_reset.isoformat()
        }

    def reset_stats(self):
        """Reset performance statistics."""
        self._stats_signals_checked = 0
        self._stats_signals_triggered = 0
        self._stats_last_reset = datetime.now()

    def _evaluate_condition(self, condition: TradingCondition, indicators: Dict[str, Any]) -> bool:
        """Evaluate if a condition is met.

        Args:
            condition: Trading condition to evaluate
            indicators: Current indicator values

        Returns:
            True if condition is met, False otherwise
        """
        # Get current value
        current_value = indicators.get(condition.indicator)
        if current_value is None:
            logger.debug(f"Indicator {condition.indicator} not found in indicators dict. Available: {list(indicators.keys())}")
            return False
        
        try:
            current_value = float(current_value)
        except (ValueError, TypeError):
            logger.debug(f"Could not convert indicator value to float: {current_value}")
            return False

        logger.debug(f"Evaluating condition: {condition.indicator} {condition.operator.value} {condition.threshold}, current_value: {current_value}")

        # Evaluate based on operator
        result = False
        
        if condition.operator == ConditionOperator.GREATER_THAN:
            result = current_value > condition.threshold
        
        elif condition.operator == ConditionOperator.LESS_THAN:
            result = current_value < condition.threshold
        
        elif condition.operator == ConditionOperator.GREATER_EQUAL:
            result = current_value >= condition.threshold
        
        elif condition.operator == ConditionOperator.LESS_EQUAL:
            result = current_value <= condition.threshold
        
        elif condition.operator == ConditionOperator.EQUAL:
            result = abs(current_value - condition.threshold) < 0.01
        
        elif condition.operator == ConditionOperator.CROSSES_ABOVE:
            # Check cross using persisted previous value in Redis (more robust across restarts)
            prev_val = None
            try:
                if self._redis_client:
                    key = f"indicators_prev:{condition.instrument}:{condition.indicator}"
                    pv = self._redis_client.get(key)
                    prev_val = float(pv) if pv is not None else None
            except Exception:
                prev_val = condition._previous_value

            # Fall back to in-memory previous if Redis not available
            if prev_val is not None:
                result = (prev_val <= condition.threshold and current_value > condition.threshold)
            # Update both Redis and in-memory previous value
            try:
                if self._redis_client:
                    key = f"indicators_prev:{condition.instrument}:{condition.indicator}"
                    # Set with TTL to avoid stale storage (e.g., 4 hours)
                    self._redis_client.setex(key, 60 * 60 * 4, str(current_value))
            except Exception:
                pass
            condition._previous_value = current_value
        
        elif condition.operator == ConditionOperator.CROSSES_BELOW:
            # Check cross using persisted previous value in Redis
            prev_val = None
            try:
                if self._redis_client:
                    key = f"indicators_prev:{condition.instrument}:{condition.indicator}"
                    pv = self._redis_client.get(key)
                    prev_val = float(pv) if pv is not None else None
            except Exception:
                prev_val = condition._previous_value

            if prev_val is not None:
                result = (prev_val >= condition.threshold and current_value < condition.threshold)

            # Update persisted previous value and in-memory
            try:
                if self._redis_client:
                    key = f"indicators_prev:{condition.instrument}:{condition.indicator}"
                    self._redis_client.setex(key, 60 * 60 * 4, str(current_value))
            except Exception:
                pass
            condition._previous_value = current_value
        
        # Check additional conditions (AND logic)
        if result and condition.additional_conditions:
            for extra_cond in condition.additional_conditions:
                indicator_name = extra_cond.get("indicator")
                operator = extra_cond.get("operator")
                threshold = extra_cond.get("threshold")
                
                if not indicator_name or operator is None or threshold is None:
                    continue
                
                value = indicators.get(indicator_name)
                if value is None:
                    result = False
                    break
                
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    result = False
                    break
                
                # Simple comparison for additional conditions
                if operator == ">":
                    result = result and (value > threshold)
                elif operator == "<":
                    result = result and (value < threshold)
                elif operator == ">=":
                    result = result and (value >= threshold)
                elif operator == "<=":
                    result = result and (value <= threshold)
                
                if not result:
                    break
        
        return result


# Global singleton instance
_signal_monitor: Optional[SignalMonitor] = None


def get_signal_monitor() -> SignalMonitor:
    """Get global signal monitor instance.
    
    Returns:
        Singleton SignalMonitor instance
    """
    global _signal_monitor
    if _signal_monitor is None:
        _signal_monitor = SignalMonitor()
    return _signal_monitor

