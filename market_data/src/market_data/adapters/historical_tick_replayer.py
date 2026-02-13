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
        on_candle_callback: Optional[Callable[[Any], None]] = None,
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
        self.on_candle_callback = on_candle_callback
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

    # Backwards-compatible alias for tests and external callers that expect
    # a 'speed_multiplier' attribute. This maps directly to the instance's
    # 'speed' attribute so both remain in sync.
    @property
    def speed_multiplier(self) -> float:
        return self.speed

    @speed_multiplier.setter
    def speed_multiplier(self, value: float) -> None:
        try:
            self.speed = float(value)
        except Exception:
            self.speed = value

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

            # If running synthetic replay, pre-populate OHLC bars in the store so
            # in-memory stores (which don't build candles automatically) have data
            if self.data_source == "synthetic":
                try:
                    from ..contracts import OHLCBar

                    # Aggregate ticks into 1-minute OHLC bars
                    def ticks_to_bars(ticks_list):
                        bars = []
                        if not ticks_list:
                            return bars
                        # Group by minute
                        groups = {}
                        for t in ticks_list:
                            minute = t.timestamp.replace(second=0, microsecond=0)
                            key = minute.isoformat()
                            groups.setdefault(key, []).append(t)

                        for k, group_ticks in groups.items():
                            opens = group_ticks[0].last_price
                            closes = group_ticks[-1].last_price
                            highs = max(t.last_price for t in group_ticks)
                            lows = min(t.last_price for t in group_ticks)
                            volume = sum((t.volume or 0) for t in group_ticks)
                            start_at = group_ticks[0].timestamp.replace(second=0, microsecond=0)
                            bars.append(OHLCBar(
                                instrument=(group_ticks[0].instrument or self.instrument_symbol),
                                timeframe="1min",
                                open=opens,
                                high=highs,
                                low=lows,
                                close=closes,
                                volume=volume,
                                start_at=start_at,
                                end_at=start_at + timedelta(minutes=1)
                            ))
                        return bars

                    synthetic_bars = ticks_to_bars(ticks)
                    for bar in synthetic_bars:
                        try:
                            self.store.store_ohlc(bar)
                        except Exception:
                            # Ignore failures for stores that don't support OHLC
                            pass
                except Exception as e:
                    logger.debug(f"Failed to pre-populate synthetic OHLC bars: {e}")

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

            # IMPORTANT: Historical data loading should be INSTANT, not streamed
            # In reality, historical_data() is a REST API call that returns all data at once
            # The "speed" parameter is only for testing/development to simulate gradual loading
            # For production, always use speed=0.0 (instant load)
            
            # Load all ticks instantly (matching Zerodha API reality)
            logger.info(f"Loading {len(ticks)} ticks instantly (speed={self.speed})...")
            
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
                
                # Yield control periodically for large datasets
                if self.ticks_replayed % 100 == 0:
                    await asyncio.sleep(0)  # Yield to event loop
                
                # Log progress every 100 ticks
                if self.ticks_replayed % 100 == 0:
                    logger.info(f"Loaded {self.ticks_replayed}/{self.ticks_loaded} ticks ({self.ticks_replayed*100//self.ticks_loaded}%)")
            
            logger.info(f"✅ Historical data loaded: {self.ticks_replayed} ticks from {ticks[0].timestamp} to {ticks[-1].timestamp}")
            logger.info(f"📊 Coverage: 9:15 AM to 3:30 PM on {self.from_date}")
            
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
            # Generate synthetic ticks for testing
            logger.info("Generating synthetic ticks for 'synthetic' data_source")
            start_time = self.rebase_to or datetime.now(IST)
            # Default duration: 60 minutes for quick tests
            ticks = self._generate_synthetic_ticks(start_time=start_time, duration_minutes=60, base_price=45000.0, instrument=self.instrument_symbol)
            logger.info(f"Generated {len(ticks)} synthetic ticks")
            return ticks
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
                        
                        # For CSV historical data, just use close price to avoid artificial swings
                        from ..contracts import MarketTick
                        candle_ticks = [MarketTick(
                            instrument="BANKNIFTY",
                            timestamp=timestamp,
                            last_price=close_price,
                            volume=volume
                        )]
                        
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
            # IMPORTANT: For futures intraday data, use continuous=False
            # - continuous=True is mainly for long-term daily charts across expiries
            # - For minute/5minute data on active contracts, use continuous=False for accurate volume
            use_continuous = False  # Use False for accurate volume data on active contracts
            
            logger.info(
                f"Fetching with continuous={use_continuous}, interval={self.interval}, oi=True"
            )
            
            try:
                historical_data = self.kite.historical_data(
                    instrument_token=instrument_token,
                    from_date=self.from_date,
                    to_date=self.to_date,
                    interval=self.interval,
                    continuous=use_continuous,
                    oi=True  # Always include Open Interest for futures
                )
                
                logger.info(f"API returned {len(historical_data) if historical_data else 0} candles")
                if historical_data and len(historical_data) > 0:
                    # Check volume data in response
                    volumes = [c.get('volume', 0) for c in historical_data[:10]]
                    logger.info(f"Volume sample (first 10 candles): {volumes}")
                    total_volume = sum(c.get('volume', 0) for c in historical_data)
                    logger.info(f"Total volume across all candles: {total_volume}")
            except Exception as e:
                if "invalid interval for continuous data" in str(e):
                    # Fallback: retry without continuous mode
                    logger.warning(f"Continuous mode failed for {self.interval}, retrying without continuous")
                    historical_data = self.kite.historical_data(
                        instrument_token=instrument_token,
                        from_date=self.from_date,
                        to_date=self.to_date,
                        interval=self.interval,
                        continuous=False,
                        oi=True
                    )
                else:
                    raise
            
            if not historical_data:
                logger.warning("No historical data returned from Zerodha")
                return []
            
            logger.info(f"Fetched {len(historical_data)} candles from Zerodha")
            
            # DEBUG: Log first few candles to verify volume data
            if historical_data:
                logger.info(f"First candle sample: {historical_data[0]}")
                if len(historical_data) > 1:
                    logger.info(f"Second candle sample: {historical_data[1]}")

            # Try to get volume from spot index if futures has no volume
            spot_volumes = {}
            use_spot_volume = os.getenv('USE_SPOT_VOLUME', 'true').lower() == 'true'
            total_futures_volume = sum(c.get('volume', 0) for c in historical_data)
            
            if use_spot_volume and total_futures_volume == 0:
                logger.info("Futures volume is zero, attempting to fetch from spot index...")
                spot_volumes = self._fetch_spot_volume(self.from_date, self.to_date, self.interval)
                if spot_volumes:
                    logger.info(f"✅ Fetched volume from spot index: {len(spot_volumes)} candles")
                else:
                    logger.warning("⚠️ Could not fetch volume from spot index")
            
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
                open_interest = candle.get("oi") if candle.get("oi") is not None else candle.get("open_interest")
                
                # Use spot volume if futures volume is zero
                if volume == 0 and spot_volumes:
                    # Match by timestamp
                    timestamp_key = timestamp.replace(second=0, microsecond=0).isoformat()
                    if timestamp_key in spot_volumes:
                        volume = spot_volumes[timestamp_key]
                        if volume > 0:
                            logger.debug(f"Using spot volume {volume} for {timestamp}")
                
                # DEBUG: Log if we find non-zero volume
                if volume > 0 and candle.get("volume", 0) > 0:
                    logger.info(f"Found futures volume: {volume} for candle at {timestamp}")

                # For historical OHLC data, just use close price to avoid artificial price swings
                # Historical OHLC candles don't contain intra-minute price movements
                from ..contracts import MarketTick, OHLCBar
                
                # Use the configured instrument symbol for storage
                # This allows dynamic instrument configuration (BANKNIFTY, BANKNIFTY26JANFUT, etc.)
                from config import get_config
                config = get_config()
                normalized_instrument = config.instrument_key
                
                # Store the OHLC bar
                ohlc_bar = OHLCBar(
                    instrument=normalized_instrument,
                    timeframe="1min",  # Assuming 1-minute candles from Zerodha
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume,
                    open_interest=open_interest,
                    start_at=timestamp,
                    end_at=timestamp + timedelta(minutes=1)
                )
                self.store.store_ohlc(ohlc_bar)

                # Fire candle callback if provided
                if self.on_candle_callback:
                    try:
                        self.on_candle_callback({
                            "timestamp": timestamp,
                            "open": open_price,
                            "high": high_price,
                            "low": low_price,
                            "close": close_price,
                            "volume": volume,
                            "oi": open_interest,
                            "instrument": normalized_instrument,
                        })
                    except Exception as e:
                        logger.error(f"Error in candle callback: {e}")
                
                candle_ticks = [MarketTick(
                    instrument=normalized_instrument,
                    timestamp=timestamp,
                    last_price=close_price,
                    volume=volume,  # Allow 0 volume, don't set to None
                    open_interest=open_interest
                )]

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
            # Normalize symbol variations
            symbol_upper = instrument_symbol.upper()
            symbol_variations = [instrument_symbol, symbol_upper]
            
            # Add common variations
            if "BANK" in symbol_upper and "NIFTY" in symbol_upper:
                if "NIFTY BANK" not in symbol_variations:
                    symbol_variations.append("NIFTY BANK")
                if "BANKNIFTY" not in symbol_variations:
                    symbol_variations.append("BANKNIFTY")
                if "NIFTYBANK" not in symbol_variations:
                    symbol_variations.append("NIFTYBANK")
            
            # Try NSE first (for equity/index) - index uses "NIFTY BANK" as tradingsymbol
            instruments = self.kite.instruments("NSE")
            for inst in instruments:
                tradingsymbol = inst.get("tradingsymbol", "").upper()
                name = inst.get("name", "").upper()
                for var in symbol_variations:
                    var_upper = var.upper()
                    if tradingsymbol == var_upper or name == var_upper:
                        token = inst.get("instrument_token")
                        if token:
                            logger.info(f"Found instrument token {token} for {instrument_symbol} (matched: {inst.get('tradingsymbol')})")
                            return token
            
            # Try NFO (for futures/options) - futures use "BANKNIFTY" as name
            instruments = self.kite.instruments("NFO")
            for inst in instruments:
                name = inst.get("name", "").upper()
                for var in symbol_variations:
                    var_upper = var.upper()
                    if name == var_upper:
                        # Get the nearest expiry future
                        if inst.get("instrument_type") == "FUT":
                            token = inst.get("instrument_token")
                            if token:
                                logger.info(f"Found instrument token {token} for {instrument_symbol} (matched: {inst.get('name')})")
                                return token
            
            logger.warning(f"Instrument token not found for {instrument_symbol} (tried variations: {symbol_variations})")
            return None
            
        except Exception as e:
            logger.error(f"Error getting instrument token: {e}")
            return None
    
    def _fetch_spot_volume(self, from_date: date, to_date: date, interval: str) -> Dict[str, int]:
        """Fetch volume data from spot index (NSE:NIFTY BANK) to supplement futures data.
        
        Args:
            from_date: Start date
            to_date: End date
            interval: Candle interval
            
        Returns:
            Dictionary mapping ISO timestamp to volume
        """
        if not self.kite:
            return {}
        
        try:
            # Map instrument symbol to spot index
            symbol_upper = self.instrument_symbol.upper()
            if "BANK" in symbol_upper and "NIFTY" in symbol_upper:
                spot_symbol = "NIFTY BANK"
                exchange = "NSE"
            elif "NIFTY" in symbol_upper and "BANK" not in symbol_upper:
                spot_symbol = "NIFTY 50"
                exchange = "NSE"
            else:
                logger.debug(f"No spot index mapping for {self.instrument_symbol}")
                return {}
            
            # Get spot index token
            instruments = self.kite.instruments(exchange)
            spot_token = None
            for inst in instruments:
                # Look for exact match on tradingsymbol (for NSE indices, tradingsymbol = name)
                tradingsymbol = inst.get("tradingsymbol", "")
                instrument_type = inst.get("instrument_type", "")
                
                # For NSE, indices have segment="INDICES"
                segment = inst.get("segment", "")
                
                # Match on tradingsymbol AND ensure it's an index (not FUT/CE/PE)
                if (tradingsymbol.upper() == spot_symbol.replace(" ", "").upper() or \
                    tradingsymbol.upper() == spot_symbol.upper()) and \
                   (instrument_type == "EQ" or segment == "INDICES" or segment == "NSE"):
                    # Make sure it's not a futures contract
                    if "FUT" not in tradingsymbol and "CE" not in tradingsymbol and "PE" not in tradingsymbol:
                        spot_token = inst.get("instrument_token")
                        logger.info(f"Found spot index token {spot_token} for {spot_symbol} (segment: {segment}, type: {instrument_type})")
                        break
            
            if not spot_token:
                logger.warning(f"Could not find spot index token for {spot_symbol}")
                return {}
            
            # Fetch spot historical data
            logger.info(f"Fetching spot volume from {spot_symbol} ({exchange})...")
            spot_data = self.kite.historical_data(
                instrument_token=spot_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval,
                continuous=False,
                oi=False
            )
            
            if not spot_data:
                logger.warning("No spot data returned")
                return {}
            
            # Build timestamp -> volume mapping
            volumes = {}
            for candle in spot_data:
                timestamp = candle.get("date")
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                elif isinstance(timestamp, datetime):
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=IST)
                
                timestamp_key = timestamp.replace(second=0, microsecond=0).isoformat()
                volumes[timestamp_key] = int(candle.get("volume", 0))
            
            total_spot_volume = sum(volumes.values())
            logger.info(f"Fetched {len(volumes)} spot candles with total volume: {total_spot_volume}")
            return volumes
            
        except Exception as e:
            logger.warning(f"Failed to fetch spot volume: {e}")
            return {}
    
    def _ohlc_to_ticks(
        self,
        timestamp: datetime,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: int,
        instrument: str,
        num_ticks: int = 20
    ) -> List[MarketTick]:
        """Convert OHLC candle to multiple ticks (simulates intra-candle movement).

        This simulates how live data would arrive: multiple ticks per minute.
        """
        ticks = []

        # Create a more realistic price progression over the minute
        # Start at open, move toward high, then toward low, end at close
        import random

        # Generate smooth price progression
        prices = []
        current_price = open

        # Phase 1: Move from open toward high (first 30% of ticks)
        high_phase_ticks = max(1, int(num_ticks * 0.3))
        for i in range(high_phase_ticks):
            if i == 0:
                prices.append(open)
            else:
                # Gradually move toward high with some noise
                progress = i / high_phase_ticks
                target = open + (high - open) * progress
                noise = (high - low) * 0.01 * (random.random() - 0.5)  # Small random noise
                prices.append(target + noise)

        # Phase 2: Move from high toward low (middle 40% of ticks)
        low_phase_ticks = max(1, int(num_ticks * 0.4))
        for i in range(low_phase_ticks):
            progress = i / low_phase_ticks
            target = high - (high - low) * progress
            noise = (high - low) * 0.01 * (random.random() - 0.5)
            prices.append(target + noise)

        # Phase 3: Move from low toward close (final 30% of ticks)
        close_phase_ticks = num_ticks - high_phase_ticks - low_phase_ticks
        for i in range(close_phase_ticks):
            progress = i / close_phase_ticks
            target = low + (close - low) * progress
            noise = (high - low) * 0.01 * (random.random() - 0.5)
            prices.append(target + noise)

        # Ensure we have exactly num_ticks prices
        if len(prices) > num_ticks:
            prices = prices[:num_ticks]
        elif len(prices) < num_ticks:
            # Pad with close price if needed
            while len(prices) < num_ticks:
                prices.append(close)

        # Distribute volume across ticks
        tick_volume = volume // num_ticks
        remainder = volume % num_ticks

        for i in range(num_ticks):
            # Calculate tick timestamp (spread over 1 minute)
            tick_time = timestamp + timedelta(seconds=i * (60 // num_ticks))

            # Use generated price sequence
            price = prices[i]

            # Add remainder to last tick
            vol = tick_volume + (remainder if i == num_ticks - 1 else 0)

            tick = MarketTick(
                instrument=instrument,
                timestamp=tick_time,
                last_price=round(price, 2),  # Round to 2 decimal places
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


# Unified replayer alias (preferred)
try:
    from .unified_replayer import UnifiedHistoricalReplayer as _UnifiedHistoricalReplayer
    from .unified_replayer import IST as _UNIFIED_IST
    from .unified_replayer import _set_system_virtual_time as _unified_set_system_virtual_time

    HistoricalTickReplayer = _UnifiedHistoricalReplayer
    IST = _UNIFIED_IST
    _set_system_virtual_time = _unified_set_system_virtual_time
except Exception:
    # If unified replayer isn't available, keep the legacy implementation
    pass


