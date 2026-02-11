"""Historical Kite WebSocket adapter.

Implements a KiteTicker-compatible interface (on_ticks/on_connect/subscribe/connect/close)
while replaying historical-like ticks. This preserves the same upstream contract as
real and mock websocket sources.
"""

from __future__ import annotations

import csv
import logging
import random
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HistoricalKiteTicker:
    """KiteTicker-compatible historical replay ticker."""

    MODE_LTP = "ltp"
    MODE_QUOTE = "quote"
    MODE_FULL = "full"

    def __init__(
        self,
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
        data_source: str = "synthetic",
        tick_interval: float = 0.25,
        start_time: Optional[datetime] = None,
    ):
        self.api_key = api_key
        self.access_token = access_token
        self.data_source = data_source
        self.tick_interval = tick_interval
        self.start_time = start_time or datetime.now(timezone.utc)

        self.on_ticks: Optional[Callable] = None
        self.on_connect: Optional[Callable] = None
        self.on_close: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        self.connected = False
        self.running = False
        self.mode = self.MODE_FULL
        self._thread: Optional[threading.Thread] = None

        self.subscribed_instruments: List[int] = []
        self._timeline: Dict[int, List[Dict[str, Any]]] = {}
        self._cursor: Dict[int, int] = {}

    def subscribe(self, instrument_tokens: List[int]) -> None:
        for token in instrument_tokens:
            if token not in self.subscribed_instruments:
                self.subscribed_instruments.append(token)
                self._timeline[token] = self._load_timeline(token)
                self._cursor[token] = 0

    def unsubscribe(self, instrument_tokens: List[int]) -> None:
        for token in instrument_tokens:
            if token in self.subscribed_instruments:
                self.subscribed_instruments.remove(token)
                self._timeline.pop(token, None)
                self._cursor.pop(token, None)

    def set_mode(self, mode: str, instrument_tokens: List[int]) -> None:
        self.mode = mode

    def connect(self, threaded: bool = False, disable_ssl_verification: bool = False) -> None:
        if self.running:
            return

        self.running = True
        self.connected = True

        if self.on_connect:
            try:
                self.on_connect(self, {"status": "Connected to HistoricalKiteTicker"})
            except Exception as exc:
                logger.error("historical on_connect callback failed: %s", exc)

        if threaded:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        else:
            self._run()

    def close(self, code: int = 1000, reason: str = "closed") -> None:
        self.running = False
        self.connected = False
        if self.on_close:
            try:
                self.on_close(self, code, reason)
            except Exception:
                pass

    def _run(self) -> None:
        while self.running:
            if not self.subscribed_instruments:
                time.sleep(0.1)
                continue

            out: List[Dict[str, Any]] = []
            for token in list(self.subscribed_instruments):
                timeline = self._timeline.get(token) or []
                if not timeline:
                    continue
                idx = self._cursor.get(token, 0)
                tick = timeline[idx]
                out.append(tick)
                self._cursor[token] = (idx + 1) % len(timeline)

            if out and self.on_ticks:
                try:
                    self.on_ticks(self, out)
                except Exception as exc:
                    if self.on_error:
                        self.on_error(self, 500, str(exc))

            time.sleep(self.tick_interval)

    def _load_timeline(self, token: int) -> List[Dict[str, Any]]:
        if self.data_source != "synthetic":
            csv_path = Path(self.data_source)
            if csv_path.exists() and csv_path.suffix.lower() == ".csv":
                rows = self._load_csv_rows(csv_path, token)
                if rows:
                    return rows
                logger.warning("No valid rows found in %s, falling back to synthetic", csv_path)

        return self._generate_synthetic_rows(token)

    def _load_csv_rows(self, csv_path: Path, token: int) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        with csv_path.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    ts = row.get("timestamp") or row.get("time")
                    ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else datetime.now(timezone.utc)
                    price = float(row.get("last_price") or row.get("close") or row.get("price"))
                    volume = int(float(row.get("volume") or 0))
                except Exception:
                    continue

                rows.append(
                    {
                        "instrument_token": token,
                        "last_price": price,
                        "volume": volume,
                        "last_traded_quantity": 1,
                        "average_traded_price": price,
                        "volume_traded": volume,
                        "total_buy_quantity": max(1, volume // 2),
                        "total_sell_quantity": max(1, volume // 2),
                        "ohlc": {
                            "open": price,
                            "high": price,
                            "low": price,
                            "close": price,
                        },
                        "timestamp": ts_dt,
                    }
                )

        return rows

    def _generate_synthetic_rows(self, token: int) -> List[Dict[str, Any]]:
        random.seed(token)
        base_price = 45000.0 + (token % 10000)
        now = self.start_time
        cumulative_volume = 0
        rows: List[Dict[str, Any]] = []

        for i in range(1200):
            drift = random.uniform(-0.25, 0.25)
            last_price = max(1.0, base_price + drift)
            tick_volume = random.randint(10, 800)
            cumulative_volume += tick_volume
            ts = now + timedelta(seconds=i)

            rows.append(
                {
                    "instrument_token": token,
                    "last_price": round(last_price, 2),
                    "volume": cumulative_volume,
                    "last_traded_quantity": random.randint(1, 25),
                    "average_traded_price": round((base_price + last_price) / 2, 2),
                    "volume_traded": cumulative_volume,
                    "total_buy_quantity": random.randint(30000, 60000),
                    "total_sell_quantity": random.randint(30000, 60000),
                    "ohlc": {
                        "open": round(base_price, 2),
                        "high": round(max(base_price, last_price + random.uniform(0, 5)), 2),
                        "low": round(min(base_price, last_price - random.uniform(0, 5)), 2),
                        "close": round(last_price, 2),
                    },
                    "timestamp": ts,
                }
            )
            base_price = last_price

        random.seed()
        return rows


def create_historical_ticker(
    api_key: Optional[str] = None,
    access_token: Optional[str] = None,
    data_source: str = "synthetic",
    tick_interval: float = 0.25,
) -> HistoricalKiteTicker:
    return HistoricalKiteTicker(
        api_key=api_key,
        access_token=access_token,
        data_source=data_source,
        tick_interval=tick_interval,
    )
