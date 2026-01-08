"""UI Dispatcher implementations."""

import logging
from typing import Dict, Any

from .contracts import (
    UIDispatcher,
    UserAction,
    BuyOverride,
    SellOverride,
    StopLossUpdate,
    RiskLimitUpdate,
)

logger = logging.getLogger(__name__)


class MockEngineInterface:
    """Mock interface to engine module for dispatching actions."""

    async def process_user_override(self, action: UserAction) -> Dict[str, Any]:
        """Mock processing of user override actions."""
        # This would normally send actions to the trading engine
        # For now, just log and return success
        logger.info(f"Processing user action: {action.action_type}")

        if isinstance(action, BuyOverride):
            return {
                "status": "queued",
                "action_id": f"buy_{action.instrument}_{action.timestamp.isoformat()}",
                "message": f"Buy override queued for {action.instrument}",
                "details": {
                    "instrument": action.instrument,
                    "quantity": action.quantity,
                    "price_limit": action.price_limit
                }
            }

        elif isinstance(action, SellOverride):
            return {
                "status": "queued",
                "action_id": f"sell_{action.instrument}_{action.timestamp.isoformat()}",
                "message": f"Sell override queued for {action.instrument}",
                "details": {
                    "instrument": action.instrument,
                    "quantity": action.quantity,
                    "price_limit": action.price_limit
                }
            }

        elif isinstance(action, StopLossUpdate):
            return {
                "status": "updated",
                "action_id": f"stoploss_{action.instrument}_{action.timestamp.isoformat()}",
                "message": f"Stop loss updated for {action.instrument}",
                "details": {
                    "instrument": action.instrument,
                    "stop_loss_price": action.stop_loss_price
                }
            }

        elif isinstance(action, RiskLimitUpdate):
            return {
                "status": "updated",
                "action_id": f"risk_limits_{action.timestamp.isoformat()}",
                "message": "Risk limits updated",
                "details": {
                    "max_position_size": action.max_position_size,
                    "max_daily_loss": action.max_daily_loss
                }
            }

        return {
            "status": "unknown",
            "message": f"Unknown action type: {action.action_type}"
        }

    async def pause_trading(self, reason: str) -> Dict[str, Any]:
        """Mock pause trading."""
        logger.info(f"Pausing trading: {reason}")
        return {
            "status": "paused",
            "reason": reason,
            "timestamp": str(self._current_time())
        }

    async def resume_trading(self) -> Dict[str, Any]:
        """Mock resume trading."""
        logger.info("Resuming trading")
        return {
            "status": "resumed",
            "timestamp": str(self._current_time())
        }

    async def emergency_stop(self, reason: str) -> Dict[str, Any]:
        """Mock emergency stop."""
        logger.warning(f"Emergency stop activated: {reason}")
        return {
            "status": "stopped",
            "reason": reason,
            "timestamp": str(self._current_time()),
            "alert_level": "critical"
        }

    def _current_time(self):
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow()


class EngineActionDispatcher(UIDispatcher):
    """Dispatcher that sends user actions to the trading engine."""

    def __init__(self, engine_interface=None):
        """Initialize with engine interface.

        Args:
            engine_interface: Interface to engine module (mock if None)
        """
        self.engine = engine_interface or MockEngineInterface()

    async def submit_override(self, action: UserAction) -> Dict[str, Any]:
        """Submit a user override action to the trading engine."""
        try:
            # Validate action
            if not isinstance(action, UserAction):
                return {
                    "status": "error",
                    "message": "Invalid action type",
                    "error": "Action must be a UserAction instance"
                }

            # Process the action through engine
            result = await self.engine.process_user_override(action)

            # Add success confirmation
            result["processed_at"] = str(action.timestamp)
            result["action_type"] = action.action_type

            logger.info(f"User action processed: {action.action_type} - {result.get('status', 'unknown')}")

            return result

        except Exception as e:
            logger.error(f"Failed to process user action {action.action_type}: {e}")
            return {
                "status": "error",
                "message": f"Failed to process {action.action_type}",
                "error": str(e),
                "action_type": action.action_type
            }

    async def pause_trading(self, reason: str = "User requested pause") -> Dict[str, Any]:
        """Pause automated trading."""
        try:
            result = await self.engine.pause_trading(reason)
            logger.info(f"Trading paused: {reason}")
            return result
        except Exception as e:
            logger.error(f"Failed to pause trading: {e}")
            return {
                "status": "error",
                "message": "Failed to pause trading",
                "error": str(e)
            }

    async def resume_trading(self) -> Dict[str, Any]:
        """Resume automated trading after pause."""
        try:
            result = await self.engine.resume_trading()
            logger.info("Trading resumed")
            return result
        except Exception as e:
            logger.error(f"Failed to resume trading: {e}")
            return {
                "status": "error",
                "message": "Failed to resume trading",
                "error": str(e)
            }

    async def emergency_stop(self, reason: str = "Emergency stop activated") -> Dict[str, Any]:
        """Emergency stop all trading activities."""
        try:
            result = await self.engine.emergency_stop(reason)
            logger.critical(f"Emergency stop activated: {reason}")
            return result
        except Exception as e:
            logger.error(f"Failed to emergency stop: {e}")
            return {
                "status": "error",
                "message": "Failed to emergency stop",
                "error": str(e)
            }

    async def publish(self, event: str, data: Dict[str, Any]) -> None:
        """Publish event to UI subscribers."""
        # This would normally publish to WebSocket subscribers, message queues, etc.
        # For now, just log the event
        logger.info(f"Published event '{event}': {data}")

        # Could be extended to:
        # - Send WebSocket messages
        # - Publish to Redis pub/sub
        # - Send notifications
        # - Update UI state


__all__ = [
    "EngineActionDispatcher",
    "MockEngineInterface",
]

