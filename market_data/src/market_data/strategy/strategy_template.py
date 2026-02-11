"""Strategy template for algorithmic trading (inspired by VN.py).

Provides clean callback-based architecture for strategy development:
- on_init(): Strategy initialization
- on_start(): Strategy activation
- on_stop(): Strategy deactivation
- on_tick(): Real-time tick callback
- on_bar(): 1-minute bar callback
- on_Xmin_bar(): X-minute bar callback

Usage:
    class MyStrategy(StrategyTemplate):
        def __init__(self, ...):
            super().__init__(...)
            self.bg = BarGenerator(self.on_bar, 15, self.on_15min_bar)
            self.am = ArrayManager()
        
        def on_tick(self, tick):
            self.bg.update_tick(tick)
        
        def on_15min_bar(self, bar):
            self.am.update_bar(bar)
            if self.am.inited:
                # Calculate indicators and generate signals
                ...
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from .contracts import MarketTick, OHLCBar
from .event_engine import EventEngine, Event, EVENT_TICK, EVENT_BAR

logger = logging.getLogger(__name__)


@dataclass
class StrategyConfig:
    """Strategy configuration."""
    strategy_name: str
    instruments: list[str]
    parameters: Dict[str, Any] = field(default_factory=dict)


class StrategyTemplate(ABC):
    """Base template for algorithmic trading strategies.
    
    Provides lifecycle management and callback interface:
    - Initialization and configuration
    - Event-driven tick/bar processing
    - Position and order management hooks
    - Logging and monitoring
    
    Subclasses must implement:
    - on_init(): Initialize indicators, load data
    - on_tick() or on_bar(): Process market data
    - Trading logic in callbacks
    
    Example:
        class MomentumStrategy(StrategyTemplate):
            mom_period = 10
            
            def __init__(self, config, event_engine):
                super().__init__(config, event_engine)
                self.bg = BarGenerator(self.on_bar, 15, self.on_15min_bar)
                self.am = ArrayManager()
            
            def on_init(self):
                self.write_log("Strategy initialized")
            
            def on_tick(self, tick):
                self.bg.update_tick(tick)
            
            def on_15min_bar(self, bar):
                self.am.update_bar(bar)
                if self.am.inited:
                    mom = self.am.mom(self.mom_period)
                    if mom > 0:
                        self.buy(bar.close, 1)
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        event_engine: Optional[EventEngine] = None
    ):
        """Initialize strategy.
        
        Args:
            config: Strategy configuration
            event_engine: Event engine for publishing signals/orders
        """
        self.strategy_name = config.strategy_name
        self.instruments = config.instruments
        self.parameters = config.parameters
        self.event_engine = event_engine
        
        # Strategy state
        self.inited = False
        self.trading = False
        
        # Position tracking (instrument -> position)
        self.pos: Dict[str, int] = {inst: 0 for inst in self.instruments}
        
        logger.info(f"Strategy {self.strategy_name} created for {len(self.instruments)} instruments")
    
    # ===================================================================
    # Lifecycle Methods
    # ===================================================================
    
    @abstractmethod
    def on_init(self):
        """Initialize strategy.
        
        Called when strategy is first loaded.
        Use for:
        - Loading historical data
        - Initializing indicators
        - Setting up internal state
        
        Strategy state:
        - inited=False, trading=False
        """
        pass
    
    def on_start(self):
        """Start strategy.
        
        Called when strategy begins trading.
        Can be overridden for custom start logic.
        
        Strategy state:
        - inited=True, trading=True
        """
        self.trading = True
        self.write_log("Strategy started")
    
    def on_stop(self):
        """Stop strategy.
        
        Called when strategy stops trading.
        Can be overridden for cleanup logic.
        
        Strategy state:
        - trading=False
        """
        self.trading = False
        self.write_log("Strategy stopped")
    
    # ===================================================================
    # Market Data Callbacks
    # ===================================================================
    
    def on_tick(self, tick: MarketTick):
        """Tick callback.
        
        Called when new tick arrives.
        Override to implement tick-based logic.
        
        Typical usage:
            def on_tick(self, tick):
                self.bg.update_tick(tick)  # Feed to BarGenerator
        
        Args:
            tick: Market tick data
        """
        pass
    
    def on_bar(self, bar: OHLCBar):
        """1-minute bar callback.
        
        Called when 1-minute bar completes.
        Override to implement bar-based logic.
        
        Typical usage:
            def on_bar(self, bar):
                self.bg.update_bar(bar)  # Feed to multi-timeframe generator
        
        Args:
            bar: OHLC bar data
        """
        pass
    
    # ===================================================================
    # Trading Interface
    # ===================================================================
    
    def buy(self, price: float, volume: int, instrument: Optional[str] = None):
        """Send buy order.
        
        Args:
            price: Order price
            volume: Order volume
            instrument: Instrument to trade (default: first instrument)
        """
        if not self.trading:
            return
        
        inst = instrument or self.instruments[0]
        self.write_log(f"BUY {inst}: {volume} @ {price}")
        
        # TODO: Implement order management
        # For now, just log and update position
        self.pos[inst] += volume
    
    def sell(self, price: float, volume: int, instrument: Optional[str] = None):
        """Send sell order.
        
        Args:
            price: Order price
            volume: Order volume
            instrument: Instrument to trade (default: first instrument)
        """
        if not self.trading:
            return
        
        inst = instrument or self.instruments[0]
        self.write_log(f"SELL {inst}: {volume} @ {price}")
        
        # TODO: Implement order management
        self.pos[inst] -= volume
    
    def short(self, price: float, volume: int, instrument: Optional[str] = None):
        """Send short order.
        
        Args:
            price: Order price
            volume: Order volume
            instrument: Instrument to trade (default: first instrument)
        """
        if not self.trading:
            return
        
        inst = instrument or self.instruments[0]
        self.write_log(f"SHORT {inst}: {volume} @ {price}")
        
        # TODO: Implement order management
        self.pos[inst] -= volume
    
    def cover(self, price: float, volume: int, instrument: Optional[str] = None):
        """Send cover order (close short).
        
        Args:
            price: Order price
            volume: Order volume
            instrument: Instrument to trade (default: first instrument)
        """
        if not self.trading:
            return
        
        inst = instrument or self.instruments[0]
        self.write_log(f"COVER {inst}: {volume} @ {price}")
        
        # TODO: Implement order management
        self.pos[inst] += volume
    
    # ===================================================================
    # Utility Methods
    # ===================================================================
    
    def write_log(self, msg: str):
        """Write log message.
        
        Args:
            msg: Log message
        """
        logger.info(f"[{self.strategy_name}] {msg}")
    
    def get_position(self, instrument: Optional[str] = None) -> int:
        """Get current position.
        
        Args:
            instrument: Instrument (default: first instrument)
            
        Returns:
            Position size (positive=long, negative=short)
        """
        inst = instrument or self.instruments[0]
        return self.pos.get(inst, 0)
    
    def put_event(self):
        """Update strategy UI/monitoring.
        
        Called to notify external systems of strategy state changes.
        """
        if not self.event_engine:
            return
        
        # TODO: Publish strategy state event
        pass
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"name={self.strategy_name}, "
            f"inited={self.inited}, "
            f"trading={self.trading})"
        )
