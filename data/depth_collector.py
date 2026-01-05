"""Collect market depth and order flow via Zerodha quote() and cache to Redis.

Designed to complement LTPDataCollector (which uses ltp()) by persisting depth,
best bid/ask, and total quantities for order-flow analytics and dashboards.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from kiteconnect import KiteConnect

from data.market_memory import MarketMemory
from config.settings import settings

logger = logging.getLogger(__name__)


class DepthCollector:
    def __init__(self, kite: KiteConnect, market_memory: MarketMemory):
        self.kite = kite
        self.market_memory = market_memory
        self.running = False

    def _instrument_key(self) -> str:
        sym = (settings.instrument_symbol or "NIFTY BANK").upper().replace(" ", "")
        if "BANKNIFTY" in sym or "NIFTYBANK" in sym:
            return "BANKNIFTY"
        return "NIFTY"

    def _resolve_token(self) -> Optional[int]:
        key = self._instrument_key()
        # Prefer NSE index exact match
        try:
            for inst in self.kite.instruments("NSE"):
                ts = (inst.get("tradingsymbol") or "").upper()
                if ts == ("NIFTY BANK" if key == "BANKNIFTY" else "NIFTY 50"):
                    return inst.get("instrument_token")
        except Exception:
            pass
        # Fallback to NFO futures nearest non-expired
        try:
            today = datetime.now().date()
            futs: List[Dict[str, Any]] = []
            for inst in self.kite.instruments("NFO"):
                if inst.get("segment") != "NFO-FUT" or inst.get("instrument_type") != "FUT":
                    continue
                ts = (inst.get("tradingsymbol") or "").upper()
                if key not in ts:
                    continue
                expiry = inst.get("expiry")
                if not expiry or expiry < today:
                    continue
                futs.append(inst)
            if futs:
                futs.sort(key=lambda x: x.get("expiry"))
                return futs[0].get("instrument_token")
        except Exception:
            pass
        return None

    def _fetch_quote(self, token: int) -> Optional[Dict[str, Any]]:
        try:
            q = self.kite.quote([token])
            return q.get(str(token)) or q.get(token) or None
        except Exception as e:
            logger.warning(f"quote() failed: {e}")
            return None

    def collect(self, interval_seconds: int = 5):
        self.running = True
        token = self._resolve_token()
        if not token:
            logger.error("DepthCollector: could not resolve instrument token")
            return
        logger.info(f"DepthCollector started for token={token}")

        while self.running:
            try:
                data = self._fetch_quote(token)
                if data:
                    tick = {
                        "instrument_token": token,
                        "last_price": data.get("last_price"),
                        "timestamp": datetime.now().isoformat(),
                    }
                    depth = data.get("depth") or {}
                    if isinstance(depth, dict):
                        buy_levels = depth.get("buy") or []
                        sell_levels = depth.get("sell") or []
                        tick["depth"] = {
                            "buy": buy_levels[:5],
                            "sell": sell_levels[:5],
                        }
                        # include top-of-book metrics if present
                        if buy_levels:
                            tick["best_bid"] = buy_levels[0].get("price")
                        if sell_levels:
                            tick["best_ask"] = sell_levels[0].get("price")
                        tick["total_bid_quantity"] = sum(lvl.get("quantity", 0) for lvl in buy_levels[:5])
                        tick["total_ask_quantity"] = sum(lvl.get("quantity", 0) for lvl in sell_levels[:5])
                    # store
                    self.market_memory.store_tick(self._instrument_key(), tick)
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                logger.info("DepthCollector stopping...")
                break
            except Exception as e:
                logger.error(f"DepthCollector error: {e}")
                time.sleep(interval_seconds)
        logger.info("DepthCollector stopped")
