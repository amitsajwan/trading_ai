"""Example momentum trading strategy.

Demonstrates complete VN.py-inspired architecture:
- Event-driven tick ingestion
- Tick → Bar aggregation via BarGenerator
- Time series management via ArrayManager
- Momentum indicator calculation
- Signal generation

Strategy Logic:
- Buy when: Momentum > 0, RSI < 30 (oversold), MACD histogram positive
- Sell when: Momentum < -10 or RSI > 70 (overbought)
- Short when: Momentum < 0, RSI > 70 (overbought), MACD histogram negative
- Cover when: Momentum > 10 or RSI < 30 (oversold)

Usage:
    from market_data.strategy.momentum_strategy import MomentumStrategy
    from market_data.strategy.strategy_template import StrategyConfig
    from market_data.event_engine import EventEngine
    
    engine = EventEngine()
    config = StrategyConfig(
        strategy_name="MOM_15M",
        instruments=["BANKNIFTY26FEBFUT"],
        parameters={
            "mom_period": 10,
            "rsi_period": 14,
            "fast_size": 1
        }
    )
    
    strategy = MomentumStrategy(config, engine)
    strategy.on_init()
    strategy.on_start()
    
    # Feed ticks
    strategy.on_tick(tick)
"""

import logging
from typing import Optional

from .strategy_template import StrategyTemplate, StrategyConfig
from ..bar_generator import BarGenerator, Interval
from ..array_manager import ArrayManager
from ..contracts import MarketTick, OHLCBar
from ..event_engine import EventEngine

logger = logging.getLogger(__name__)


class MomentumStrategy(StrategyTemplate):
    """Momentum-based trading strategy.
    
    Uses multiple momentum indicators to identify trend strength:
    - MOM: Momentum (rate of change)
    - RSI: Relative Strength Index (overbought/oversold)
    - MACD: Moving Average Convergence Divergence (trend)
    
    Operates on 15-minute bars for medium-term signals.
    """
    
    # Strategy parameters (can be overridden in config)
    mom_period = 10          # Momentum lookback period
    rsi_period = 14          # RSI period
    rsi_overbought = 70      # RSI overbought threshold
    rsi_oversold = 30        # RSI oversold threshold
    macd_fast = 12           # MACD fast period
    macd_slow = 26           # MACD slow period
    macd_signal = 9          # MACD signal period
    fixed_size = 1           # Position size
    
    def __init__(
        self,
        config: StrategyConfig,
        event_engine: Optional[EventEngine] = None
    ):
        """Initialize momentum strategy.
        
        Args:
            config: Strategy configuration
            event_engine: Event engine for publishing signals
        """
        super().__init__(config, event_engine)
        
        # Override parameters from config
        for key, value in self.parameters.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        # Bar generator: Tick → 1-min → 15-min bars
        self.bg = BarGenerator(
            on_bar=self.on_bar,
            window=15,
            on_window_bar=self.on_15min_bar,
            interval=Interval.MINUTE
        )
        
        # Array manager: stores last 100 bars
        self.am = ArrayManager(size=100)
        
        # Strategy state
        self.mom_value = 0.0
        self.rsi_value = 0.0
        self.macd = 0.0
        self.macd_signal_value = 0.0
        self.macd_hist = 0.0
        
        # Trading state
        self.last_signal = None
        self.bars_since_trade = 0
    
    def on_init(self):
        """Initialize strategy."""
        self.write_log("Momentum strategy initializing")
        self.write_log(f"Parameters: MOM={self.mom_period}, RSI={self.rsi_period}")
        self.write_log(f"Timeframe: 15-minute bars")
        
        # TODO: Load historical data for backtesting
        # For now, strategy will wait for live data
        
        self.inited = True
        self.write_log("Strategy initialized successfully")
    
    def on_start(self):
        """Start strategy trading."""
        super().on_start()
        self.write_log(f"Monitoring {len(self.instruments)} instruments")
    
    def on_tick(self, tick: MarketTick):
        """Process tick data.
        
        Feeds tick to BarGenerator for aggregation.
        
        Args:
            tick: Market tick data
        """
        if not self.trading:
            return
        
        # Feed to bar generator
        self.bg.update_tick(tick)
    
    def on_bar(self, bar: OHLCBar):
        """Process 1-minute bar.
        
        Passes to BarGenerator for 15-minute aggregation.
        
        Args:
            bar: 1-minute OHLC bar
        """
        # Feed to window generator
        self.bg.update_bar(bar)
    
    def on_15min_bar(self, bar: OHLCBar):
        """Process 15-minute bar and generate signals.
        
        Main strategy logic:
        1. Update time series
        2. Calculate momentum indicators
        3. Generate trading signals
        4. Execute orders
        
        Args:
            bar: 15-minute OHLC bar
        """
        if not self.trading:
            return
        
        # Update array manager
        self.am.update_bar(bar)
        
        # Need enough data to calculate indicators
        if not self.am.inited:
            self.write_log(f"Warming up... {self.am.count}/{self.am.size} bars")
            return
        
        # ═══════════════════════════════════════════════════════
        # Calculate momentum indicators
        # ═══════════════════════════════════════════════════════
        try:
            self.mom_value = self.am.mom(self.mom_period)
            self.rsi_value = self.am.rsi(self.rsi_period)
            self.macd, self.macd_signal_value, self.macd_hist = self.am.macd(
                self.macd_fast,
                self.macd_slow,
                self.macd_signal
            )
        except Exception as e:
            self.write_log(f"Error calculating indicators: {e}")
            return
        
        # Log indicators
        self.write_log(
            f"Bar: {bar.start_at.strftime('%H:%M')} | "
            f"Close: {bar.close:.2f} | "
            f"MOM: {self.mom_value:.2f} | "
            f"RSI: {self.rsi_value:.2f} | "
            f"MACD Hist: {self.macd_hist:.2f}"
        )
        
        # ═══════════════════════════════════════════════════════
        # Generate trading signals
        # ═══════════════════════════════════════════════════════
        instrument = self.instruments[0]
        current_pos = self.get_position(instrument)
        
        # Track bars since last trade
        self.bars_since_trade += 1
        
        # No position: look for entry
        if current_pos == 0:
            self._check_entry_signals(bar, instrument)
        
        # Long position: look for exit
        elif current_pos > 0:
            self._check_long_exit(bar, instrument)
        
        # Short position: look for exit
        elif current_pos < 0:
            self._check_short_exit(bar, instrument)
        
        # Update UI
        self.put_event()
    
    def _check_entry_signals(self, bar: OHLCBar, instrument: str):
        """Check for entry signals.
        
        Args:
            bar: Current bar
            instrument: Instrument to trade
        """
        # BULLISH MOMENTUM: Enter long
        if (
            self.mom_value > 0 and                    # Positive momentum
            self.rsi_value < self.rsi_oversold and    # Oversold condition
            self.macd_hist > 0                        # MACD histogram positive
        ):
            self.write_log(
                f"🟢 LONG SIGNAL: MOM={self.mom_value:.2f}, "
                f"RSI={self.rsi_value:.2f}, MACD_H={self.macd_hist:.2f}"
            )
            self.buy(bar.close + 5, self.fixed_size, instrument)
            self.last_signal = "LONG"
            self.bars_since_trade = 0
        
        # BEARISH MOMENTUM: Enter short
        elif (
            self.mom_value < 0 and                     # Negative momentum
            self.rsi_value > self.rsi_overbought and   # Overbought condition
            self.macd_hist < 0                         # MACD histogram negative
        ):
            self.write_log(
                f"🔴 SHORT SIGNAL: MOM={self.mom_value:.2f}, "
                f"RSI={self.rsi_value:.2f}, MACD_H={self.macd_hist:.2f}"
            )
            self.short(bar.close - 5, self.fixed_size, instrument)
            self.last_signal = "SHORT"
            self.bars_since_trade = 0
    
    def _check_long_exit(self, bar: OHLCBar, instrument: str):
        """Check for long exit signals.
        
        Args:
            bar: Current bar
            instrument: Instrument to trade
        """
        # EXIT LONG: Momentum turning negative OR RSI overbought
        if (
            self.mom_value < -10 or                    # Strong negative momentum
            self.rsi_value > self.rsi_overbought or    # Overbought
            self.macd_hist < -5                        # MACD turning down
        ):
            self.write_log(
                f"🔵 EXIT LONG: MOM={self.mom_value:.2f}, "
                f"RSI={self.rsi_value:.2f}, MACD_H={self.macd_hist:.2f} "
                f"(held {self.bars_since_trade} bars)"
            )
            pos = self.get_position(instrument)
            self.sell(bar.close - 5, abs(pos), instrument)
            self.last_signal = "EXIT_LONG"
            self.bars_since_trade = 0
    
    def _check_short_exit(self, bar: OHLCBar, instrument: str):
        """Check for short exit signals.
        
        Args:
            bar: Current bar
            instrument: Instrument to trade
        """
        # EXIT SHORT: Momentum turning positive OR RSI oversold
        if (
            self.mom_value > 10 or                     # Strong positive momentum
            self.rsi_value < self.rsi_oversold or      # Oversold
            self.macd_hist > 5                         # MACD turning up
        ):
            self.write_log(
                f"🟡 EXIT SHORT: MOM={self.mom_value:.2f}, "
                f"RSI={self.rsi_value:.2f}, MACD_H={self.macd_hist:.2f} "
                f"(held {self.bars_since_trade} bars)"
            )
            pos = self.get_position(instrument)
            self.cover(bar.close + 5, abs(pos), instrument)
            self.last_signal = "EXIT_SHORT"
            self.bars_since_trade = 0
    
    def get_stats(self) -> dict:
        """Get strategy statistics.
        
        Returns:
            Dictionary with strategy stats
        """
        return {
            "strategy_name": self.strategy_name,
            "inited": self.inited,
            "trading": self.trading,
            "position": {inst: self.pos[inst] for inst in self.instruments},
            "indicators": {
                "momentum": self.mom_value,
                "rsi": self.rsi_value,
                "macd": self.macd,
                "macd_signal": self.macd_signal_value,
                "macd_hist": self.macd_hist,
            },
            "last_signal": self.last_signal,
            "bars_since_trade": self.bars_since_trade,
            "am_count": self.am.count,
            "am_inited": self.am.inited,
        }
