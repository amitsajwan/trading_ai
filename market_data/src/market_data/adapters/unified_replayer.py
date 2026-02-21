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
import re
import time
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable, Tuple

try:
    from kiteconnect.exceptions import TokenException
except Exception:  # pragma: no cover - optional in some test contexts
    class TokenException(Exception):
        pass

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
        self.last_error: Optional[Exception] = None

        # Rebase options: if rebase is True, ticks are shifted by offset so they
        # appear as 'now' (or rebase_to) instead of changing system-level virtual time.
        self.rebase = rebase
        self.rebase_to = rebase_to
        self.rebase_offset: Optional[timedelta] = None
        self._has_explicit_start_date = start_date is not None
        self.start_date = start_date or (datetime.now() - timedelta(hours=1))
        self._local_option_snapshots_by_minute: Dict[datetime, Dict[str, Any]] = {}
        self._local_last_snapshot_minute: Optional[datetime] = None
        self._local_redis_client = None
        self._local_prev_price: Optional[float] = None
        self._local_prev_oi: Optional[int] = None
        self._local_ema_abs_return: float = 0.0
        self._fast_forward_to_raw = (os.getenv("HISTORICAL_FAST_FORWARD_TO") or "").strip()
        self._fast_forward_speed = self._safe_float(os.getenv("HISTORICAL_FAST_FORWARD_SPEED")) or 0.0
        self._fast_forward_until: Optional[datetime] = None
        self._clock_sync_to_now = (os.getenv("HISTORICAL_CLOCK_SYNC_TO_NOW", "0").strip().lower() in ("1", "true", "yes", "on"))
        self._clock_sync_anchor = (os.getenv("HISTORICAL_CLOCK_SYNC_ANCHOR", "auto") or "auto").strip().lower()
        self._clock_sync_offset: Optional[timedelta] = None
        self._clock_sync_anchor_replay: Optional[datetime] = None
        self._clock_sync_anchor_wall: Optional[datetime] = None

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

    @staticmethod
    def _coerce_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except Exception:
                return None
        return None

    def _scaled_delay_seconds(
        self,
        previous_ts: Optional[datetime],
        current_ts: Optional[datetime],
        speed_value: Optional[float] = None,
    ) -> float:
        """Return wall-clock delay for timestamp-based replay pacing.

        speed semantics:
        - 1.0 => replay at original event intervals (real-time)
        - 2.0 => 2x faster (half delay)
        - 0.5 => 2x slower (double delay)
        - <=0 => instant load (no delay)
        """
        if previous_ts is None or current_ts is None:
            return 0.0
        speed = self.speed if speed_value is None else float(speed_value)
        if not speed or speed <= 0:
            return 0.0

        prev = previous_ts
        curr = current_ts

        if prev.tzinfo is None and curr.tzinfo is not None:
            prev = prev.replace(tzinfo=curr.tzinfo)
        elif prev.tzinfo is not None and curr.tzinfo is None:
            curr = curr.replace(tzinfo=prev.tzinfo)

        try:
            delta_seconds = (curr - prev).total_seconds()
        except Exception:
            return 0.0

        if delta_seconds <= 0:
            return 0.0

        return delta_seconds / float(speed)

    def _resolve_fast_forward_until(self, first_ts: Optional[datetime]) -> Optional[datetime]:
        if self._fast_forward_until is not None:
            return self._fast_forward_until
        raw = self._fast_forward_to_raw
        if not raw or first_ts is None:
            return None
        try:
            # Time-only form: HH:MM or HH:MM:SS (applied to replay date).
            if "T" not in raw and " " not in raw and ":" in raw:
                parts = raw.split(":")
                hh = int(parts[0])
                mm = int(parts[1]) if len(parts) > 1 else 0
                ss = int(parts[2]) if len(parts) > 2 else 0
                target = first_ts.replace(hour=hh, minute=mm, second=ss, microsecond=0)
            else:
                target = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if target.tzinfo is None and first_ts.tzinfo is not None:
                    target = target.replace(tzinfo=first_ts.tzinfo)
                elif target.tzinfo is not None and first_ts.tzinfo is None:
                    first_ts = first_ts.replace(tzinfo=target.tzinfo)
        except Exception:
            logger.warning("Invalid HISTORICAL_FAST_FORWARD_TO value: %s", raw)
            return None

        self._fast_forward_until = target
        return target

    def _effective_speed_for_timestamp(self, event_ts: Optional[datetime]) -> float:
        speed = float(self.speed or 0.0)
        if event_ts is None:
            return speed
        if self._fast_forward_speed <= 0:
            return speed
        ff_until = self._resolve_fast_forward_until(event_ts)
        if ff_until is None:
            return speed

        ts = event_ts
        if ff_until.tzinfo is None and ts.tzinfo is not None:
            ff_until = ff_until.replace(tzinfo=ts.tzinfo)
        elif ff_until.tzinfo is not None and ts.tzinfo is None:
            ts = ts.replace(tzinfo=ff_until.tzinfo)

        if ts < ff_until:
            return float(self._fast_forward_speed)
        return speed

    def _ensure_clock_sync_offset(self, first_replay_ts: Optional[datetime]) -> None:
        if not self._clock_sync_to_now:
            return
        if self._clock_sync_offset is not None:
            return
        if first_replay_ts is None:
            return

        ff_until = self._resolve_fast_forward_until(first_replay_ts)
        anchor = first_replay_ts
        anchor_mode = self._clock_sync_anchor
        if anchor_mode in ("fast_forward", "ff", "fast-forward"):
            if ff_until is not None:
                anchor = ff_until
        elif anchor_mode == "auto":
            if ff_until is not None and self._fast_forward_speed > 0:
                anchor = ff_until
        elif anchor_mode != "start":
            logger.warning("Unknown HISTORICAL_CLOCK_SYNC_ANCHOR=%s, defaulting to auto", anchor_mode)
            if ff_until is not None and self._fast_forward_speed > 0:
                anchor = ff_until

        wall_now = datetime.now(anchor.tzinfo) if anchor.tzinfo is not None else datetime.now()
        wall_anchor = wall_now

        # If we're anchoring to fast-forward target, compensate for the real-time
        # it will take to reach that target at fast-forward speed. This keeps
        # replay timestamps aligned with wall clock at the moment we hit anchor.
        if (
            ff_until is not None
            and anchor == ff_until
            and first_replay_ts is not None
            and self._fast_forward_speed > 0
        ):
            first_ts = first_replay_ts
            target_ts = anchor
            if first_ts.tzinfo is None and target_ts.tzinfo is not None:
                first_ts = first_ts.replace(tzinfo=target_ts.tzinfo)
            elif first_ts.tzinfo is not None and target_ts.tzinfo is None:
                target_ts = target_ts.replace(tzinfo=first_ts.tzinfo)
            try:
                fast_forward_span_seconds = max(0.0, (target_ts - first_ts).total_seconds())
                travel_seconds = fast_forward_span_seconds / float(self._fast_forward_speed)
                wall_anchor = wall_now + timedelta(seconds=travel_seconds)
            except Exception:
                wall_anchor = wall_now

        self._clock_sync_anchor_replay = anchor
        self._clock_sync_anchor_wall = wall_anchor
        self._clock_sync_offset = wall_anchor - anchor
        logger.info(
            "Clock-sync enabled: anchor_mode=%s replay_anchor=%s wall_anchor=%s offset=%s",
            anchor_mode,
            anchor,
            wall_anchor,
            self._clock_sync_offset,
        )

    def _map_publish_timestamp(self, source_ts: datetime) -> datetime:
        ts = source_ts
        if self._clock_sync_to_now:
            self._ensure_clock_sync_offset(ts)
            if self._clock_sync_offset is not None:
                return ts + self._clock_sync_offset
            return ts

        if self.rebase:
            if self.rebase_offset is None:
                first_ts = ts
                target = self.rebase_to or datetime.now(IST)
                if first_ts.tzinfo is not None and target.tzinfo is None:
                    target = target.replace(tzinfo=first_ts.tzinfo)
                elif first_ts.tzinfo is None and target.tzinfo is not None:
                    first_ts = first_ts.replace(tzinfo=target.tzinfo)
                self.rebase_offset = target - first_ts
                logger.info(f"Rebase enabled: offset={self.rebase_offset}")
            return ts + self.rebase_offset

        return ts

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
            self.last_error = None
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
            self.last_error = e
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

        self._ensure_clock_sync_offset(ticks[0].timestamp if ticks else None)

        paced = bool(self.speed and self.speed > 0)
        ff_until = self._resolve_fast_forward_until(ticks[0].timestamp if ticks else None)
        if paced:
            if ff_until is not None and self._fast_forward_speed > 0:
                logger.info(
                    "Streaming %d ticks with dynamic pacing (base_speed=%s, fast_forward_speed=%s until %s)",
                    len(ticks),
                    self.speed,
                    self._fast_forward_speed,
                    ff_until,
                )
            else:
                logger.info(
                    f"Streaming {len(ticks)} ticks with timestamp pacing "
                    f"(speed_multiplier={self.speed}, 1.0=real-time intervals)..."
                )
        else:
            logger.info(f"Loading {len(ticks)} ticks instantly (speed={self.speed})...")

        previous_event_ts: Optional[datetime] = None

        for tick in ticks:
            if not self.running:
                break

            source_event_ts = tick.timestamp

            effective_speed = self._effective_speed_for_timestamp(source_event_ts)
            if effective_speed > 0:
                delay_seconds = self._scaled_delay_seconds(
                    previous_event_ts,
                    source_event_ts,
                    speed_value=effective_speed,
                )
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)

            previous_event_ts = source_event_ts

            use_virtual = os.getenv("USE_VIRTUAL_TIME", "0").lower() in ("1", "true", "yes")
            publish_ts = self._map_publish_timestamp(source_event_ts)
            if publish_ts != source_event_ts:
                tick.original_timestamp = source_event_ts
            tick.timestamp = publish_ts

            if use_virtual:
                _set_system_virtual_time(tick.timestamp)

            self.store.store_tick(tick)
            self._publish_local_side_channels(tick, source_event_ts=source_event_ts)

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

        if ticks:
            logger.info(
                f"✅ Historical data loaded: {self.ticks_replayed} ticks from "
                f"{ticks[0].timestamp} to {ticks[-1].timestamp}"
            )

    async def _replay_points(self, data_points: List[Dict[str, Any]]) -> None:
        if not data_points:
            logger.error("No data points loaded for replay")
            return

        paced = bool(self.speed and self.speed > 0)
        first_point_ts = self._coerce_datetime(data_points[0].get("timestamp")) if data_points else None
        self._ensure_clock_sync_offset(first_point_ts)
        ff_until = self._resolve_fast_forward_until(first_point_ts)
        if paced and ff_until is not None and self._fast_forward_speed > 0:
            logger.info(
                "Streaming %d points with dynamic pacing (base_speed=%s, fast_forward_speed=%s until %s)",
                len(data_points),
                self.speed,
                self._fast_forward_speed,
                ff_until,
            )
        previous_event_ts: Optional[datetime] = None

        while self.running:
            for point in data_points:
                if not self.running:
                    break

                point_ts = self._coerce_datetime(point.get("timestamp"))
                effective_speed = self._effective_speed_for_timestamp(point_ts)
                if effective_speed > 0:
                    delay_seconds = self._scaled_delay_seconds(
                        previous_event_ts,
                        point_ts,
                        speed_value=effective_speed,
                    )
                    if delay_seconds > 0:
                        await asyncio.sleep(delay_seconds)

                if point_ts is not None:
                    previous_event_ts = point_ts

                await self._store_data_point(point)

            if not self.loop:
                break

    def _load_ticks(self) -> List[MarketTick]:
        if self.data_source == "zerodha":
            return self._load_from_zerodha()
        if self.data_source == "local":
            return self._load_from_local()
        if self.data_source.endswith(".csv"):
            return self._load_from_csv()
        if self.data_source == "synthetic":
            logger.info("Generating synthetic ticks for 'synthetic' data_source")
            start_time = self.rebase_to or datetime.now(IST)
            if self._has_explicit_start_date and self.start_date is not None:
                start_time = self.start_date
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
        base_oi = 1_500_000

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
            minute_oi = int(base_oi + (i * 180) + ((i % 6) - 3) * 120)
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
                        "oi": minute_oi + (tick_idx * 5),
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
                    "oi": minute_oi,
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

    def _load_from_local(self) -> List[MarketTick]:
        """Load one trading day from local archive and prepare options/depth snapshots."""
        replay_day = self._resolve_local_replay_date()
        base_path = Path(os.getenv("LOCAL_HISTORICAL_BASE", r"C:/archive/banknifty_data"))

        fut_path = (
            base_path
            / "banknifty_fut"
            / str(replay_day.year)
            / str(int(replay_day.month))
            / f"banknifty_fut_{replay_day.strftime('%d_%m_%Y')}.csv"
        )
        opt_path = (
            base_path
            / "banknifty_options"
            / str(replay_day.year)
            / str(int(replay_day.month))
            / f"banknifty_options_{replay_day.strftime('%d_%m_%Y')}.csv"
        )

        if not fut_path.exists():
            logger.error(f"Local historical futures file not found: {fut_path}")
            return []

        ticks: List[MarketTick] = []
        fut_close_by_minute: Dict[datetime, float] = {}
        resolved_instrument = str(self.instrument_symbol or "").strip().upper()

        try:
            with open(fut_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row_symbol = str(row.get("symbol") or "").strip().upper()
                    if row_symbol:
                        resolved_instrument = row_symbol
                    ts = self._parse_local_timestamp(row.get("date"), row.get("time"))
                    if ts is None:
                        continue
                    close_val = self._safe_float(row.get("close"))
                    if close_val is None:
                        continue

                    minute = ts.replace(second=0, microsecond=0)
                    fut_close_by_minute[minute] = close_val
                    ticks.append(
                        MarketTick(
                            instrument=resolved_instrument or self.instrument_symbol,
                            timestamp=ts,
                            last_price=close_val,
                            volume=self._safe_int(row.get("volume")),
                            open_interest=self._safe_int(row.get("oi")),
                        )
                    )
        except Exception as exc:
            logger.error(f"Failed loading local futures file {fut_path}: {exc}", exc_info=True)
            return []

        if opt_path.exists():
            self._local_option_snapshots_by_minute = self._build_local_option_snapshots(
                options_file=opt_path,
                fut_close_by_minute=fut_close_by_minute,
                base_instrument=resolved_instrument or self.instrument_symbol,
            )
        else:
            self._local_option_snapshots_by_minute = {}
            logger.warning(f"Local options file not found for {replay_day}: {opt_path}")

        if resolved_instrument:
            self.instrument_symbol = resolved_instrument

        self._local_last_snapshot_minute = None
        self._local_prev_price = None
        self._local_prev_oi = None
        self._local_ema_abs_return = 0.0
        ticks.sort(key=lambda t: t.timestamp)
        logger.info(
            "Loaded local day %s from %s: futures_ticks=%d, option_snapshots=%d",
            replay_day,
            base_path,
            len(ticks),
            len(self._local_option_snapshots_by_minute),
        )
        return ticks

    def _resolve_local_replay_date(self) -> date:
        if isinstance(self.from_date, date):
            return self.from_date
        if self._has_explicit_start_date and isinstance(self.start_date, datetime):
            return self.start_date.date()
        env_from = (os.getenv("HISTORICAL_FROM") or "").strip()
        if env_from:
            try:
                return datetime.strptime(env_from, "%Y-%m-%d").date()
            except Exception:
                pass
        return datetime.now(IST).date()

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            return int(float(value))
        except Exception:
            return None

    @staticmethod
    def _parse_local_timestamp(date_value: Any, time_value: Any) -> Optional[datetime]:
        if date_value is None or time_value is None:
            return None
        raw = f"{str(date_value).strip()} {str(time_value).strip()}"
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=IST)
            except Exception:
                continue
        return None

    def _build_local_option_snapshots(
        self,
        options_file: Path,
        fut_close_by_minute: Dict[datetime, float],
        base_instrument: Optional[str] = None,
    ) -> Dict[datetime, Dict[str, Any]]:
        chain_by_minute: Dict[datetime, Dict[int, Dict[str, Dict[str, Any]]]] = {}
        expiry_by_minute: Dict[datetime, str] = {}
        symbol_re = re.compile(r"^BANKNIFTY(\d{2}[A-Z]{3}\d{2})(\d+)(CE|PE)$")

        with open(options_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol_raw = str(row.get("symbol") or "").strip().upper()
                match = symbol_re.match(symbol_raw)
                if not match:
                    continue
                expiry_code, strike_raw, opt_type = match.groups()
                ts = self._parse_local_timestamp(row.get("date"), row.get("time"))
                if ts is None:
                    continue
                minute = ts.replace(second=0, microsecond=0)
                strike = int(strike_raw)
                close_val = self._safe_float(row.get("close"))
                oi_val = self._safe_int(row.get("oi")) or 0
                vol_val = self._safe_int(row.get("volume")) or 0

                minute_entry = chain_by_minute.setdefault(minute, {})
                strike_entry = minute_entry.setdefault(strike, {})
                strike_entry[opt_type] = {
                    "ltp": close_val,
                    "oi": oi_val,
                    "volume": vol_val,
                }
                expiry_by_minute[minute] = expiry_code

        snapshots_by_minute: Dict[datetime, Dict[str, Any]] = {}
        base_instrument = str(base_instrument or self.instrument_symbol or "BANKNIFTY").upper()
        for minute, strikes_map in chain_by_minute.items():
            strikes: List[Dict[str, Any]] = []
            total_call_oi = 0
            total_put_oi = 0
            for strike in sorted(strikes_map):
                ce = strikes_map[strike].get("CE")
                pe = strikes_map[strike].get("PE")
                ce_oi = int(ce.get("oi", 0)) if ce else 0
                pe_oi = int(pe.get("oi", 0)) if pe else 0
                total_call_oi += ce_oi
                total_put_oi += pe_oi
                strikes.append(
                    {
                        "strike": strike,
                        "ce_ltp": ce.get("ltp") if ce else None,
                        "ce_oi": ce_oi,
                        "ce_volume": int(ce.get("volume", 0)) if ce else 0,
                        "ce_iv": None,
                        "pe_ltp": pe.get("ltp") if pe else None,
                        "pe_oi": pe_oi,
                        "pe_volume": int(pe.get("volume", 0)) if pe else 0,
                        "pe_iv": None,
                    }
                )

            pcr = (float(total_put_oi) / float(total_call_oi)) if total_call_oi > 0 else None
            snapshots_by_minute[minute] = {
                "instrument": base_instrument,
                "expiry": expiry_by_minute.get(minute, ""),
                "strikes": strikes,
                "timestamp": minute.isoformat(),
                "futures_price": fut_close_by_minute.get(minute),
                "pcr": pcr,
                "max_pain": None,
                "source": "local_historical",
                "status": "ok",
                "mode_hint": "historical",
            }

        return snapshots_by_minute

    def _publish_local_side_channels(self, tick: MarketTick, source_event_ts: Optional[datetime] = None) -> None:
        if self.data_source != "local":
            return
        minute = tick.timestamp.replace(second=0, microsecond=0)
        source_minute = (source_event_ts or tick.timestamp).replace(second=0, microsecond=0)
        if self._local_last_snapshot_minute == minute:
            return
        self._local_last_snapshot_minute = minute

        redis_client = self._get_local_redis_client()
        if redis_client is None:
            return
        key_fn = self._resolve_redis_key_fn()

        instrument_upper = str(self.instrument_symbol or tick.instrument or "").upper()
        if not instrument_upper:
            return

        snapshot = self._local_option_snapshots_by_minute.get(source_minute)
        if snapshot:
            try:
                ttl = max(30, int(os.getenv("HISTORICAL_OPTIONS_CHAIN_TTL_SECONDS", "1800")))
                payload = dict(snapshot)
                payload["instrument"] = instrument_upper
                payload["futures_price"] = float(tick.last_price)
                payload["timestamp"] = minute.isoformat()
                payload_json = json.dumps(payload, default=str)
                redis_client.setex(key_fn(f"options:{instrument_upper}:chain"), ttl, payload_json)
                expiry = str(payload.get("expiry") or "").strip()
                if expiry:
                    redis_client.setex(
                        key_fn(f"options:{instrument_upper}:{expiry}:chain"),
                        ttl,
                        payload_json,
                    )
                redis_client.publish(f"market:options:{instrument_upper}", payload_json)
            except Exception as exc:
                logger.debug(f"Failed publishing local options snapshot: {exc}")

        try:
            depth_ttl = max(30, int(os.getenv("DEPTH_TTL_SECONDS", "180")))
            ts_iso = minute.isoformat()
            buy, sell = self._build_local_depth_levels(tick)
            redis_client.setex(key_fn(f"depth:{instrument_upper}:buy"), depth_ttl, json.dumps(buy))
            redis_client.setex(key_fn(f"depth:{instrument_upper}:sell"), depth_ttl, json.dumps(sell))
            redis_client.setex(key_fn(f"depth:{instrument_upper}:timestamp"), depth_ttl, ts_iso)
            redis_client.setex(
                key_fn(f"depth:{instrument_upper}:total_bid_qty"),
                depth_ttl,
                str(sum(int(level["quantity"]) for level in buy)),
            )
            redis_client.setex(
                key_fn(f"depth:{instrument_upper}:total_ask_qty"),
                depth_ttl,
                str(sum(int(level["quantity"]) for level in sell)),
            )
        except Exception as exc:
            logger.debug(f"Failed publishing local depth snapshot: {exc}")

    @staticmethod
    def _clamp(value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))

    def _build_local_depth_levels(self, tick: MarketTick) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Generate replay-consistent synthetic depth from local market dynamics."""
        mid = float(tick.last_price)
        prev_price = self._local_prev_price or mid
        ret = abs(mid - prev_price) / prev_price if prev_price > 0 else 0.0
        self._local_ema_abs_return = (0.2 * ret) + (0.8 * self._local_ema_abs_return)

        base_bps = float(os.getenv("LOCAL_DEPTH_BASE_BPS", "2.0")) / 10000.0
        spread_multiplier = 1.0 + (10.0 * self._local_ema_abs_return)
        spread = max(0.5, round(mid * base_bps * spread_multiplier, 2))

        volume = int(tick.volume or 0)
        volume_norm = self._clamp(volume / 25000.0, 0.25, 5.0)
        qty_seed = max(40, int(180 * volume_norm))

        trend_sign = 1 if mid > prev_price else (-1 if mid < prev_price else 0)
        oi_now = int(tick.open_interest or 0)
        oi_prev = self._local_prev_oi if self._local_prev_oi is not None else oi_now
        oi_sign = 1 if oi_now > oi_prev else (-1 if oi_now < oi_prev else 0)

        bid_bias = self._clamp(1.0 + 0.22 * trend_sign + 0.15 * oi_sign, 0.6, 1.4)
        ask_bias = self._clamp(1.0 - 0.22 * trend_sign - 0.15 * oi_sign, 0.6, 1.4)

        buy: List[Dict[str, Any]] = []
        sell: List[Dict[str, Any]] = []
        for lvl in range(1, 6):
            distance = spread * (1.0 + 0.35 * (lvl - 1))
            level_shape = (6 - lvl) / 5.0  # front of book carries more quantity
            bid_qty = max(10, int(qty_seed * level_shape * bid_bias))
            ask_qty = max(10, int(qty_seed * level_shape * ask_bias))

            buy.append(
                {
                    "price": round(mid - distance, 2),
                    "quantity": bid_qty,
                    "orders": max(1, int(bid_qty / 75)),
                }
            )
            sell.append(
                {
                    "price": round(mid + distance, 2),
                    "quantity": ask_qty,
                    "orders": max(1, int(ask_qty / 75)),
                }
            )

        self._local_prev_price = mid
        self._local_prev_oi = oi_now
        return buy, sell

    def _get_local_redis_client(self):
        if self._local_redis_client is not None:
            return self._local_redis_client
        try:
            import redis

            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", "6379"))
            self._local_redis_client = redis.Redis(host=host, port=port, db=0, decode_responses=True)
            return self._local_redis_client
        except Exception:
            return None

    @staticmethod
    def _resolve_redis_key_fn() -> Callable[[str], str]:
        try:
            from redis_key_manager import get_redis_key
            return get_redis_key
        except Exception:
            return lambda key: key

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

        except TokenException as e:
            # Hard-fail auth errors so runtime can stop immediately with a precise message.
            raise RuntimeError(
                "Zerodha authentication failed during historical fetch "
                "(Incorrect api_key/access_token). Re-run kite login and retry."
            ) from e
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
                instruments = self._kite_instruments_with_retry("NFO")
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
            instruments = self._kite_instruments_with_retry("NSE")
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
            instruments = self._kite_instruments_with_retry("NFO")
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

    def _kite_instruments_with_retry(self, exchange: str, attempts: int = 3, base_delay_sec: float = 1.5) -> List[Dict[str, Any]]:
        """Fetch Kite instruments list with bounded retry for transient TLS/network errors."""
        if not self.kite:
            return []
        ttl_seconds = int(os.getenv("KITE_INSTRUMENTS_CACHE_TTL_SECONDS", "86400"))
        cache_path = self._kite_instruments_cache_path(exchange)

        # Fast path: use fresh local cache to avoid repeated upstream calls.
        cached_rows = self._load_kite_instruments_cache(cache_path, ttl_seconds=ttl_seconds)
        if cached_rows:
            logger.info(
                "Using cached Kite instruments for %s (%s rows, ttl=%ss)",
                exchange,
                len(cached_rows),
                ttl_seconds,
            )
            return cached_rows

        last_error: Optional[Exception] = None
        for attempt in range(1, max(1, attempts) + 1):
            try:
                rows = self.kite.instruments(exchange)
                if isinstance(rows, list):
                    self._save_kite_instruments_cache(cache_path, rows)
                    return rows
                return []
            except Exception as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                delay = base_delay_sec * attempt
                logger.warning(
                    "Kite instruments(%s) failed (attempt %s/%s): %s; retrying in %.1fs",
                    exchange,
                    attempt,
                    attempts,
                    exc,
                    delay,
                )
                time.sleep(delay)
        # Final fallback: stale cache is better than no replay at all.
        stale_rows = self._load_kite_instruments_cache(cache_path, ttl_seconds=0)
        if stale_rows:
            logger.warning(
                "Using stale cached Kite instruments for %s after upstream failures (%s rows): %s",
                exchange,
                len(stale_rows),
                last_error,
            )
            return stale_rows
        logger.error("Kite instruments(%s) failed after %s attempts: %s", exchange, attempts, last_error)
        return []

    def _kite_instruments_cache_path(self, exchange: str) -> Path:
        cache_dir = Path(os.getenv("KITE_INSTRUMENTS_CACHE_DIR", ".run")).resolve()
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        safe_exchange = str(exchange or "unknown").strip().upper()
        return cache_dir / f"kite_instruments_{safe_exchange}.json"

    def _load_kite_instruments_cache(self, cache_path: Path, ttl_seconds: int) -> List[Dict[str, Any]]:
        try:
            if not cache_path.exists():
                return []
            if ttl_seconds > 0:
                age = time.time() - cache_path.stat().st_mtime
                if age > ttl_seconds:
                    return []
            with cache_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            rows = payload.get("rows") if isinstance(payload, dict) else None
            return rows if isinstance(rows, list) else []
        except Exception:
            return []

    def _save_kite_instruments_cache(self, cache_path: Path, rows: List[Dict[str, Any]]) -> None:
        try:
            payload = {
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "count": len(rows or []),
                "rows": rows or [],
            }
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception as e:
            logger.debug("Failed to save instruments cache at %s: %s", cache_path, e)

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
            latest_oi = next((t.open_interest for t in reversed(group_ticks) if t.open_interest is not None), None)
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
                    open_interest=latest_oi,
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

            timestamp = self._map_publish_timestamp(timestamp)

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
                    if isinstance(tick_ts, datetime):
                        tick_ts = self._map_publish_timestamp(tick_ts)
                    else:
                        tick_ts = timestamp
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
        oi = 1_500_000

        import random

        for _ in range(duration_minutes):
            for tick_idx in range(4):
                tick_time = current_time + timedelta(seconds=tick_idx * 15)
                price_change = random.uniform(-10, 10)
                price = max(1000, price + price_change)
                oi = max(1000, oi + random.randint(-300, 300))

                ticks.append(
                    MarketTick(
                        instrument=instrument,
                        timestamp=tick_time,
                        last_price=round(price, 2),
                        volume=random.randint(1000, 10000),
                        open_interest=int(oi),
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
