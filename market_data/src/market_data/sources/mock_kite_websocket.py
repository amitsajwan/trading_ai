"""Mock Kite WebSocket - Generates synthetic ticks matching Real Kite WebSocket format.

This is a DROP-IN REPLACEMENT for KiteTicker that:
1. Emits ticks in EXACT Kite WebSocket format
2. Uses same interface (on_ticks, on_connect, etc.)
3. Generates realistic price movements (random walk)
4. Supports multiple instruments
5. Can be swapped with Real KiteTicker by changing 1 line of code

Architecture: Mock Generator → Same Tick Format → Same Handler → Redis → API → Dashboard

Usage:
    # Real Kite WebSocket:
    ticker = KiteTicker(api_key, access_token)
    
    # Mock (IDENTICAL INTERFACE):
    ticker = MockKiteTicker()
    
    # Same code from here:
    ticker.on_ticks = handle_ticks
    ticker.on_connect = handle_connect
    ticker.subscribe([256265])
    ticker.connect()
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Callable, Optional, Any
import random

logger = logging.getLogger(__name__)


class MockKiteTicker:
    """
    Mock implementation of KiteTicker WebSocket.
    
    Generates synthetic ticks matching Real Kite WebSocket format exactly.
    Drop-in replacement - uses identical interface.
    """
    
    # Mode constants (matching KiteTicker)
    MODE_LTP = "ltp"
    MODE_QUOTE = "quote"
    MODE_FULL = "full"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
        tick_interval: float = 1.0,
        price_volatility: float = 0.002,
        starting_price: float = 45000.0
    ):
        """
        Initialize Mock Kite WebSocket.
        
        Args:
            api_key: Ignored (for interface compatibility)
            access_token: Ignored (for interface compatibility)
            tick_interval: Seconds between ticks (default: 1.0)
            price_volatility: Price change % per tick (default: 0.2%)
            starting_price: Initial price for instruments
        """
        self.api_key = api_key
        self.access_token = access_token
        self.tick_interval = tick_interval
        self.price_volatility = price_volatility
        self.starting_price = starting_price
        
        # Callbacks (matching KiteTicker interface)
        self.on_ticks: Optional[Callable] = None
        self.on_connect: Optional[Callable] = None
        self.on_close: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_message: Optional[Callable] = None
        self.on_reconnect: Optional[Callable] = None
        self.on_noreconnect: Optional[Callable] = None
        
        # WebSocket state
        self.connected = False
        self.running = False
        self._thread: Optional[threading.Thread] = None
        
        # Instrument tracking
        self.subscribed_instruments: List[int] = []
        self.instrument_states: Dict[int, Dict[str, Any]] = {}
        self.mode: str = self.MODE_FULL
        
        # Simulated timestamp for testing bar generation
        self.current_timestamp = datetime.now(timezone.utc)
        
        logger.info(f"MockKiteTicker initialized (tick_interval={tick_interval}s)")
    
    def connect(self, threaded: bool = False, disable_ssl_verification: bool = False) -> None:
        """
        Start mock WebSocket connection.
        
        Args:
            threaded: Run in background thread (default: False)
            disable_ssl_verification: Ignored (for interface compatibility)
        """
        if self.running:
            logger.warning("MockKiteTicker already running")
            return
        
        self.running = True
        self.connected = True
        
        # Call on_connect callback
        if self.on_connect:
            try:
                self.on_connect(self, {"status": "Connected to Mock WebSocket"})
            except Exception as e:
                logger.error(f"Error in on_connect callback: {e}")
        
        # Start tick generation
        if threaded:
            self._thread = threading.Thread(target=self._tick_generator, daemon=True)
            self._thread.start()
            logger.info("MockKiteTicker started in background thread")
        else:
            logger.info("MockKiteTicker started (blocking mode)")
            self._tick_generator()
    
    def close(self, code: int = 1000, reason: str = "User closed connection") -> None:
        """
        Stop mock WebSocket connection.
        
        Args:
            code: Close code (default: 1000)
            reason: Close reason
        """
        if not self.running:
            return
        
        logger.info(f"Closing MockKiteTicker: {reason}")
        self.running = False
        self.connected = False
        
        # Call on_close callback
        if self.on_close:
            try:
                self.on_close(self, code, reason)
            except Exception as e:
                logger.error(f"Error in on_close callback: {e}")
        
        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
    
    def subscribe(self, instrument_tokens: List[int]) -> None:
        """
        Subscribe to instruments.
        
        Args:
            instrument_tokens: List of instrument tokens
        """
        for token in instrument_tokens:
            if token not in self.subscribed_instruments:
                self.subscribed_instruments.append(token)
                # Initialize state for new instrument
                self._init_instrument_state(token)
        
        logger.info(f"MockKiteTicker subscribed to {len(instrument_tokens)} instruments")
    
    def unsubscribe(self, instrument_tokens: List[int]) -> None:
        """
        Unsubscribe from instruments.
        
        Args:
            instrument_tokens: List of instrument tokens
        """
        for token in instrument_tokens:
            if token in self.subscribed_instruments:
                self.subscribed_instruments.remove(token)
                if token in self.instrument_states:
                    del self.instrument_states[token]
        
        logger.info(f"MockKiteTicker unsubscribed from {len(instrument_tokens)} instruments")
    
    def set_mode(self, mode: str, instrument_tokens: List[int]) -> None:
        """
        Set tick mode (ltp, quote, full).
        
        Args:
            mode: Mode (MODE_LTP, MODE_QUOTE, MODE_FULL)
            instrument_tokens: Instruments to apply mode to
        """
        self.mode = mode
        logger.info(f"MockKiteTicker mode set to: {mode}")
    
    def _init_instrument_state(self, token: int) -> None:
        """Initialize state for an instrument."""
        # Use token to generate deterministic starting price
        random.seed(token)
        price_base = self.starting_price + (token % 10000) * 10
        
        self.instrument_states[token] = {
            'last_price': price_base,
            'open': price_base,
            'high': price_base,
            'low': price_base,
            'close': price_base,
            'volume': 0,
            'cumulative_volume': 0,
            'total_buy_quantity': random.randint(40000, 60000),
            'total_sell_quantity': random.randint(40000, 60000),
            'last_quantity': 0,
            'average_price': price_base,
            'tick_count': 0
        }
        
        # Reset random seed
        random.seed()
    
    def _tick_generator(self) -> None:
        """Background thread generating ticks."""
        logger.info("MockKiteTicker tick generator started")
        logger.info(f"MockKiteTicker: running={self.running}, subscribed_instruments={len(self.subscribed_instruments)}")
        
        while self.running:
            logger.info(f"MockKiteTicker: Loop iteration, running={self.running}, subscribed={len(self.subscribed_instruments)}")
            if not self.subscribed_instruments:
                time.sleep(0.1)
                continue
            
            # Generate ticks for all subscribed instruments
            ticks = []
            for token in self.subscribed_instruments:
                tick = self._generate_tick(token)
                ticks.append(tick)
            
            # Call on_ticks callback
            logger.info(f"MockKiteTicker: About to call on_ticks callback, callback exists: {self.on_ticks is not None}, ticks count: {len(ticks)}")
            if self.on_ticks and ticks:
                try:
                    logger.info("MockKiteTicker: Calling on_ticks callback")
                    self.on_ticks(self, ticks)
                    logger.info("MockKiteTicker: on_ticks callback completed")
                except Exception as e:
                    logger.error(f"Error in on_ticks callback: {e}", exc_info=True)
            
            # Wait for next tick
            time.sleep(1.0)
        
        logger.info("MockKiteTicker tick generator stopped")
    
    def _generate_tick(self, token: int) -> Dict[str, Any]:
        """
        Generate a single tick for an instrument.
        
        Returns tick in EXACT Kite WebSocket format.
        """
        state = self.instrument_states[token]
        state['tick_count'] += 1
        
        # Random walk price movement
        last_price = state['last_price']
        change_pct = random.gauss(0, self.price_volatility)  # Normal distribution
        new_price = last_price * (1 + change_pct)
        new_price = round(new_price, 2)
        
        # Update OHLC
        state['last_price'] = new_price
        state['high'] = max(state['high'], new_price)
        state['low'] = min(state['low'], new_price)
        state['close'] = new_price
        
        # Volume (incremental)
        tick_volume = random.randint(1, 100)
        state['volume'] += tick_volume
        state['cumulative_volume'] += tick_volume
        state['last_quantity'] = tick_volume
        
        # Buy/Sell quantities (random walk)
        state['total_buy_quantity'] += random.randint(-500, 1000)
        state['total_sell_quantity'] += random.randint(-500, 1000)
        state['total_buy_quantity'] = max(0, state['total_buy_quantity'])
        state['total_sell_quantity'] = max(0, state['total_sell_quantity'])
        
        # Average traded price (weighted)
        total_vol = state['cumulative_volume']
        if total_vol > 0:
            state['average_price'] = (
                (state['average_price'] * (total_vol - tick_volume) + new_price * tick_volume)
                / total_vol
            )
        
        # Current timestamp (incremented for testing)
        self.current_timestamp = self.current_timestamp.replace(second=0, microsecond=0)
        tick_timestamp = self.current_timestamp
        
        # Increment timestamp for next tick (10 seconds to span minutes faster)
        from datetime import timedelta
        self.current_timestamp += timedelta(seconds=10)
        
        # Build tick in EXACT Kite format
        tick = {
            'instrument_token': token,
            'last_price': new_price,
            'last_quantity': state['last_quantity'],
            'average_price': round(state['average_price'], 2),
            'volume': state['cumulative_volume'],  # Kite uses cumulative
            'buy_quantity': state['total_buy_quantity'],
            'sell_quantity': state['total_sell_quantity'],
            'timestamp': tick_timestamp,  # datetime object (Kite format)
        }
        
        # Add QUOTE mode fields
        if self.mode in [self.MODE_QUOTE, self.MODE_FULL]:
            tick.update({
                'ohlc': {
                    'open': state['open'],
                    'high': state['high'],
                    'low': state['low'],
                    'close': state['close']
                },
                'change': round(((new_price - state['open']) / state['open']) * 100, 2),
            })
        
        # Add FULL mode fields
        if self.mode == self.MODE_FULL:
            # Generate realistic depth (5 levels)
            tick.update({
                'depth': self._generate_depth(new_price),
                'last_trade_time': tick_timestamp,
                'oi': random.randint(1000000, 2000000),  # Open Interest
                'oi_day_high': random.randint(1500000, 2000000),
                'oi_day_low': random.randint(1000000, 1500000),
            })
        
        return tick
    
    def _generate_depth(self, current_price: float) -> Dict[str, List[Dict[str, Any]]]:
        """Generate realistic market depth (bid/ask stacks)."""
        buy_depth = []
        sell_depth = []
        
        tick_size = 0.05  # Typical tick size
        
        # Generate 5 levels of depth
        for i in range(5):
            # Buy side (below current price)
            buy_price = current_price - (i + 1) * tick_size
            buy_depth.append({
                'price': round(buy_price, 2),
                'quantity': random.randint(10, 500),
                'orders': random.randint(1, 20)
            })
            
            # Sell side (above current price)
            sell_price = current_price + (i + 1) * tick_size
            sell_depth.append({
                'price': round(sell_price, 2),
                'quantity': random.randint(10, 500),
                'orders': random.randint(1, 20)
            })
        
        return {
            'buy': buy_depth,
            'sell': sell_depth
        }
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self.connected


# Convenience function for building Mock WebSocket
def create_mock_ticker(
    instruments: Optional[Dict[int, str]] = None,
    tick_interval: float = 1.0,
    price_volatility: float = 0.002,
    starting_price: float = 45000.0
) -> MockKiteTicker:
    """
    Create and configure Mock Kite WebSocket.
    
    Args:
        instruments: Dict mapping tokens to symbols (for logging)
        tick_interval: Seconds between ticks
        price_volatility: Price change % per tick
        starting_price: Initial price for instruments
    
    Returns:
        Configured MockKiteTicker
    
    Example:
        >>> ticker = create_mock_ticker(
        ...     instruments={256265: 'BANKNIFTY26FEBFUT'},
        ...     tick_interval=1.0
        ... )
        >>> ticker.on_ticks = handle_ticks
        >>> ticker.subscribe([256265])
        >>> ticker.connect(threaded=True)
    """
    ticker = MockKiteTicker(
        tick_interval=tick_interval,
        price_volatility=price_volatility,
        starting_price=starting_price
    )
    
    if instruments:
        logger.info(f"Mock WebSocket configured for instruments: {list(instruments.values())}")
    
    return ticker
