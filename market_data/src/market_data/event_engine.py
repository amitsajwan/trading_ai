"""Event-driven architecture engine (inspired by VN.py).

Provides a centralized event bus for decoupling components:
- Gateway publishes tick events
- Strategies subscribe to tick/bar events
- Processors can transform and republish events

This eliminates direct coupling between components.
"""

import logging
from collections import defaultdict
from queue import Queue, Empty
from threading import Thread
from typing import Callable, Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import time

logger = logging.getLogger(__name__)


# Event type constants
EVENT_TICK = "tick"
EVENT_BAR = "bar"
EVENT_BAR_1M = "bar.1m"
EVENT_BAR_5M = "bar.5m"
EVENT_BAR_15M = "bar.15m"
EVENT_BAR_1H = "bar.1h"
EVENT_BAR_DAILY = "bar.daily"
EVENT_SIGNAL = "signal"
EVENT_ORDER = "order"
EVENT_TRADE = "trade"
EVENT_ERROR = "error"
EVENT_LOG = "log"


@dataclass
class Event:
    """Event object passed through the event engine.
    
    Attributes:
        type: Event type (e.g., "tick", "bar", "signal")
        data: Event payload (tick, bar, signal, etc.)
        timestamp: When event was created
    """
    type: str
    data: Any
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class EventEngine:
    """Event-driven engine for decoupled component communication.
    
    Based on VN.py's EventEngine architecture:
    - Thread-safe queue for event processing
    - Multiple handlers per event type
    - General handlers for all events
    - Background thread for continuous processing
    
    Example:
        engine = EventEngine()
        engine.register(EVENT_TICK, on_tick_handler)
        engine.start()
        
        # Publish events
        engine.put(Event(EVENT_TICK, tick_data))
    """
    
    def __init__(self, interval: int = 1):
        """Initialize event engine.
        
        Args:
            interval: Timer interval in seconds for background processing
        """
        self._interval = interval
        self._queue: Queue = Queue()
        self._active = False
        self._thread: Optional[Thread] = None
        
        # Event handlers: {event_type: [handler1, handler2, ...]}
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        # General handlers called for ALL events
        self._general_handlers: List[Callable] = []
        
        # Event statistics
        self._event_count = 0
        self._error_count = 0
        self._start_time: Optional[datetime] = None
        
        logger.info("EventEngine initialized")
    
    def start(self):
        """Start event processing thread."""
        if self._active:
            logger.warning("EventEngine already running")
            return
        
        self._active = True
        self._start_time = datetime.now()
        self._thread = Thread(target=self._run, daemon=True, name="EventEngine")
        self._thread.start()
        
        logger.info("EventEngine started")
    
    def stop(self):
        """Stop event processing thread."""
        if not self._active:
            return
        
        self._active = False
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        
        logger.info(f"EventEngine stopped. Processed {self._event_count} events, {self._error_count} errors")
    
    def _run(self):
        """Event processing loop (runs in background thread)."""
        logger.info("EventEngine processing thread started")
        
        while self._active:
            try:
                # Block for up to interval seconds waiting for events
                event = self._queue.get(block=True, timeout=self._interval)
                self._process(event)
                self._event_count += 1
                
            except Empty:
                # No events in queue, continue
                continue
            except Exception as e:
                logger.error(f"Error in event processing loop: {e}", exc_info=True)
                self._error_count += 1
    
    def _process(self, event: Event):
        """Process single event by calling all registered handlers.
        
        Args:
            event: Event to process
        """
        logger.debug(f"Processing event: {event.type}")
        
        # Call type-specific handlers
        if event.type in self._handlers:
            logger.debug(f"Found {len(self._handlers[event.type])} handlers for {event.type}")
            for handler in self._handlers[event.type]:
                try:
                    logger.debug(f"Calling handler {handler} for {event.type}")
                    handler(event)
                except Exception as e:
                    logger.error(f"Error in handler for {event.type}: {e}", exc_info=True)
                    self._error_count += 1
        else:
            logger.debug(f"No handlers found for {event.type}")
        
        # Call general handlers (for all event types)
        for handler in self._general_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in general handler: {e}", exc_info=True)
                self._error_count += 1
    
    def put(self, event: Event):
        """Put event into queue for processing.
        
        Args:
            event: Event to process
        """
        self._queue.put(event)
    
    def register(self, event_type: str, handler: Callable[[Event], None]):
        """Register handler for specific event type.
        
        Args:
            event_type: Event type to handle (e.g., EVENT_TICK)
            handler: Callback function taking Event as parameter
        """
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug(f"Registered handler for {event_type}")
    
    def unregister(self, event_type: str, handler: Callable[[Event], None]):
        """Unregister handler for event type.
        
        Args:
            event_type: Event type
            handler: Handler to remove
        """
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug(f"Unregistered handler for {event_type}")
    
    def register_general(self, handler: Callable[[Event], None]):
        """Register general handler called for ALL events.
        
        Useful for logging, monitoring, debugging.
        
        Args:
            handler: Callback function taking Event as parameter
        """
        if handler not in self._general_handlers:
            self._general_handlers.append(handler)
            logger.debug("Registered general handler")
    
    def unregister_general(self, handler: Callable[[Event], None]):
        """Unregister general handler.
        
        Args:
            handler: Handler to remove
        """
        if handler in self._general_handlers:
            self._general_handlers.remove(handler)
            logger.debug("Unregistered general handler")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event engine statistics.
        
        Returns:
            Dictionary with statistics
        """
        uptime = None
        if self._start_time:
            uptime = (datetime.now() - self._start_time).total_seconds()
        
        return {
            "active": self._active,
            "event_count": self._event_count,
            "error_count": self._error_count,
            "queue_size": self._queue.qsize(),
            "handler_types": len(self._handlers),
            "general_handlers": len(self._general_handlers),
            "uptime_seconds": uptime,
            "start_time": self._start_time.isoformat() if self._start_time else None,
        }
    
    def __repr__(self) -> str:
        return f"EventEngine(active={self._active}, events={self._event_count}, errors={self._error_count})"
