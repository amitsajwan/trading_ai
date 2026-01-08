"""Historical tick replayer that mimics live Zerodha WebSocket flow.

Key principle: Strategy should NOT know the difference between live and historical data.

Flow:
    Historical CSV/Zerodha API/Data → MarketTick (same structure) → Candle Builder → Indicators → Strategy
"""

import asyncio
import csv
import logging
import os
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from collections import deque

from ..contracts import MarketTick, MarketIngestion, MarketStore

logger = logging.getLogger(__name__)

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))


def _set_system_virtual_time(timestamp: datetime):
    """Set system-wide virtual time via Redis."""
    try:
        import redis
        import os
        
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        r = redis.Redis(host=host, port=port, db=0)
        
        # Enable virtual time mode
        r.set("system:virtual_time:enabled", "1")
        r.set("system:virtual_time:current", timestamp.isoformat())
        
        logger.debug(f"Set system virtual time to: {timestamp}")
    except Exception as e:
        logger.warning(f"Could not set virtual time: {e}")


class HistoricalTickReplayer(MarketIngestion):
    """Replay historical ticks in the same order and structure as live Zerodha data.
    
    This replaces the Zerodha WebSocket for backtesting. The strategy code
    remains unchanged - it just receives MarketTick objects in time order.
    """
    
    def __init__(
        self,
        store: MarketStore,
        data_source: str,
        speed: float = 0.0,
        on_tick_callback: Optional[Callable[[MarketTick], None]] = None,
        kite=None,
        instrument_symbol: str = "NIFTY BANK",
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        interval: str = "minute",
        rebase: bool = False,
        rebase_to: Optional[datetime] = None
    ):
        """Initialize historical tick replayer.
        
        Args:
            store: MarketStore to write ticks to
            data_source: "zerodha" for API, path to CSV file, or "synthetic" for generated data
            speed: Replay speed (0.0 = instant, 1.0 = real-time, 2.0 = 2x speed)
            on_tick_callback: Optional callback function called for each tick
            kite: KiteConnect instance (required if data_source="zerodha")
            instrument_symbol: Instrument symbol (e.g., "NIFTY BANK", "BANKNIFTY")
            from_date: Start date for historical data (required if data_source="zerodha")
            to_date: End date for historical data (required if data_source="zerodha")
            interval: Data interval ("minute", "3minute", "5minute", "day", etc.)
        """
        self.store = store
        self.data_source = data_source
        self.speed = speed
        self.on_tick_callback = on_tick_callback
        self.kite = kite
        self.instrument_symbol = instrument_symbol
        self.from_date = from_date
        self.to_date = to_date
        self.interval = interval
        
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.ticks_loaded = 0
        self.ticks_replayed = 0

        # Rebase options: if rebase is True, ticks are shifted by offset so they
        # appear as 'now' (or rebase_to) instead of changing system-level virtual time.
        self.rebase = rebase
        self.rebase_to = rebase_to
        self.rebase_offset = None  # type: Optional[timedelta]        
    def bind_store(self, store: MarketStore) -> None:
        """Bind market store."""
        self.store = store
    
    def start(self) -> None:
        """Start historical tick replay."""
        if self.running:
            logger.warning("Replayer already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._replay_loop())
        logger.info(f"Started historical tick replayer (speed={self.speed})")
    
    def stop(self) -> None:
        """Stop historical tick replay."""
        self.running = False
        if self.task:
            self.task.cancel()
        logger.info("Stopped historical tick replayer")
    
    async def _replay_loop(self):
        """Main replay loop - replays ticks in chronological order."""
        try:
            ticks = self._load_ticks()
            self.ticks_loaded = len(ticks)
            
            if not ticks:
                logger.error("No ticks loaded for replay")
                return
            
            logger.info(f"Loaded {len(ticks)} ticks, starting replay...")
            
            # If rebase is enabled, compute offset to make first tick land at rebase_to or now
            if self.rebase:
                first_ts = ticks[0].timestamp
                target = self.rebase_to or datetime.now(IST)
                # Ensure both datetimes are in the same timezone state for subtraction
                if first_ts.tzinfo is not None and target.tzinfo is None:
                    # first_ts is aware, target is naive - make target aware
                    target = target.replace(tzinfo=first_ts.tzinfo)
                elif first_ts.tzinfo is None and target.tzinfo is not None:
                    # first_ts is naive, target is aware - make first_ts aware
                    first_ts = first_ts.replace(tzinfo=target.tzinfo)
                self.rebase_offset = target - first_ts
                logger.info(f"Rebase enabled: offset={self.rebase_offset}")

            # Calculate sleep duration based on speed
            sleep_duration = 0.0
            if self.speed > 0:
                # Calculate average time between ticks
                if len(ticks) > 1:
                    time_span = (ticks[-1].timestamp - ticks[0].timestamp).total_seconds()
                    avg_interval = time_span / len(ticks) if len(ticks) > 1 else 1.0
                    sleep_duration = avg_interval / self.speed
            
            last_timestamp = None
            
            for tick in ticks:
                if not self.running:
                    break

                # Adjust timestamp if rebase mode
                if self.rebase and self.rebase_offset is not None:
                    tick.original_timestamp = tick.timestamp
                    tick.timestamp = tick.timestamp + self.rebase_offset
                else:
                    # Only set system virtual time when not rebasing and when enabled via env
                    use_virtual = os.getenv('USE_VIRTUAL_TIME', '0').lower() in ('1', 'true', 'yes')
                    if use_virtual:
                        _set_system_virtual_time(tick.timestamp)
                
                # Store tick in market store (same as live data)
                self.store.store_tick(tick)
                
                # Call callback if provided (for strategy/indicators)
                if self.on_tick_callback:
                    try:
                        if asyncio.iscoroutinefunction(self.on_tick_callback):
                            await self.on_tick_callback(tick)
                        else:
                            self.on_tick_callback(tick)
                    except Exception as e:
                        logger.error(f"Error in tick callback: {e}")
                
                self.ticks_replayed += 1
                
                # Sleep to simulate real-time (if speed > 0)
                if self.speed > 0 and sleep_duration > 0:
                    await asyncio.sleep(sleep_duration)
                elif self.speed == 0.0 and self.ticks_replayed % 1000 == 0:
                    # Yield control periodically even at instant speed for large datasets
                    await asyncio.sleep(0)  # Yield to event loop
                
                # Log progress every 100 ticks (or more frequently for large datasets)
                log_interval = 100 if self.ticks_loaded < 1000 else 1000
                if self.ticks_replayed % log_interval == 0:
                    logger.info(f"Replayed {self.ticks_replayed}/{self.ticks_loaded} ticks ({self.ticks_replayed*100//self.ticks_loaded}%)")
            
            logger.info(f"Replay complete: {self.ticks_replayed} ticks replayed")
            
        except asyncio.CancelledError:
            logger.info("Replay cancelled")
        except KeyboardInterrupt:
            logger.info("Replay interrupted by user")
        except Exception as e:
            logger.error(f"Error in replay loop: {e}", exc_info=True)
        finally:
            self.running = False
    
    def _load_ticks(self) -> List[MarketTick]:
        """Load historical ticks from data source."""
        if self.data_source == "zerodha":
            return self._load_from_zerodha()
        elif self.data_source.endswith('.csv'):
            return self._load_from_csv()
        elif self.data_source == "synthetic":
            # Synthetic data generation removed - only real data sources allowed
            logger.error("Synthetic data generation is not allowed. Use 'zerodha' or CSV file.")
            return []
        else:
            logger.error(f"Unknown or unsupported data source: {self.data_source}")
            logger.error("Supported sources: 'zerodha' or path to CSV file")
            return []
    
    def _load_from_csv(self) -> List[MarketTick]:
        """Load ticks from CSV file (BankNifty 1-minute format).
        
        Expected CSV format:
            Date,Time,Open,High,Low,Close,Volume
            2024-01-15,09:15,45000,45100,44950,45050,1500000
        """
        ticks = []
        path = Path(self.data_source)
        
        if not path.exists():
            logger.error(f"CSV file not found: {self.data_source}")
            return []
        
        try:
            with open(path, 'r') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    try:
                        # Parse date and time
                        date_str = row.get('Date', '').strip()
                        time_str = row.get('Time', '').strip()
                        
                        if not date_str or not time_str:
                            continue
                        
                        # Combine date and time
                        dt_str = f"{date_str} {time_str}"
                        timestamp = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                        timestamp = timestamp.replace(tzinfo=IST)
                        
                        # Parse OHLC
                        open_price = float(row.get('Open', 0))
                        high_price = float(row.get('High', 0))
                        low_price = float(row.get('Low', 0))
                        close_price = float(row.get('Close', 0))
                        volume = int(float(row.get('Volume', 0)))
                        
                        # Convert OHLC candle to ticks
                        # Method 2: Multiple ticks per candle (more realistic)
                        candle_ticks = self._ohlc_to_ticks(
                            timestamp=timestamp,
                            open=open_price,
                            high=high_price,
                            low=low_price,
                            close=close_price,
                            volume=volume,
                            instrument="BANKNIFTY"
                        )
                        
                        ticks.extend(candle_ticks)
                        
                    except Exception as e:
                        logger.warning(f"Error parsing CSV row: {e}, row: {row}")
                        continue
            
            # Sort by timestamp to ensure chronological order
            ticks.sort(key=lambda t: t.timestamp)
            
            logger.info(f"Loaded {len(ticks)} ticks from CSV")
            return ticks
            
        except Exception as e:
            logger.error(f"Error loading CSV: {e}", exc_info=True)
            return []
    
    def _load_from_zerodha(self) -> List[MarketTick]:
        """Load historical data from Zerodha API using kite.historical_data().
        
        Returns:
            List of MarketTick objects converted from OHLC candles
        """
        if not self.kite:
            logger.error("Kite client not provided for Zerodha historical data")
            return []
        
        if not self.from_date or not self.to_date:
            logger.error("from_date and to_date required for Zerodha historical data")
            return []
        
        try:
            # Get instrument token
            instrument_token = self._get_instrument_token(self.instrument_symbol)
            if not instrument_token:
                logger.error(f"Instrument token not found for {self.instrument_symbol}")
                return []
            
            logger.info(
                f"Fetching historical data from Zerodha: {self.instrument_symbol} "
                f"({self.from_date} to {self.to_date}, interval={self.interval})"
            )
            
            # Fetch historical data
            historical_data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=self.from_date,
                to_date=self.to_date,
                interval=self.interval,
                continuous=False,
                oi=False
            )
            
            if not historical_data:
                logger.warning("No historical data returned from Zerodha")
                return []
            
            logger.info(f"Fetched {len(historical_data)} candles from Zerodha")

            # Convert OHLC candles to ticks (filter for market hours only)
            ticks = []
            for candle in historical_data:
                # Parse timestamp (Zerodha returns datetime objects)
                timestamp = candle.get("date")
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                elif isinstance(timestamp, datetime):
                    # Ensure timezone aware
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=IST)

                # Filter for market hours only (9:15 AM to 3:30 PM IST)
                market_open = timestamp.replace(hour=9, minute=15, second=0, microsecond=0)
                market_close = timestamp.replace(hour=15, minute=30, second=0, microsecond=0)

                # Only process candles within market hours (9:15 AM to 3:30 PM IST)
                if timestamp.hour < 9 or (timestamp.hour == 9 and timestamp.minute < 15) or timestamp.hour > 15 or (timestamp.hour == 15 and timestamp.minute > 30):
                    continue

                # Parse OHLC
                open_price = float(candle.get("open", 0))
                high_price = float(candle.get("high", 0))
                low_price = float(candle.get("low", 0))
                close_price = float(candle.get("close", 0))
                volume = int(candle.get("volume", 0))

                # Convert OHLC candle to multiple ticks
                candle_ticks = self._ohlc_to_ticks(
                    timestamp=timestamp,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume,
                    instrument=self.instrument_symbol
                )

                ticks.extend(candle_ticks)
            
            # Sort by timestamp to ensure chronological order
            ticks.sort(key=lambda t: t.timestamp)
            
            logger.info(f"Converted {len(historical_data)} candles to {len(ticks)} ticks")
            return ticks
            
        except Exception as e:
            logger.error(f"Error loading historical data from Zerodha: {e}", exc_info=True)
            return []
    
    def _get_instrument_token(self, instrument_symbol: str) -> Optional[int]:
        """Get instrument token for a symbol.
        
        Args:
            instrument_symbol: Instrument symbol (e.g., "NIFTY BANK", "BANKNIFTY")
            
        Returns:
            Instrument token or None if not found
        """
        try:
            # Try NSE first (for equity/index)
            instruments = self.kite.instruments("NSE")
            for inst in instruments:
                if inst.get("tradingsymbol") == instrument_symbol or inst.get("name") == instrument_symbol:
                    return inst.get("instrument_token")
            
            # Try NFO (for futures/options)
            instruments = self.kite.instruments("NFO")
            for inst in instruments:
                # Match by name (e.g., "BANKNIFTY")
                if inst.get("name") == instrument_symbol:
                    # Get the nearest expiry future
                    if inst.get("instrument_type") == "FUT":
                        return inst.get("instrument_token")
            
            logger.warning(f"Instrument token not found for {instrument_symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting instrument token: {e}")
            return None
    
    def _ohlc_to_ticks(
        self,
        timestamp: datetime,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: int,
        instrument: str,
        num_ticks: int = 4
    ) -> List[MarketTick]:
        """Convert OHLC candle to multiple ticks (simulates intra-candle movement).
        
        This simulates how live data would arrive: multiple ticks per minute.
        """
        ticks = []
        
        # Price sequence: open → high → low → close (or variations)
        prices = [open, high, low, close]
        
        # Distribute volume across ticks
        tick_volume = volume // num_ticks
        remainder = volume % num_ticks
        
        for i in range(num_ticks):
            # Calculate tick timestamp (spread over 1 minute)
            tick_time = timestamp + timedelta(seconds=i * (60 // num_ticks))
            
            # Use price sequence (cycle if needed)
            price = prices[i % len(prices)]
            
            # Add remainder to last tick
            vol = tick_volume + (remainder if i == num_ticks - 1 else 0)
            
            tick = MarketTick(
                instrument=instrument,
                timestamp=tick_time,
                last_price=price,
                volume=vol
            )
            ticks.append(tick)
        
        return ticks
    
    def _generate_synthetic_ticks(
        self,
        start_time: Optional[datetime] = None,
        duration_minutes: int = 60,
        base_price: float = 45000.0,
        instrument: str = None
    ) -> List[MarketTick]:
        """Generate synthetic ticks for testing."""
        if instrument is None:
            # Use the instrument_symbol from the replayer instance (set during init)
            instrument = self.instrument_symbol or "BANKNIFTY"
        if start_time is None:
            start_time = datetime.now(IST).replace(hour=9, minute=15, second=0, microsecond=0)
        
        ticks = []
        current_time = start_time
        price = base_price
        
        import random
        
        for i in range(duration_minutes):
            # Generate 4 ticks per minute (simulating 15-second intervals)
            for tick_idx in range(4):
                tick_time = current_time + timedelta(seconds=tick_idx * 15)
                
                # Simple random walk
                price_change = random.uniform(-10, 10)
                price = max(1000, price + price_change)
                
                tick = MarketTick(
                    instrument=instrument,
                    timestamp=tick_time,
                    last_price=round(price, 2),
                    volume=random.randint(1000, 10000)
                )
                ticks.append(tick)
            
            current_time += timedelta(minutes=1)
        
        return ticks
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get replay statistics."""
        return {
            "ticks_loaded": self.ticks_loaded,
            "ticks_replayed": self.ticks_replayed,
            "running": self.running,
            "speed": self.speed
        }


