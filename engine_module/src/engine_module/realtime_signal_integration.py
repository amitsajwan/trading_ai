"""Integration: Real-time Signal Monitoring with Technical Indicators.

This module integrates SignalMonitor with TechnicalIndicatorsService to enable
real-time signal-to-trade conversion on every market tick.

Flow:
    1. Agent Analysis (15-min cycle) → Creates conditional signals
    2. SignalMonitor → Stores active signals  
    3. Market Tick → TechnicalIndicatorsService.update_tick()
    4. Auto-trigger → SignalMonitor.check_signals() on every tick
    5. Condition Met → Execute trade automatically
"""

import asyncio
import logging
import sys
import os
from typing import Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class RealtimeSignalProcessor:
    """Processes signals in real-time by monitoring every market tick.
    
    This is the bridge between:
    - TechnicalIndicatorsService (calculates indicators on every tick)
    - SignalMonitor (checks conditions and triggers trades)
    - Trade Execution (places orders when conditions are met)
    """
    
    def __init__(self, 
                 technical_service=None,
                 signal_monitor=None,
                 trade_executor: Optional[Callable] = None):
        """Initialize real-time signal processor.
        
        Args:
            technical_service: TechnicalIndicatorsService instance
            signal_monitor: SignalMonitor instance  
            trade_executor: Async function to execute trades
        """
        # Get services
        if technical_service is None:
            try:
                from market_data.technical_indicators_service import get_technical_service
            except ImportError:
                # Fallback: ensure market_data/src is in path
                market_data_src = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'market_data', 'src'))
                if os.path.exists(market_data_src) and market_data_src not in sys.path:
                    sys.path.insert(0, market_data_src)
                from market_data.technical_indicators_service import get_technical_service
            technical_service = get_technical_service()
        
        if signal_monitor is None:
            from engine_module.src.engine_module.signal_monitor import get_signal_monitor
            signal_monitor = get_signal_monitor()
        
        self.technical_service = technical_service
        self.signal_monitor = signal_monitor
        self.trade_executor = trade_executor
        
        # Register trade executor callback with monitor
        if trade_executor:
            self.signal_monitor.set_execution_callback(trade_executor)

        # Start Redis pub/sub listener for indicator updates (loosely coupled)
        self._pubsub_task = None
        try:
            # Prefer asyncio Redis client when available
            try:
                import redis.asyncio as aioredis
                self._aioredis = aioredis
            except Exception:
                self._aioredis = None

            # Start background listener depending on availability
            if self._aioredis is not None:
                # Asyncio-based listener
                import asyncio
                self._pubsub_task = asyncio.create_task(self._async_redis_listener())
            else:
                # Fallback to threaded listener using sync redis client
                import threading
                t = threading.Thread(target=self._threaded_redis_listener, daemon=True)
                t.start()
        except Exception as e:
            logger.warning(f"Failed to start Redis indicator listener: {e}")

        # Statistics
        self.ticks_processed = 0
        self.signals_triggered = 0
        
        logger.info("RealtimeSignalProcessor initialized")

    
    async def on_tick(self, instrument: str, tick: Dict[str, Any]) -> Dict[str, Any]:
        """Process market tick: Update indicators → Check signals → Execute trades.
        
        This should be called on EVERY market tick from your WebSocket handler.
        
        Args:
            instrument: Instrument symbol
            tick: Tick data with last_price, volume, timestamp
            
        Returns:
            Dict with processing results
        """
        self.ticks_processed += 1
        
        # Step 1: Update technical indicators
        indicators = self.technical_service.update_tick(instrument, tick)
        
        # Step 2: Check if any signals should trigger
        triggered_events = await self.signal_monitor.check_signals(instrument)
        
        if triggered_events:
            self.signals_triggered += len(triggered_events)
            logger.info(
                f"✅ {len(triggered_events)} signal(s) triggered for {instrument} "
                f"at price {tick.get('last_price')}"
            )
        
        # After processing, return a compact summary
        return {
            "instrument": instrument,
            "tick_price": tick.get("last_price"),
            "timestamp": tick.get("timestamp"),
            "indicators_updated": True,
            "signals_checked": len(self.signal_monitor.get_active_signals(instrument)),
            "signals_triggered": len(triggered_events),
            "triggered_events": triggered_events
        }

    async def _async_redis_listener(self):
        """Async listener for Redis pub/sub indicator updates (uses redis.asyncio)."""
        try:
            aioredis = self._aioredis
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            client = aioredis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
            pubsub = client.pubsub()
            await pubsub.psubscribe("indicators:*")
            logger.info("Subscribed to Redis channel pattern indicators:*")

            async for message in pubsub.listen():
                # Message types: pmessage (pattern), message
                try:
                    if message and message.get("type") in ("pmessage", "message"):
                        channel = message.get("channel") or message.get("pattern")
                        data = message.get("data")
                        if not data:
                            continue
                        import json
                        try:
                            payload = json.loads(data)
                        except Exception:
                            payload = {}

                        # Channel is like 'indicators:INSTRUMENT'
                        ch = channel if isinstance(channel, str) else channel.decode("utf-8")
                        if ch and ch.startswith("indicators:"):
                            instr = ch.split(":", 1)[1]
                            # Trigger signal checks for this instrument
                            try:
                                await self.signal_monitor.check_signals(instr)
                            except Exception as e:
                                logger.error(f"Error checking signals for {instr}: {e}")
                except Exception as e:
                    logger.debug(f"Ignored pubsub message error: {e}")
        except Exception as e:
            logger.warning(f"Async Redis listener stopped: {e}")

    def _threaded_redis_listener(self):
        """Threaded listener for sync redis client.
        Uses blocking pubsub.get_message with timeout polling and schedules asyncio checks.
        """
        try:
            from engine_module.api_service import get_redis_client
            import time, json
            redis_client = get_redis_client()
            pubsub = redis_client.pubsub()
            pubsub.psubscribe("indicators:*")
            logger.info("Threaded Redis listener subscribed to indicators:*")

            while True:
                message = pubsub.get_message(timeout=1.0)
                if message and message.get("type") in ("pmessage", "message"):
                    channel = message.get("channel")
                    data = message.get("data")
                    try:
                        payload = json.loads(data) if data else {}
                    except Exception:
                        payload = {}

                    ch = channel if isinstance(channel, str) else channel.decode("utf-8")
                    if ch.startswith("indicators:"):
                        instr = ch.split(":", 1)[1]
                        # Schedule check_signals in event loop
                        try:
                            import asyncio
                            loop = asyncio.get_event_loop()
                            asyncio.run_coroutine_threadsafe(self.signal_monitor.check_signals(instr), loop)
                        except Exception as e:
                            logger.error(f"Failed to schedule signal check for {instr}: {e}")

                time.sleep(0.01)
        except Exception as e:
            logger.warning(f"Threaded Redis listener stopped: {e}")    
    async def on_candle(self, instrument: str, candle: Dict[str, Any]) -> Dict[str, Any]:
        """Process completed candle: Update indicators → Check signals.
        
        Args:
            instrument: Instrument symbol
            candle: OHLCV candle data
            
        Returns:
            Dict with processing results
        """
        # Update indicators with completed candle
        indicators = self.technical_service.update_candle(instrument, candle)
        
        # Check signals
        triggered_events = await self.signal_monitor.check_signals(instrument)
        
        if triggered_events:
            self.signals_triggered += len(triggered_events)
        
        return {
            "instrument": instrument,
            "candle_close": candle.get("close"),
            "timestamp": candle.get("timestamp"),
            "indicators_updated": True,
            "signals_triggered": len(triggered_events),
            "triggered_events": triggered_events
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics.
        
        Returns:
            Dict with processing stats
        """
        return {
            "ticks_processed": self.ticks_processed,
            "signals_triggered": self.signals_triggered,
            "active_signals": len(self.signal_monitor.get_active_signals()),
            "total_triggered_history": len(self.signal_monitor.get_triggered_signals())
        }


async def example_trade_executor(event):
    """Example trade execution callback.
    
    This should be replaced with actual broker API integration.
    
    Args:
        event: SignalTriggerEvent with trade details
    """
    from engine_module.src.engine_module.signal_monitor import SignalTriggerEvent
    
    logger.info("=" * 70)
    logger.info("🚀 EXECUTING TRADE")
    logger.info("-" * 70)
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
    
    # TODO: Replace with actual broker API call
    # order = await broker.place_order(
    #     instrument=event.instrument,
    #     transaction_type=event.action,
    #     quantity=event.position_size,
    #     price=event.current_price,
    #     stop_loss=event.stop_loss,
    #     target=event.take_profit
    # )
    
    # For now, just log
    await asyncio.sleep(0.1)  # Simulate API call
    logger.info(f"✓ Trade executed (PAPER TRADING)")


def create_realtime_processor(trade_executor: Optional[Callable] = None) -> RealtimeSignalProcessor:
    """Factory function to create a configured RealtimeSignalProcessor.
    
    Args:
        trade_executor: Optional custom trade executor callback.
                       If None, uses example executor.
    
    Returns:
        Configured RealtimeSignalProcessor instance
    """
    if trade_executor is None:
        trade_executor = example_trade_executor
    
    processor = RealtimeSignalProcessor(trade_executor=trade_executor)
    
    logger.info("✓ RealtimeSignalProcessor created")
    logger.info("  - TechnicalIndicatorsService: Connected")
    logger.info("  - SignalMonitor: Connected")
    logger.info("  - Trade Executor: Registered")
    
    return processor


# Example: How to integrate with your market data WebSocket
"""
# In your market data handler (e.g., Kite WebSocket on_ticks callback)

from engine_module.realtime_signal_integration import create_realtime_processor

# Initialize processor once at startup
processor = create_realtime_processor()

def on_ticks(ws, ticks):
    '''WebSocket tick handler.'''
    for tick in ticks:
        # Process each tick through real-time signal system
        asyncio.create_task(processor.on_tick(
            instrument=tick["instrument_token"],
            tick={
                "last_price": tick["last_price"],
                "volume": tick["volume"],
                "timestamp": tick["timestamp"]
            }
        ))
"""

