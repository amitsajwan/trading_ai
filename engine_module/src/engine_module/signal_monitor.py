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
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

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
    
    # Multi-condition support (AND logic)
    additional_conditions: List[Dict[str, Any]] = field(default_factory=list)
    
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
        """Initialize signal monitor.
        
        Args:
            technical_service: Optional TechnicalIndicatorsService instance.
                              If None, will fetch via get_technical_service()
        """
        self._active_signals: Dict[str, TradingCondition] = {}
        self._triggered_signals: List[SignalTriggerEvent] = []
        self._technical_service = technical_service
        
        # Callbacks for trade execution
        self._on_signal_triggered: Optional[Callable] = None
        
        logger.info("SignalMonitor initialized")
    
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
        # Get latest indicators from service
        if self._technical_service is None:
            from market_data.src.market_data.technical_indicators_service import get_technical_service
            self._technical_service = get_technical_service()
        
        indicators_dict = self._technical_service.get_indicators_dict(instrument)
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
                if datetime.now().isoformat() > condition.expires_at:
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
            return False
        
        try:
            current_value = float(current_value)
        except (ValueError, TypeError):
            return False
        
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
            # Check if value crossed from below to above threshold
            if condition._previous_value is not None:
                result = (condition._previous_value <= condition.threshold and 
                         current_value > condition.threshold)
            condition._previous_value = current_value
        
        elif condition.operator == ConditionOperator.CROSSES_BELOW:
            # Check if value crossed from above to below threshold
            if condition._previous_value is not None:
                result = (condition._previous_value >= condition.threshold and 
                         current_value < condition.threshold)
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

