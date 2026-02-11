#!/usr/bin/env python3
"""Unified Runner for Mock/Real WebSocket → EventEngine → Bars → Indicators Pipeline.

This runner demonstrates the SWAPPABLE ARCHITECTURE integrated with EVENT-DRIVEN SYSTEM:
- Change 1 line to swap Real WebSocket ↔ Mock WebSocket
- All downstream code IDENTICAL
- Event-driven real-time bars and indicators
- Mode auto-detected (live/historical) with automatic prefix

Usage:
    # Mock WebSocket (for testing/development):
    python simple_runner.py --websocket mock --instruments BANKNIFTY26FEBFUT
    
    # Real Kite WebSocket (when available):
    python simple_runner.py --websocket real --instruments BANKNIFTY26FEBFUT
    
    # Multiple instruments:
    python simple_runner.py --websocket mock --instruments BANKNIFTY26FEBFUT NIFTY26FEBFUT

Architecture (EVENT-DRIVEN):
    WebSocket (Real/Mock) → WebSocketTickCollector → EventEngine (EVENT_TICK)
         ↑                                                ↓
      PLUGGABLE                                      BarGenerator (subscribes)
      (1 line)                                           ↓
                                                  EventEngine (EVENT_BAR_1M, 5M, 15M, 1H)
                                                         ↓
                                                  IndicatorHandler (subscribes to bar events)
                                                         ↓
                                                  Redis Storage (AUTO-PREFIXED: live:/historical:)
"""

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'market_data', 'src'))
sys.path.insert(0, os.path.dirname(__file__))  # For redis_key_manager

# Imports
try:
    import redis
    from redis_key_manager import get_execution_mode  # Root level module
    # Import mock_kite_websocket directly to avoid sources/__init__.py kiteconnect import
    import importlib.util
    spec = importlib.util.spec_from_file_location("mock_kite_websocket", os.path.join(os.path.dirname(__file__), 'market_data', 'src', 'market_data', 'sources', 'mock_kite_websocket.py'))
    mock_kite_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mock_kite_module)
    MockKiteTicker = mock_kite_module.MockKiteTicker
    create_mock_ticker = mock_kite_module.create_mock_ticker
    # Conditionally import EventDrivenCollector only for real websocket
    EventDrivenCollector = None  # Will import only when needed
    from market_data.event_engine import EventEngine, Event, EVENT_TICK, EVENT_BAR, EVENT_BAR_1M, EVENT_BAR_5M, EVENT_BAR_15M, EVENT_BAR_1H
    from market_data.bar_generator import BarGenerator, Interval
    from market_data.contracts import MarketTick, OHLCBar
    from market_data.adapters.redis_store import RedisMarketStore
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure you're running from the correct directory with all dependencies installed")
    sys.exit(1)


class RealTimeIndicatorHandler:
    """
    Event-driven handler for real-time indicator calculation.
    
    Subscribes to bar events and calculates indicators in real-time.
    """
    
    def __init__(self, event_engine: EventEngine, store: RedisMarketStore):
        """Initialize indicator handler.
        
        Args:
            event_engine: EventEngine to subscribe to
            store: Redis store for reading bars and storing indicators
        """
        self.event_engine = event_engine
        self.store = store
        self.indicators_calculated = 0
        
        # Subscribe to all bar events
        self.event_engine.register(EVENT_BAR_1M, self._on_bar)
        self.event_engine.register(EVENT_BAR_5M, self._on_bar)
        self.event_engine.register(EVENT_BAR_15M, self._on_bar)
        self.event_engine.register(EVENT_BAR_1H, self._on_bar)
        
        logger.info("✅ RealTimeIndicatorHandler subscribed to bar events")
    
    def _on_bar(self, event: Event):
        """Handle bar event - calculate and store indicators in real-time.
        
        Args:
            event: Bar event (contains OHLCBar in event.data)
        """
        try:
            bar: OHLCBar = event.data
            
            logger.info(f"🎯 Indicator handler received {event.type} event for {bar.instrument} {bar.timeframe}")
            
            # Only calculate for 1-minute bars to avoid redundancy
            if bar.timeframe != "1m":
                logger.debug(f"Skipping indicators for {bar.timeframe} (only 1m supported)")
                return
            
            # Import here to avoid circular dependency
            from market_data.technical_indicators_service import TechnicalIndicatorsService
            
            # Get last N bars for indicator calculation (100 bars for most indicators)
            bars = self.store.get_ohlc(bar.instrument, bar.timeframe, limit=100)
            
            logger.info(f"📊 Retrieved {len(bars)} bars for indicator calculation")
            
            if len(bars) < 14:  # Minimum for RSI
                logger.debug(f"Not enough bars for indicators: {len(bars)}")
                return
            
            # Calculate indicators
            indicators_service = TechnicalIndicatorsService()
            indicators = indicators_service.calculate_indicators_from_ohlc_bars(
                instrument=bar.instrument,
                timeframe=bar.timeframe,
                ohlc_bars=bars
            )
            
            # Store indicators in Redis for API access
            self._store_indicators(bar.instrument, indicators)
            
            self.indicators_calculated += 1
            logger.info(f"✨ Real-time indicators calculated and stored for {bar.instrument} (total: {self.indicators_calculated})")
        
        except ImportError:
            logger.debug("TechnicalIndicatorsService not available")
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}", exc_info=True)
    
    def _store_indicators(self, instrument: str, indicators):
        """Store indicators in Redis for API access."""
        try:
            # Get Redis client
            import redis
            from redis_key_manager import get_redis_key
            r = redis.Redis(host='localhost', port=6380, decode_responses=True)
            
            # Store each indicator
            key_prefix = f"indicators:{instrument.upper()}:"
            
            # Convert indicators to dict and store
            ind_dict = indicators.__dict__
            for key, value in ind_dict.items():
                if key.startswith('_') or value is None:
                    continue
                redis_key = key_prefix + key
                r.set(redis_key, str(value))
            
            logger.info(f"Stored {len(ind_dict)} indicators for {instrument}")
            
        except Exception as e:
            logger.error(f"Error storing indicators: {e}")


class EventDrivenPipelineRunner:
    """
    Runs the complete EVENT-DRIVEN pipeline: WebSocket → EventEngine → Bars → Indicators.
    
    Key Features:
    - Swap WebSocket with 1 line change, everything else identical!
    - Uses existing EventEngine + BarGenerator (event-driven)
    - Real-time bar aggregation and indicator calculation
    - Mode-agnostic storage with automatic prefixes
    """
    
    def __init__(
        self,
        websocket_type: str = 'mock',
        instruments: List[str] = None,
        timeframes: Dict[str, int] = None,
        tick_interval: float = 60.0
    ):
        """
        Initialize event-driven pipeline runner.
        
        Args:
            websocket_type: 'mock' or 'real'
            instruments: Instrument symbols
            timeframes: Dict mapping timeframe names to window sizes
                       e.g., {'5min': 5, '15min': 15, '1h': 60}
            tick_interval: Seconds between ticks (mock only)
        """
        self.websocket_type = websocket_type
        self.instruments = instruments or ['BANKNIFTY26FEBFUT']
        self.timeframes = timeframes or {'5min': 5, '15min': 15}
        self.tick_interval = tick_interval
        
        # Event-driven components
        self.event_engine: Optional[EventEngine] = None
        self.tick_collector: Optional[Any] = None  # EventDrivenCollector when real websocket
        self.bar_generators: Dict[str, List[BarGenerator]] = {}  # instrument -> [generators]
        self.indicator_handler: Optional[RealTimeIndicatorHandler] = None
        self.store: Optional[RedisMarketStore] = None
        
        self.running = False
        self.bars_generated = 0
        
        # Detect mode
        self.mode = get_execution_mode()
        
        logger.info("=" * 70)
        logger.info("EVENT-DRIVEN PIPELINE RUNNER")
        logger.info("=" * 70)
        logger.info(f"Architecture: WebSocket → EventEngine → BarGenerator → Indicators")
        logger.info(f"WebSocket Type: {websocket_type.upper()}")
        logger.info(f"Execution Mode: {self.mode.upper()}")
        logger.info(f"Instruments: {', '.join(self.instruments)}")
        logger.info(f"Timeframes: {', '.join(self.timeframes.keys())}")
        logger.info("=" * 70)
    
    def start(self) -> None:
        """Start the complete event-driven pipeline."""
        if self.running:
            logger.warning("Pipeline already running")
            return
        
        try:
            # Step 1: Initialize Redis Store
            logger.info("📦 Initializing Redis Store...")
            redis_client = redis.Redis(host='localhost', port=6380, decode_responses=True)
            self.store = RedisMarketStore(redis_client, mode=self.mode.upper())
            
            # Step 2: Start EventEngine (message bus)
            logger.info("🚌 Starting EventEngine...")
            self.event_engine = EventEngine()
            self.event_engine.start()
            logger.info("   ✅ EventEngine running")
            
            # Step 3: Setup BarGenerators (subscribe to EVENT_TICK)
            logger.info("📊 Setting up BarGenerators...")
            self._setup_bar_generators()
            
            # Step 4: Setup Indicator Handler (subscribes to bar events)
            logger.info("✨ Setting up RealTimeIndicatorHandler...")
            self.indicator_handler = RealTimeIndicatorHandler(self.event_engine, self.store)
            
            # Step 5: Start WebSocket (PLUGGABLE: Real or Mock)
            logger.info(f"🔌 Starting {self.websocket_type.upper()} WebSocket...")
            self._start_websocket()
            
            self.running = True
            logger.info("")
            logger.info("=" * 70)
            logger.info("✅ EVENT-DRIVEN PIPELINE RUNNING")
            logger.info("=" * 70)
            logger.info("Data Flow:")
            logger.info(f"  1. WebSocket ({self.websocket_type}) → Ticks")
            logger.info(f"  2. Ticks → EventEngine (EVENT_TICK)")
            logger.info(f"  3. BarGenerator subscribes → generates bars")
            logger.info(f"  4. Bars → EventEngine (EVENT_BAR_1M, 5M, 15M, 1H)")
            logger.info(f"  5. IndicatorHandler subscribes → calculates indicators")
            logger.info(f"  6. Storage → Redis ({self.mode}:ohlc_sorted:*, {self.mode}:indicators:*)")
            logger.info("")
            logger.info("Press Ctrl+C to stop...")
            logger.info("=" * 70)
        
        except Exception as e:
            logger.error(f"Failed to start pipeline: {e}", exc_info=True)
            self.stop()
            raise
    
    def _setup_bar_generators(self) -> None:
        """Setup BarGenerators for each instrument and timeframe."""
        for instrument in self.instruments:
            generators = []
            
            # For each timeframe, create aggregator
            for tf_name, window in self.timeframes.items():
                # Determine interval (minute or hour)
                if 'h' in tf_name.lower():
                    interval = Interval.HOUR
                else:
                    interval = Interval.MINUTE
                
                # Create handler for this timeframe
                def create_bar_handler(inst, tf):
                    """Create bar close handler for specific instrument/timeframe."""
                    def on_bar(bar: OHLCBar):
                        # Update bar metadata
                        bar.instrument = inst
                        bar.timeframe = tf
                        
                        # Store bar
                        self._store_bar(bar)
                        
                        # Emit bar event
                        event_type = f"bar.{tf}"
                        self.event_engine.put(Event(event_type, bar))
                        
                        self.bars_generated += 1
                        logger.info(
                            f"📊 {tf} bar closed: {inst} "
                            f"O={bar.open:.2f} H={bar.high:.2f} L={bar.low:.2f} C={bar.close:.2f} V={bar.volume}"
                        )
                        logger.info(f"   📡 Published {event_type} event to EventEngine")
                    
                    return on_bar
                
                # For 1-minute bars
                def create_1min_handler(inst):
                    """Handler for 1-minute bars."""
                    def on_1min_bar(bar: OHLCBar):
                        bar.instrument = inst
                        bar.timeframe = "1m"
                        self._store_bar(bar)
                        self.event_engine.put(Event(EVENT_BAR_1M, bar))
                        self.bars_generated += 1
                        logger.info(
                            f"📊 1m bar: {inst} "
                            f"O={bar.open:.2f} H={bar.high:.2f} L={bar.low:.2f} C={bar.close:.2f} V={bar.volume}"
                        )
                    return on_1min_bar
                
                # Create BarGenerator
                if window == 1:
                    # 1-minute bars only
                    bg = BarGenerator(on_bar=create_1min_handler(instrument))
                else:
                    # 1-minute → X-minute/hour bars
                    bg = BarGenerator(
                        on_bar=create_1min_handler(instrument),
                        window=window,
                        on_window_bar=create_bar_handler(instrument, tf_name),
                        interval=interval
                    )
                
                generators.append(bg)
                logger.info(f"   Created BarGenerator for {instrument}:{tf_name} (window={window})")
            
            # Subscribe BarGenerators to EVENT_TICK
            def create_tick_handler(inst_generators):
                """Create tick handler that forwards to all generators."""
                def on_tick_event(event: Event):
                    tick: MarketTick = event.data
                    logger.info(f"🎯 Tick handler called for {tick.instrument}")
                    for gen in inst_generators:
                        logger.info(f"  Calling update_tick on BarGenerator for {gen}")
                        gen.update_tick(tick)
                return on_tick_event
            
            self.event_engine.register(EVENT_TICK, create_tick_handler(generators))
            self.bar_generators[instrument] = generators
        
        logger.info(f"   ✅ {len(self.bar_generators)} BarGenerators subscribed to EVENT_TICK")
    
    def _store_bar(self, bar: OHLCBar) -> None:
        """Store OHLC bar to Redis with mode prefix.
        
        Args:
            bar: OHLC bar to store
        """
        try:
            self.store.store_ohlc(bar)
        except Exception as e:
            logger.error(f"Failed to store bar: {e}")
    
    def _start_websocket(self) -> None:
        """Start WebSocket tick collector (Real or Mock)."""
        if self.websocket_type == 'mock':
            self._start_mock_websocket()
        elif self.websocket_type == 'real':
            self._start_real_websocket()
        else:
            raise ValueError(f"Unknown websocket_type: {self.websocket_type}")
    
    def _start_mock_websocket(self) -> None:
        """Start Mock WebSocket with direct EventEngine integration (no collector needed)."""
        # Create instrument tokens (mock uses simple numeric tokens)
        instruments = {}
        for i, symbol in enumerate(self.instruments):
            token = 256265 + i  # Generate sequential tokens
            instruments[str(token)] = symbol
        
        # Create Mock WebSocket
        self.mock_ticker = create_mock_ticker(
            instruments={int(k): v for k, v in instruments.items()},
            tick_interval=self.tick_interval,
            starting_price=45000.0
        )
        
        # Track last volume to calculate differenced volume
        last_volume = {}
        
        # Define callback that publishes ticks directly to EventEngine
        def on_ticks(ws, ticks):
            """Handle ticks from mock websocket - publish to EventEngine."""
            logger.info(f"🎯 on_ticks called with {len(ticks)} ticks")
            for tick_data in ticks:
                # Extract data
                instrument_token = tick_data.get('instrument_token')
                trading_symbol = instruments.get(str(instrument_token), f"TOKEN_{instrument_token}")
                ltp = tick_data.get('last_price', 0.0)
                volume = tick_data.get('volume', 0)
                
                # Calculate differenced volume
                last_vol = last_volume.get(instrument_token, 0)
                diff_volume = max(0, volume - last_vol)
                last_volume[instrument_token] = volume
                
                # Create MarketTick
                tick = MarketTick(
                    instrument=trading_symbol,
                    timestamp=datetime.now(),
                    last_price=ltp,
                    volume=diff_volume
                )
                
                # Publish to EventEngine
                if self.event_engine:
                    event = Event(EVENT_TICK, tick)
                    self.event_engine.put(event)
                    logger.debug(f"📨 Published tick: {trading_symbol} @ {ltp:.2f}")
                    logger.info(f"✅ Tick published to EventEngine: {trading_symbol}")
                else:
                    logger.error("❌ EventEngine not available!")
        
        def on_connect(ws, response):
            """Handle connection."""
            logger.info("   🔗 Mock WebSocket connected")
        
        def on_close(ws, code, reason):
            """Handle disconnection."""
            logger.warning(f"   🔌 Mock WebSocket closed: {code} - {reason}")
        
        def on_error(ws, code, reason):
            """Handle errors."""
            logger.error(f"   ❌ Mock WebSocket error: {code} - {reason}")
        
        # Set up callbacks
        self.mock_ticker.on_ticks = on_ticks
        self.mock_ticker.on_connect = on_connect
        self.mock_ticker.on_close = on_close
        self.mock_ticker.on_error = on_error
        
        print(f"DEBUG: on_ticks callback set: {self.mock_ticker.on_ticks is not None}")
        print(f"DEBUG: event_engine exists: {self.event_engine is not None}")
        logger.info(f"   🎯 Callbacks set: on_ticks={self.mock_ticker.on_ticks is not None}")
        
        # Subscribe to instruments
        self.mock_ticker.subscribe([int(token) for token in instruments.keys()])
        
        logger.info(f"   📡 Subscribed to {len(self.mock_ticker.subscribed_instruments)} instruments")
        
        # Start mock ticker
        self.mock_ticker.connect(threaded=True)
        
        # Give the background thread a moment to start
        time.sleep(0.1)
        
        logger.info(f"   ✅ Mock WebSocket started (tick_interval={self.tick_interval}s)")
        logger.info(f"   📡 Emitting ticks for: {list(instruments.values())}")
    
    def _start_real_websocket(self) -> None:
        """Start Real Kite WebSocket with EventEngine integration."""
        # Import EventDrivenCollector only when needed (avoids kiteconnect import for mock mode)
        global EventDrivenCollector
        if EventDrivenCollector is None:
            from market_data.collectors.websocket_tick_collector import WebSocketTickCollector as EventDrivenCollector
        
        # Check credentials
        api_key = os.getenv('KITE_API_KEY')
        access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        if not api_key or not access_token:
            raise RuntimeError(
                "Real WebSocket requires KITE_API_KEY and KITE_ACCESS_TOKEN environment variables.\n"
                "Run: python -m market_data.tools.kite_auth to generate credentials."
            )
        
        # Create instrument mapping
        instruments = {
            "15148802": "BANKNIFTY26FEBFUT"  # Current valid token
        }
        
        # Create tick collector WITH EventEngine
        self.tick_collector = EventDrivenCollector(
            instruments=instruments
        )
        # Manually set EventEngine (backward compatible)
        self.tick_collector.event_engine = self.event_engine
        self.tick_collector.start()
        
        logger.info("   ✅ Real Kite WebSocket started")
        logger.info(f"   📡 Subscribed to: {list(instruments.values())}")
    
    def stop(self) -> None:
        """Stop the event-driven pipeline."""
        if not self.running:
            return
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("🛑 STOPPING EVENT-DRIVEN PIPELINE")
        logger.info("=" * 70)
        
        # Force close any open bars
        if self.bar_generators:
            logger.info(f"Force closing open bars... found {len(self.bar_generators)} instruments")
            try:
                for instrument, generators in self.bar_generators.items():
                    logger.info(f"  Instrument {instrument}: {len(generators)} generators")
                    for i, gen in enumerate(generators):
                        logger.info(f"    Generator {i}: calling generate()")
                        closed_bar = gen.generate()  # Force close current bar
                        if closed_bar:
                            logger.info(f"      Force closed bar for {instrument}: {closed_bar.start_at} - {closed_bar.end_at}")
                            self.bars_generated += 1
                        else:
                            logger.info(f"      No bar to close for {instrument} generator {i}")
            except Exception as e:
                logger.error(f"Error force closing bars: {e}")
        else:
            logger.info("No bar generators to force close")
        
        # Stop WebSocket (Mock or Real)
        if self.mock_ticker:
            logger.info("Stopping Mock WebSocket...")
            try:
                self.mock_ticker.close()
            except Exception as e:
                logger.error(f"Error stopping Mock WebSocket: {e}")
        elif self.tick_collector and hasattr(self.tick_collector, 'ticker'):
            logger.info("Stopping Real WebSocket...")
            try:
                self.tick_collector.stop()
            except Exception as e:
                logger.error(f"Error stopping Real WebSocket: {e}")
        
        # Stop EventEngine
        if self.event_engine:
            logger.info("Stopping EventEngine...")
            try:
                self.event_engine.stop()
            except Exception as e:
                logger.error(f"Error stopping EventEngine: {e}")
        
        self.running = False
        
        # Print stats
        logger.info("")
        logger.info("📈 STATISTICS:")
        logger.info(f"  Bars Generated: {self.bars_generated}")
        if self.indicator_handler:
            logger.info(f"  Indicators Calculated: {self.indicator_handler.indicators_calculated}")
        if self.event_engine:
            stats = self.event_engine.get_stats()
            logger.info(f"  EventEngine Events: {stats['event_count']}")
            logger.info(f"  EventEngine Errors: {stats['error_count']}")
    
    def run(self) -> None:
        """Run until interrupted."""
        # Setup signal handlers
        def signal_handler(sig, frame):
            logger.info("\n⚠️  Interrupt received, shutting down gracefully...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start pipeline
        self.start()
        
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Event-Driven Pipeline: WebSocket → EventEngine → Bars → Indicators",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Mock WebSocket (default):
  python simple_runner.py --websocket mock
  
  # Real Kite WebSocket:
  python simple_runner.py --websocket real
  
  # Fast ticks for testing:
  python simple_runner.py --websocket mock --tick-interval 0.5
  
  # Multiple instruments:
  python simple_runner.py --instruments BANKNIFTY26FEBFUT NIFTY26FEBFUT
        """
    )
    
    parser.add_argument(
        '--websocket',
        choices=['mock', 'real'],
        default='mock',
        help='WebSocket type: mock (synthetic ticks) or real (Zerodha Kite)'
    )
    
    parser.add_argument(
        '--instruments',
        nargs='+',
        default=['BANKNIFTY26FEBFUT'],
        help='Instrument symbols to track'
    )
    
    parser.add_argument(
        '--tick-interval',
        type=float,
        default=1.0,
        help='Seconds between ticks (mock only, default: 1.0)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Define timeframes (1min base → multi-timeframe)
    timeframes = {
        '5min': 5,
        '15min': 15,
    }
    
    # Create and run pipeline
    runner = EventDrivenPipelineRunner(
        websocket_type=args.websocket,
        instruments=args.instruments,
        timeframes=timeframes,
        tick_interval=args.tick_interval
    )
    
    runner.run()


if __name__ == '__main__':
    main()
