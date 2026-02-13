"""Unified historical replayer.

Combines tick-level replay (CSV/Zerodha/synthetic) and JSON OHLC/tick replay
into a single interface.
"""
from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable, Tuple

from ..contracts import MarketTick, MarketIngestion, MarketStore, OHLCBar

logger = logging.getLogger(__name__)

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))


def _set_system_virtual_time(timestamp: datetime):
    """Set system-wide virtual time via Redis."""
    try:
        import redis

        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        r = redis.Redis(host=host, port=port, db=0)

        r.set("system:virtual_time:enabled", "1")
        r.set("system:virtual_time:current", timestamp.isoformat())

        logger.debug(f"Set system virtual time to: {timestamp}")
    except Exception as e:
        logger.warning(f"Could not set virtual time: {e}")


class UnifiedHistoricalReplayer(MarketIngestion):
    """Replay historical market data from multiple sources.

    Supports:
    - Zerodha OHLC (converted to ticks)
    - CSV OHLC
    - JSON OHLC/ticks
    - Synthetic ticks
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
        rebase_to: Optional[datetime] = None,
        loop: bool = False,
        start_date: Optional[datetime] = None,
    ):
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
        self.loop = loop

        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.ticks_loaded = 0
        self.ticks_replayed = 0

        # Rebase options: if rebase is True, ticks are shifted by offset so they
        # appear as 'now' (or rebase_to) instead of changing system-level virtual time.
        self.rebase = rebase
        self.rebase_to = rebase_to
        self.rebase_offset: Optional[timedelta] = None
        self.start_date = start_date or (datetime.now() - timedelta(hours=1))

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
        self.store = store

    def start(self) -> None:
        if self.running:
            logger.warning("Replayer already running")
            return
        self.running = True
        self.task = asyncio.create_task(self._replay_loop())
        logger.info(f"Started historical replayer (speed={self.speed})")

    def stop(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
        logger.info("Stopped historical replayer")

    async def _replay_loop(self):
        try:
            mode, payload = self._load_events()

            if mode == "points":
                data_points: List[Dict[str, Any]] = payload
                await self._replay_points(data_points)
            else:
                ticks: List[MarketTick] = payload
                await self._replay_ticks(ticks)

        except asyncio.CancelledError:
            logger.info("Replay cancelled")
        except KeyboardInterrupt:
            logger.info("Replay interrupted by user")
        except Exception as e:
            logger.error(f"Error in replay loop: {e}", exc_info=True)
        finally:
            self.running = False

    def _load_events(self) -> Tuple[str, List[Any]]:
        if self.data_source.endswith(".json"):
            points = self._load_points_from_file()
            return "points", points

        if self.data_source == "zerodha":
            points = self._load_zerodha_points()
            return "points", points

        ticks = self._load_ticks()
        return "ticks", ticks

    async def _replay_ticks(self, ticks: List[MarketTick]) -> None:
        self.ticks_loaded = len(ticks)

        if not ticks:
            logger.error("No ticks loaded for replay")
            return

        logger.info(f"Loaded {len(ticks)} ticks, starting replay...")

        # If running synthetic replay AND we're doing an instant-load run (speed<=0),
        # pre-populate OHLC bars in the store so consumers see charts immediately.
        # For paced/streaming runs (speed>0), avoid pre-populating so OHLC builds
        # and pub/sub messages arrive over time.
        if self.data_source == "synthetic" and not (self.speed and self.speed > 0):
            try:
                synthetic_bars = self._ticks_to_bars(ticks)
                for bar in synthetic_bars:
                    try:
                        self.store.store_ohlc(bar)
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"Failed to pre-populate synthetic OHLC bars: {e}")

        # If rebase is enabled, compute offset to make first tick land at rebase_to or now
        if self.rebase:
            first_ts = ticks[0].timestamp
            target = self.rebase_to or datetime.now(IST)
            if first_ts.tzinfo is not None and target.tzinfo is None:
                target = target.replace(tzinfo=first_ts.tzinfo)
            elif first_ts.tzinfo is None and target.tzinfo is not None:
                first_ts = first_ts.replace(tzinfo=target.tzinfo)
            self.rebase_offset = target - first_ts
            logger.info(f"Rebase enabled: offset={self.rebase_offset}")

        paced = bool(self.speed and self.speed > 0)
        if paced:
            logger.info(f"Streaming {len(ticks)} ticks (speed={self.speed} ticks/sec)...")
        else:
            logger.info(f"Loading {len(ticks)} ticks instantly (speed={self.speed})...")

        for tick in ticks:
            if not self.running:
                break

            if self.rebase and self.rebase_offset is not None:
                tick.original_timestamp = tick.timestamp
                tick.timestamp = tick.timestamp + self.rebase_offset
            else:
                use_virtual = os.getenv("USE_VIRTUAL_TIME", "0").lower() in ("1", "true", "yes")
                if use_virtual:
                    _set_system_virtual_time(tick.timestamp)

            self.store.store_tick(tick)

            if self.on_tick_callback:
                try:
                    if asyncio.iscoroutinefunction(self.on_tick_callback):
                        await self.on_tick_callback(tick)
                    else:
                        self.on_tick_callback(tick)
                except Exception as e:
                    logger.error(f"Error in tick callback: {e}")

            self.ticks_replayed += 1
            if self.ticks_replayed % 100 == 0:
                await asyncio.sleep(0)
                logger.info(
                    f"Loaded {self.ticks_replayed}/{self.ticks_loaded} ticks "
                    f"({self.ticks_replayed*100//self.ticks_loaded}%)"
                )

            # Pace streaming mode
            if paced:
                try:
                    await asyncio.sleep(1.0 / float(self.speed))
                except Exception:
                    await asyncio.sleep(0)

        if ticks:
            logger.info(
                f"✅ Historical data loaded: {self.ticks_replayed} ticks from "
                f"{ticks[0].timestamp} to {ticks[-1].timestamp}"
            )

    async def _replay_points(self, data_points: List[Dict[str, Any]]) -> None:
        if not data_points:
            logger.error("No data points loaded for replay")
            return

        while self.running:
            for point in data_points:
                if not self.running:
                    break

                await self._store_data_point(point)

                if self.speed and self.speed > 0:
                    await asyncio.sleep(1.0 / float(self.speed))

            if not self.loop:
                break

    def _load_ticks(self) -> List[MarketTick]:
        if self.data_source == "zerodha":
            return self._load_from_zerodha()
        if self.data_source.endswith(".csv"):
            return self._load_from_csv()
        if self.data_source == "synthetic":
            logger.info("Generating synthetic ticks for 'synthetic' data_source")
            start_time = self.rebase_to or datetime.now(IST)
            try:
                duration_minutes = int(os.getenv("SYNTHETIC_DURATION_MINUTES", "390"))
            except Exception:
                duration_minutes = 390
            ticks = self._generate_synthetic_ticks(
                start_time=start_time,
                duration_minutes=duration_minutes,
                base_price=45000.0,
                instrument=self.instrument_symbol,
            )
            logger.info(f"Generated {len(ticks)} synthetic ticks")
            return ticks

        logger.error(f"Unknown or unsupported data source: {self.data_source}")
        logger.error("Supported sources: 'zerodha', 'synthetic', CSV path, or JSON path")
        return []

    def _load_points_from_file(self) -> List[Dict[str, Any]]:
        try:
            path = Path(self.data_source)
            if path.exists():
                with open(path) as f:
                    return json.load(f)
            logger.warning(f"Data file {self.data_source} not found, using synthetic data")
            return self._generate_synthetic_points()
        except Exception as e:
            logger.error(f"Error loading data from {self.data_source}: {e}")
            return self._generate_synthetic_points()

    def _generate_synthetic_points(self) -> List[Dict[str, Any]]:
        data_points = []
        base_time = self.start_date
        base_price = 45100.0

        for i in range(60):
            timestamp = base_time + timedelta(minutes=i)
            price_change = (i % 10 - 5) * 15
            trend = (i // 20) * 50

            open_price = base_price + trend + price_change
            high_price = open_price + abs(price_change) + 10
            low_price = open_price - abs(price_change) - 10
            close_price = open_price + (price_change * 0.8)

            num_ticks = 5 + (i % 5)
            tick_volume = 1000 + (i * 50)
            total_volume = tick_volume * num_ticks

            tick_data = []
            for tick_idx in range(num_ticks):
                tick_time = timestamp + timedelta(seconds=tick_idx * 12)
                tick_price_change = (tick_idx - num_ticks // 2) * 5
                tick_price = open_price + tick_price_change
                tick_price = max(low_price, min(high_price, tick_price))

                tick_data.append(
                    {
                        "timestamp": tick_time.isoformat(),
                        "instrument": self.instrument_symbol,
                        "price": tick_price,
                        "volume": tick_volume,
                    }
                )

            data_points.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "instrument": self.instrument_symbol,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": total_volume,
                    "ticks": tick_data,
                }
            )

        return data_points

    def _load_from_csv(self) -> List[MarketTick]:
        ticks: List[MarketTick] = []
        path = Path(self.data_source)

        if not path.exists():
            logger.error(f"CSV file not found: {self.data_source}")
            return []

        try:
            with open(path, "r") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        date_str = row.get("Date", "").strip()
                        time_str = row.get("Time", "").strip()

                        if not date_str or not time_str:
                            continue

                        dt_str = f"{date_str} {time_str}"
                        timestamp = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                        timestamp = timestamp.replace(tzinfo=IST)

                        close_price = float(row.get("Close", 0))
                        volume = int(float(row.get("Volume", 0)))

                        candle_ticks = [
                            MarketTick(
                                instrument=self.instrument_symbol,
                                timestamp=timestamp,
                                last_price=close_price,
                                volume=volume,
                            )
                        ]

                        ticks.extend(candle_ticks)
                    except Exception as e:
                        logger.warning(f"Error parsing CSV row: {e}, row: {row}")
                        continue

            ticks.sort(key=lambda t: t.timestamp)
            logger.info(f"Loaded {len(ticks)} ticks from CSV")
            return ticks

        except Exception as e:
            logger.error(f"Error loading CSV: {e}", exc_info=True)
            return []

    def _load_from_zerodha(self) -> List[MarketTick]:
        """Backward-compatible tick loader.

        Prefer _load_zerodha_points() for candle-paced replay so bars are
        written progressively rather than all at once.
        """
        points = self._load_zerodha_points()
        ticks: List[MarketTick] = []
        for point in points:
            ts = point.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if not isinstance(ts, datetime):
                continue
            ticks.append(
                MarketTick(
                    instrument=point.get("instrument") or self.instrument_symbol,
                    timestamp=ts,
                    last_price=float(point.get("close", 0.0)),
                    volume=int(point.get("volume", 0) or 0),
                    open_interest=point.get("oi") or point.get("open_interest"),
                )
            )

        ticks.sort(key=lambda t: t.timestamp)
        return ticks

    def _load_zerodha_points(self) -> List[Dict[str, Any]]:
        if not self.kite:
            logger.error("Kite client not provided for Zerodha historical data")
            return []

        if not self.from_date or not self.to_date:
            logger.error("from_date and to_date required for Zerodha historical data")
            return []

        try:
            instrument_token = self._get_instrument_token(self.instrument_symbol)
            if not instrument_token:
                logger.error(f"Instrument token not found for {self.instrument_symbol}")
                return []

            logger.info(
                f"Fetching historical data from Zerodha: {self.instrument_symbol} "
                f"({self.from_date} to {self.to_date}, interval={self.interval})"
            )

            use_continuous = self.instrument_symbol.upper().endswith('FUT')

            try:
                historical_data = self.kite.historical_data(
                    instrument_token=instrument_token,
                    from_date=self.from_date,
                    to_date=self.to_date,
                    interval=self.interval,
                    continuous=use_continuous,
                    oi=True,
                )
            except Exception as e:
                if "invalid interval for continuous data" in str(e):
                    historical_data = self.kite.historical_data(
                        instrument_token=instrument_token,
                        from_date=self.from_date,
                        to_date=self.to_date,
                        interval=self.interval,
                        continuous=False,
                        oi=True,
                    )
                else:
                    raise

            logger.info(f"Kite API returned {len(historical_data) if historical_data else 0} candles")
            if historical_data:
                sample = historical_data[0]
                logger.info(f"Sample candle: volume={sample.get('volume', 'N/A')}, date={sample.get('date', 'N/A')}")

            if not historical_data:
                logger.warning("No historical data returned from Zerodha")
                return []

            spot_volumes = {}
            use_spot_volume = os.getenv("USE_SPOT_VOLUME", "true").lower() == "true"
            total_futures_volume = sum(c.get("volume", 0) for c in historical_data)

            if use_spot_volume and total_futures_volume == 0:
                logger.info("Futures volume is zero, attempting to fetch from spot index...")
                spot_volumes = self._fetch_spot_volume(self.from_date, self.to_date, self.interval)

            points: List[Dict[str, Any]] = []
            for candle in historical_data:
                timestamp = candle.get("date")
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                elif isinstance(timestamp, datetime):
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=IST)

                market_open = timestamp.replace(hour=9, minute=15, second=0, microsecond=0)
                market_close = timestamp.replace(hour=15, minute=30, second=0, microsecond=0)

                if timestamp < market_open or timestamp > market_close:
                    continue

                open_price = float(candle.get("open", 0))
                high_price = float(candle.get("high", 0))
                low_price = float(candle.get("low", 0))
                close_price = float(candle.get("close", 0))
                volume = int(candle.get("volume", 0))
                open_interest = candle.get("oi") if candle.get("oi") is not None else candle.get("open_interest")

                if volume == 0 and spot_volumes:
                    timestamp_key = timestamp.replace(second=0, microsecond=0).isoformat()
                    if timestamp_key in spot_volumes:
                        volume = spot_volumes[timestamp_key]

                points.append(
                    {
                        "timestamp": timestamp,
                        "open": open_price,
                        "high": high_price,
                        "low": low_price,
                        "close": close_price,
                        "volume": volume,
                        "oi": open_interest,
                        "instrument": self._resolve_instrument_key(),
                    }
                )

            points.sort(key=lambda p: p["timestamp"])
            logger.info(f"Loaded {len(points)} Zerodha candles for paced replay")
            return points

        except Exception as e:
            logger.error(f"Error loading historical data from Zerodha: {e}", exc_info=True)
            return []

    def _resolve_instrument_key(self) -> str:
        try:
            from config import get_config

            config = get_config()
            return config.instrument_key
        except Exception:
            return self.instrument_symbol.upper().replace(" ", "")

    def _get_instrument_token(self, instrument_symbol: str) -> Optional[int]:
        try:
            symbol_upper = instrument_symbol.upper()
            symbol_variations = [instrument_symbol, symbol_upper]

            if "BANK" in symbol_upper and "NIFTY" in symbol_upper:
                if "NIFTY BANK" not in symbol_variations:
                    symbol_variations.append("NIFTY BANK")
                if "BANKNIFTY" not in symbol_variations:
                    symbol_variations.append("BANKNIFTY")
                if "NIFTYBANK" not in symbol_variations:
                    symbol_variations.append("NIFTYBANK")

            # For futures contracts, search NFO first for exact trading symbol or current active
            if symbol_upper.endswith('FUT'):
                instruments = self.kite.instruments("NFO")
                # First try exact match
                for inst in instruments:
                    tradingsymbol = inst.get("tradingsymbol", "").upper()
                    if tradingsymbol == symbol_upper:
                        token = inst.get("instrument_token")
                        if token:
                            logger.info(
                                f"Found instrument token {token} for {instrument_symbol} "
                                f"(matched: {inst.get('tradingsymbol')} in NFO)"
                            )
                            return token
                # If not found, find the current active FUT for the base symbol
                base_symbol = symbol_upper.replace('FUT', '').replace('26', '').replace('24', '')  # Remove year and FUT
                fut_instruments = [inst for inst in instruments if inst.get("instrument_type") == "FUT" and inst.get("name", "").upper() == base_symbol]
                if fut_instruments:
                    # Sort by expiry date descending to get the latest
                    fut_instruments.sort(key=lambda x: x.get("expiry", ""), reverse=True)
                    inst = fut_instruments[0]
                    token = inst.get("instrument_token")
                    if token:
                        logger.info(
                            f"Found current active instrument token {token} for {instrument_symbol} "
                            f"(matched: {inst.get('tradingsymbol')} in NFO)"
                        )
                        return token

            # Search NSE for indices
            instruments = self.kite.instruments("NSE")
            for inst in instruments:
                tradingsymbol = inst.get("tradingsymbol", "").upper()
                name = inst.get("name", "").upper()
                for var in symbol_variations:
                    var_upper = var.upper()
                    if tradingsymbol == var_upper or name == var_upper:
                        token = inst.get("instrument_token")
                        if token:
                            logger.info(
                                f"Found instrument token {token} for {instrument_symbol} "
                                f"(matched: {inst.get('tradingsymbol')} in NSE)"
                            )
                            return token

            # Search NFO for other instruments
            instruments = self.kite.instruments("NFO")
            for inst in instruments:
                name = inst.get("name", "").upper()
                tradingsymbol = inst.get("tradingsymbol", "").upper()
                for var in symbol_variations:
                    var_upper = var.upper()
                    if name == var_upper or tradingsymbol == var_upper:
                        token = inst.get("instrument_token")
                        if token:
                            logger.info(
                                f"Found instrument token {token} for {instrument_symbol} "
                                f"(matched: {inst.get('tradingsymbol')} in NFO)"
                            )
                            return token

            logger.warning(
                f"Instrument token not found for {instrument_symbol} (tried variations: {symbol_variations})"
            )
            return None

        except Exception as e:
            logger.error(f"Error getting instrument token: {e}")
            return None

    def _fetch_spot_volume(self, from_date: date, to_date: date, interval: str) -> Dict[str, int]:
        if not self.kite:
            return {}

        try:
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

            instruments = self.kite.instruments(exchange)
            spot_token = None
            for inst in instruments:
                tradingsymbol = inst.get("tradingsymbol", "")
                instrument_type = inst.get("instrument_type", "")
                segment = inst.get("segment", "")

                if (
                    tradingsymbol.upper() == spot_symbol.replace(" ", "").upper()
                    or tradingsymbol.upper() == spot_symbol.upper()
                ) and (instrument_type == "EQ" or segment in ("INDICES", "NSE")):
                    if "FUT" not in tradingsymbol and "CE" not in tradingsymbol and "PE" not in tradingsymbol:
                        spot_token = inst.get("instrument_token")
                        logger.info(
                            f"Found spot index token {spot_token} for {spot_symbol} "
                            f"(segment: {segment}, type: {instrument_type})"
                        )
                        break

            if not spot_token:
                logger.warning(f"Could not find spot index token for {spot_symbol}")
                return {}

            spot_data = self.kite.historical_data(
                instrument_token=spot_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval,
                continuous=False,
                oi=False,
            )

            if not spot_data:
                logger.warning("No spot data returned")
                return {}

            volumes = {}
            for candle in spot_data:
                timestamp = candle.get("date")
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                elif isinstance(timestamp, datetime):
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=IST)

                timestamp_key = timestamp.replace(second=0, microsecond=0).isoformat()
                volumes[timestamp_key] = int(candle.get("volume", 0))

            return volumes

        except Exception as e:
            logger.warning(f"Failed to fetch spot volume: {e}")
            return {}

    def _ticks_to_bars(self, ticks_list: List[MarketTick]) -> List[OHLCBar]:
        bars: List[OHLCBar] = []
        if not ticks_list:
            return bars

        groups: Dict[str, List[MarketTick]] = {}
        for tick in ticks_list:
            minute = tick.timestamp.replace(second=0, microsecond=0)
            key = minute.isoformat()
            groups.setdefault(key, []).append(tick)

        for group_ticks in groups.values():
            opens = group_ticks[0].last_price
            closes = group_ticks[-1].last_price
            highs = max(t.last_price for t in group_ticks)
            lows = min(t.last_price for t in group_ticks)
            volume = sum((t.volume or 0) for t in group_ticks)
            start_at = group_ticks[0].timestamp.replace(second=0, microsecond=0)
            bars.append(
                OHLCBar(
                    instrument=(group_ticks[0].instrument or self.instrument_symbol),
                    timeframe="1min",
                    open=opens,
                    high=highs,
                    low=lows,
                    close=closes,
                    volume=volume,
                    start_at=start_at,
                    end_at=start_at + timedelta(minutes=1),
                )
            )
        return bars

    async def _store_data_point(self, point: Dict[str, Any]) -> None:
        try:
            ts_raw = point.get("timestamp")
            if isinstance(ts_raw, str):
                timestamp = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            elif isinstance(ts_raw, datetime):
                timestamp = ts_raw
            else:
                timestamp = datetime.now(IST)

            instrument = point.get("instrument") or self.instrument_symbol

            if self.rebase:
                if self.rebase_offset is None:
                    first_ts = timestamp
                    target = self.rebase_to or datetime.now(timezone.utc)
                    if target.tzinfo is not None:
                        target = target.replace(tzinfo=None)
                    self.rebase_offset = target - first_ts
                timestamp = timestamp + self.rebase_offset
            else:
                use_virtual = os.getenv("USE_VIRTUAL_TIME", "0").lower() in ("1", "true", "yes")
                if use_virtual:
                    _set_system_virtual_time(timestamp)

            if all(k in point for k in ["open", "high", "low", "close"]):
                bar = OHLCBar(
                    instrument=instrument,
                    timeframe="1min",
                    open=point["open"],
                    high=point["high"],
                    low=point["low"],
                    close=point["close"],
                    volume=point.get("volume", 0),
                    open_interest=point.get("oi") or point.get("open_interest"),
                    start_at=timestamp,
                    end_at=timestamp + timedelta(minutes=1),
                )
                self.store.store_ohlc(bar)

                if self.on_candle_callback:
                    try:
                        self.on_candle_callback(
                            {
                                "timestamp": timestamp,
                                "open": point["open"],
                                "high": point["high"],
                                "low": point["low"],
                                "close": point["close"],
                                "volume": point.get("volume", 0),
                                "oi": point.get("oi") or point.get("open_interest"),
                                "instrument": instrument,
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error in candle callback: {e}")

            if "ticks" in point:
                for tick_data in point["ticks"]:
                    tick_ts = tick_data.get("timestamp")
                    if isinstance(tick_ts, str):
                        tick_ts = datetime.fromisoformat(tick_ts.replace("Z", "+00:00"))
                    tick = MarketTick(
                        instrument=instrument,
                        timestamp=tick_ts,
                        last_price=tick_data["price"],
                        volume=tick_data.get("volume"),
                        open_interest=tick_data.get("oi") or tick_data.get("open_interest"),
                    )
                    self.store.store_tick(tick)
            elif "close" in point:
                tick = MarketTick(
                    instrument=instrument,
                    timestamp=timestamp,
                    last_price=point["close"],
                    volume=point.get("volume"),
                    open_interest=point.get("oi") or point.get("open_interest"),
                )
                self.store.store_tick(tick)

        except Exception as e:
            logger.error(f"Error storing data point: {e}")

    def _generate_synthetic_ticks(
        self,
        start_time: Optional[datetime] = None,
        duration_minutes: int = 60,
        base_price: float = 45000.0,
        instrument: Optional[str] = None,
    ) -> List[MarketTick]:
        if instrument is None:
            instrument = self.instrument_symbol or "BANKNIFTY"
        if start_time is None:
            start_time = datetime.now(IST).replace(hour=9, minute=15, second=0, microsecond=0)

        ticks: List[MarketTick] = []
        current_time = start_time
        price = base_price

        import random

        for _ in range(duration_minutes):
            for tick_idx in range(4):
                tick_time = current_time + timedelta(seconds=tick_idx * 15)
                price_change = random.uniform(-10, 10)
                price = max(1000, price + price_change)

                ticks.append(
                    MarketTick(
                        instrument=instrument,
                        timestamp=tick_time,
                        last_price=round(price, 2),
                        volume=random.randint(1000, 10000),
                    )
                )

            current_time += timedelta(minutes=1)

        return ticks

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "ticks_loaded": self.ticks_loaded,
            "ticks_replayed": self.ticks_replayed,
            "running": self.running,
            "speed": self.speed,
        }
