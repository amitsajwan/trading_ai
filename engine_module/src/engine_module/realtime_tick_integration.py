"""Real-time Tick Integration - Connects Market Data Ticks to Signal Monitoring.

This service bridges market data ticks (from collectors or historical replay) 
with the SignalMonitor for real-time condition checking and trade execution.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import os
import sys

logger = logging.getLogger(__name__)

# Global real-time processor instance
_realtime_processor = None


async def process_tick_for_signals(instrument: str, tick: Dict[str, Any]) -> Dict[str, Any]:
    """Process a market tick through the real-time signal monitoring system.
    
    This function should be called on EVERY market tick (from WebSocket, collectors, or historical replay).
    It updates technical indicators and checks if any active signals should trigger.
    
    Args:
        instrument: Instrument symbol (e.g., "BANKNIFTY")
        tick: Tick data dictionary with:
            - last_price: float
            - volume: int (optional)
            - timestamp: str or datetime
            - Other tick fields
    
    Returns:
        Dict with processing results including triggered signals
    """
    global _realtime_processor
    
    try:
        # Initialize processor if not already done
        if _realtime_processor is None:
            _realtime_processor = await _initialize_realtime_processor()
        
        if _realtime_processor is None:
            return {
                "processed": False,
                "error": "RealtimeSignalProcessor not available"
            }
        
        # Process tick through signal monitoring
        result = await _realtime_processor.on_tick(instrument, tick)
        return result
        
    except Exception as e:
        logger.error(f"Error processing tick for signals: {e}", exc_info=True)
        return {
            "processed": False,
            "error": str(e)
        }


async def _initialize_realtime_processor() -> Optional[Any]:
    """Initialize RealtimeSignalProcessor with trade execution callback.
    
    Returns:
        RealtimeSignalProcessor instance or None if initialization fails
    """
    try:
        from .realtime_signal_integration import create_realtime_processor
        
        # Create trade executor callback
        trade_executor = await _create_trade_executor()
        
        # Create processor with trade executor
        processor = create_realtime_processor(trade_executor=trade_executor)
        
        logger.info("Real-time tick integration initialized")
        return processor
        
    except ImportError as e:
        logger.warning(f"RealtimeSignalProcessor not available: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize real-time processor: {e}", exc_info=True)
        return None


async def _create_trade_executor() -> Callable:
    """Create trade execution callback that connects to user_module.
    
    Returns:
        Async function that executes trades when signals trigger
    """
    async def execute_trade(event: Any) -> None:
        """Execute trade when signal condition is met.
        
        Args:
            event: SignalTriggerEvent from SignalMonitor
        """
        try:
            logger.info("=" * 70)
            logger.info("🚀 EXECUTING TRADE FROM SIGNAL TRIGGER")
            logger.info("-" * 70)
            logger.info(f"  Signal ID: {event.condition_id}")
            logger.info(f"  Instrument: {event.instrument}")
            logger.info(f"  Action: {event.action}")
            logger.info(f"  Price: {event.current_price}")
            logger.info(f"  Position Size: {event.position_size}")
            logger.info(f"  Confidence: {event.confidence:.0%}")
            logger.info(f"  Stop Loss: {event.stop_loss}" if event.stop_loss else "  Stop Loss: None")
            logger.info(f"  Take Profit: {event.take_profit}" if event.take_profit else "  Take Profit: None")
            logger.info("-" * 70)
            logger.info(f"  Trigger: {event.indicator_name} = {event.indicator_value:.2f}")
            logger.info(f"  Threshold: {event.threshold}")
            logger.info(f"  Triggered At: {event.triggered_at}")
            logger.info("=" * 70)
            
            # Execute trade via user_module API
            try:
                import httpx
                async with httpx.AsyncClient(timeout=30.0) as client:
                    trade_data = {
                        "instrument": event.instrument,
                        "side": event.action,
                        "quantity": int(event.position_size),
                        "price": event.current_price,
                        "order_type": "MARKET",
                        "stop_loss": event.stop_loss,
                        "take_profit": event.take_profit,
                        "signal_id": event.condition_id,
                        "triggered_at": event.triggered_at
                    }
                    
                    # Try user_module trade execution endpoint
                    response = await client.post(
                        "http://localhost:8007/api/trade/execute",
                        json=trade_data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        logger.info(f"✅ Trade executed successfully: {result}")
                        
                        # Update signal status in MongoDB
                        await _mark_signal_as_executed(event.condition_id)
                    else:
                        logger.error(f"❌ Trade execution failed: {response.status_code} - {response.text}")
                        
            except Exception as trade_error:
                logger.error(f"Failed to execute trade via user_module: {trade_error}", exc_info=True)
                
                # Fallback: Try engine API if user_module not available
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        # Fallback to engine trade execution
                        response = await client.post(
                            f"http://localhost:8006/api/v1/trade/execute",
                            json=trade_data
                        )
                        if response.status_code == 200:
                            logger.info(f"✅ Trade executed via engine API: {response.json()}")
                            await _mark_signal_as_executed(event.condition_id)
                        else:
                            logger.error(f"❌ Engine API trade execution also failed: {response.status_code}")
                except Exception as fallback_error:
                    logger.error(f"Fallback trade execution also failed: {fallback_error}")
            
            logger.info(f"✓ Trade execution completed for signal {event.condition_id}")
            
        except Exception as e:
            logger.error(f"Error in trade executor callback: {e}", exc_info=True)
    
    return execute_trade


async def _mark_signal_as_executed(condition_id: str) -> None:
    """Mark signal as executed in MongoDB.
    
    Args:
        condition_id: Signal condition ID
    """
    try:
        from pymongo import MongoClient
        
        mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/zerodha_trading")
        client = MongoClient(mongodb_uri)
        db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
        db = client[db_name]
        
        collection = db["signals"]
        collection.update_one(
            {"condition_id": condition_id},
            {"$set": {"status": "executed", "executed_at": datetime.now().isoformat()}}
        )
        
        logger.info(f"Marked signal {condition_id} as executed in MongoDB")
        
    except Exception as e:
        logger.warning(f"Failed to mark signal as executed: {e}")


# Integration hook for market data collectors
def setup_tick_callback_for_collectors() -> Optional[Callable]:
    """Setup tick callback for market data collectors.
    
    Returns:
        Callback function that can be passed to tick collectors
    """
    async def tick_callback(tick: Any) -> None:
        """Callback function for market data ticks.
        
        Args:
            tick: MarketTick or tick dictionary
        """
        try:
            # Extract instrument and tick data
            if hasattr(tick, 'instrument'):
                instrument = tick.instrument
                tick_dict = {
                    "last_price": tick.last_price if hasattr(tick, 'last_price') else getattr(tick, 'price', 0),
                    "volume": getattr(tick, 'volume', 0),
                    "timestamp": getattr(tick, 'timestamp', datetime.now().isoformat())
                }
            elif isinstance(tick, dict):
                instrument = tick.get("instrument", "BANKNIFTY")
                tick_dict = {
                    "last_price": tick.get("last_price", tick.get("price", 0)),
                    "volume": tick.get("volume", 0),
                    "timestamp": tick.get("timestamp", datetime.now().isoformat())
                }
            else:
                logger.warning(f"Unknown tick format: {type(tick)}")
                return
            
            # Process tick through signal monitoring
            await process_tick_for_signals(instrument, tick_dict)
            
        except Exception as e:
            logger.error(f"Error in tick callback: {e}", exc_info=True)
    
    return tick_callback
