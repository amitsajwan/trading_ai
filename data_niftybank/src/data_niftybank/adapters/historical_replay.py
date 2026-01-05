"""Historical data replay adapter for testing without live market data."""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..contracts import MarketIngestion, MarketStore, MarketTick, OHLCBar

logger = logging.getLogger(__name__)


class HistoricalDataReplay(MarketIngestion):
    """Replay historical market data for testing and backtesting.

    Can load data from JSON files or generate synthetic data for testing
    when live market data is not available.
    """

    def __init__(self, store: MarketStore, data_source: str = "synthetic"):
        """Initialize historical data replay.

        Args:
            store: MarketStore to write replayed data to
            data_source: "synthetic" for generated data, or path to JSON file
        """
        self.store = store
        self.data_source = data_source
        self.running = False
        self.task: Optional[asyncio.Task] = None

        # Replay configuration
        self.speed_multiplier = 1.0  # 1.0 = real-time, 2.0 = 2x speed
        self.loop = True  # Loop data when it ends

    def bind_store(self, store: MarketStore) -> None:
        """Bind market store (already done in __init__)."""
        self.store = store

    def start(self) -> None:
        """Start historical data replay."""
        if self.running:
            return

        self.running = True
        self.task = asyncio.create_task(self._replay_loop())

    def stop(self) -> None:
        """Stop historical data replay."""
        self.running = False
        if self.task:
            self.task.cancel()

    async def _replay_loop(self):
        """Main replay loop."""
        try:
            data_points = self._load_data()

            while self.running:
                for point in data_points:
                    if not self.running:
                        break

                    # Convert data point to tick/bar and store
                    await self._store_data_point(point)

                    # Wait based on speed multiplier
                    if self.speed_multiplier > 0:
                        await asyncio.sleep(1.0 / self.speed_multiplier)

                if not self.loop:
                    break

        except Exception as e:
            logger.error(f"Error in replay loop: {e}")
        finally:
            self.running = False

    def _load_data(self) -> List[Dict[str, Any]]:
        """Load historical data from source."""
        if self.data_source == "synthetic":
            return self._generate_synthetic_data()
        else:
            return self._load_from_file()

    def _generate_synthetic_data(self) -> List[Dict[str, Any]]:
        """Generate synthetic market data for testing."""
        data_points = []
        base_time = datetime.now() - timedelta(hours=1)
        base_price = 45100.0  # BANKNIFTY price level

        # Generate 60 minutes of 1-minute bars with multiple ticks per minute
        for i in range(60):
            timestamp = base_time + timedelta(minutes=i)

            # Simulate some price movement
            price_change = (i % 10 - 5) * 15  # -75 to +75 range
            trend = (i // 20) * 50  # Gradual trend

            open_price = base_price + trend + price_change
            high_price = open_price + abs(price_change) + 10
            low_price = open_price - abs(price_change) - 10
            close_price = open_price + (price_change * 0.8)

            # Generate multiple ticks per minute for better VWAP calculation
            num_ticks = 5 + (i % 5)  # 5-9 ticks per minute
            tick_volume = 1000 + (i * 50)  # Base tick volume
            total_volume = tick_volume * num_ticks

            # Create individual ticks within this minute
            tick_data = []
            for tick_idx in range(num_ticks):
                tick_time = timestamp + timedelta(seconds=tick_idx * 12)  # Spread over minute

                # Price movement within the bar
                tick_price_change = (tick_idx - num_ticks//2) * 5
                tick_price = open_price + tick_price_change

                # Ensure tick price is within OHLC bounds
                tick_price = max(low_price, min(high_price, tick_price))

                tick_data.append({
                    "timestamp": tick_time.isoformat(),
                    "instrument": "BANKNIFTY",
                    "price": tick_price,
                    "volume": tick_volume
                })

            data_points.append({
                "timestamp": timestamp.isoformat(),
                "instrument": "BANKNIFTY",
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": total_volume,
                "ticks": tick_data  # Store individual ticks
            })

            # Store individual ticks in Redis for VWAP calculation
            if hasattr(self.store, 'redis_client') and self.store.redis_client:
                try:
                    for tick in tick_data:
                        tick_obj = MarketTick(
                            instrument="BANKNIFTY",
                            timestamp=datetime.fromisoformat(tick["timestamp"]),
                            last_price=tick["price"],
                            volume=tick["volume"]
                        )
                        self.store.store_tick(tick_obj)

                    # Update aggregate data
                    volume_key = f"volume:BANKNIFTY:latest"
                    oi_key = f"oi:BANKNIFTY:latest"

                    # Accumulate volume over time
                    total_volume = sum(dp["volume"] for dp in data_points[-60:])  # Last hour
                    self.store.redis_client.set(volume_key, str(int(total_volume)))
                    self.store.redis_client.set(oi_key, "2500000")  # Sample OI
                except Exception as e:
                    logger.warning(f"Redis storage error: {e}")

        return data_points

    def _load_from_file(self) -> List[Dict[str, Any]]:
        """Load data from JSON file."""
        try:
            path = Path(self.data_source)
            if path.exists():
                with open(path) as f:
                    return json.load(f)
            else:
                logger.warning(f"Data file {self.data_source} not found, using synthetic data")
                return self._generate_synthetic_data()
        except Exception as e:
            logger.error(f"Error loading data from {self.data_source}: {e}")
            return self._generate_synthetic_data()

    async def _store_data_point(self, point: Dict[str, Any]):
        """Store a data point in the market store."""
        try:
            timestamp = datetime.fromisoformat(point["timestamp"])
            instrument = point["instrument"]

            # Store as OHLC bar
            if all(k in point for k in ["open", "high", "low", "close"]):
                bar = OHLCBar(
                    instrument=instrument,
                    timeframe="1min",
                    open=point["open"],
                    high=point["high"],
                    low=point["low"],
                    close=point["close"],
                    volume=point.get("volume", 0),
                    start_at=timestamp
                )
                self.store.store_ohlc(bar)

            # Store individual ticks if available (for VWAP calculation)
            if "ticks" in point:
                for tick_data in point["ticks"]:
                    tick = MarketTick(
                        instrument=instrument,
                        timestamp=datetime.fromisoformat(tick_data["timestamp"]),
                        last_price=tick_data["price"],
                        volume=tick_data["volume"]
                    )
                    self.store.store_tick(tick)
            # Fallback: store single tick using close price
            elif "close" in point:
                tick = MarketTick(
                    instrument=instrument,
                    timestamp=timestamp,
                    last_price=point["close"],
                    volume=point.get("volume")
                )
                self.store.store_tick(tick)

        except Exception as e:
            logger.error(f"Error storing data point: {e}")


class LTPDataAdapter(MarketIngestion):
    """Adapter for LTPDataCollector - REST API based data collection."""

    def __init__(self, kite, market_memory):
        """Initialize LTP data adapter.

        Args:
            kite: KiteConnect instance
            market_memory: MarketMemory instance
        """
        self.kite = kite
        self.market_memory = market_memory
        self.collector = None
        self.store: Optional[MarketStore] = None

    def bind_store(self, store: MarketStore) -> None:
        """Bind market store."""
        self.store = store

    def start(self) -> None:
        """Start LTP data collection."""
        if self.collector is None:
            # Import here to avoid circular imports
            from data.ltp_data_collector import LTPDataCollector
            self.collector = LTPDataCollector(self.kite, self.market_memory)

        logger.info("Starting LTP data collection...")
        # LTP collector typically runs on a schedule, not continuously
        # For testing, we might want to trigger collection manually

    def stop(self) -> None:
        """Stop LTP data collection."""
        if self.collector:
            logger.info("Stopping LTP data collection...")
            # LTP collector cleanup if needed
