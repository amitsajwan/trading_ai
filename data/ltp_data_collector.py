"""Collect live market data using LTP API (works with free Kite Connect plan)."""

import logging
import json
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from kiteconnect import KiteConnect
from data.market_memory import MarketMemory
from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


class LTPDataCollector:
    """Collect live market data using LTP API calls."""
    
    def __init__(self, kite: KiteConnect, market_memory: MarketMemory):
        """Initialize LTP data collector."""
        self.kite = kite
        self.market_memory = market_memory
        self.running = False
        
        # MongoDB connection
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.ohlc_collection = get_collection(self.db, "ohlc_history")
        
        # Current candles being built
        self.current_candles = {
            "1min": {},
            "5min": {},
            "15min": {},
            "hourly": {}
        }
        
        # Price tracking for OHLC
        self.price_history = []
        # Track cumulative volume for delta computation
        self._last_cum_volume: Optional[float] = None
    
    def _instrument_key(self) -> str:
        sym = (settings.instrument_symbol or "NIFTY BANK").upper().replace(" ", "")
        if "BANKNIFTY" in sym or "NIFTYBANK" in sym:
            return "BANKNIFTY"
        return "NIFTY"

    def get_instrument_token(self) -> Optional[int]:
        """Resolve instrument token for index (prefer NSE index, fallback NFO-FUT)."""
        try:
            key = self._instrument_key()
            # Prefer NSE index exact match
            nse = self.kite.instruments("NSE")
            wanted = "NIFTY BANK" if key == "BANKNIFTY" else "NIFTY 50"
            for inst in nse:
                if (inst.get("tradingsymbol") or "").upper() == wanted:
                    return inst.get("instrument_token")
            # Fallback to NFO futures nearest expiry
            nfo = self.kite.instruments("NFO")
            today = datetime.now().date()
            futs = []
            for inst in nfo:
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
            return None
        except Exception as e:
            logger.error(f"Error getting instrument token: {e}")
            return None
    
    def get_ltp(self, instrument_token: int) -> Optional[float]:
        """Get Last Traded Price using LTP API."""
        try:
            ltp_data = self.kite.ltp([instrument_token])
            if instrument_token in ltp_data:
                return ltp_data[instrument_token].get("last_price")
            return None
        except Exception as e:
            logger.error(f"Error fetching LTP: {e}")
            return None
    
    def update_ohlc_from_price(self, price: float, timestamp: datetime, volume_delta: float = 0.0):
        """Update OHLC candles from current price."""
        def get_candle_key(dt: datetime, minutes: int) -> str:
            rounded_minute = (dt.minute // minutes) * minutes
            rounded = dt.replace(minute=rounded_minute, second=0, microsecond=0)
            return rounded.isoformat()
        
        # Update 1-minute candles
        key_1min = get_candle_key(timestamp, 1)
        if key_1min not in self.current_candles["1min"]:
            # Finalize previous candle if exists
            if self.current_candles["1min"]:
                prev_key = max(self.current_candles["1min"].keys())
                self._finalize_candle("1min", self.current_candles["1min"].pop(prev_key))
            
            # Start new candle
            self.current_candles["1min"][key_1min] = {
                "timestamp": key_1min,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": float(volume_delta) if volume_delta else 0,
                "timeframe": "1min"
            }
        else:
            candle = self.current_candles["1min"][key_1min]
            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price
            if volume_delta:
                candle["volume"] = float(candle.get("volume", 0)) + float(volume_delta)
        
        # Similar for other timeframes
        for minutes, timeframe in [(5, "5min"), (15, "15min")]:
            key = get_candle_key(timestamp, minutes)
            if key not in self.current_candles[timeframe]:
                if self.current_candles[timeframe]:
                    prev_key = max(self.current_candles[timeframe].keys())
                    self._finalize_candle(timeframe, self.current_candles[timeframe].pop(prev_key))
                
                self.current_candles[timeframe][key] = {
                    "timestamp": key,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": float(volume_delta) if volume_delta else 0,
                    "timeframe": timeframe
                }
            else:
                candle = self.current_candles[timeframe][key]
                candle["high"] = max(candle["high"], price)
                candle["low"] = min(candle["low"], price)
                candle["close"] = price
                if volume_delta:
                    candle["volume"] = float(candle.get("volume", 0)) + float(volume_delta)
        
        # Hourly
        key_hourly = timestamp.replace(minute=0, second=0, microsecond=0).isoformat()
        if key_hourly not in self.current_candles["hourly"]:
            if self.current_candles["hourly"]:
                prev_key = max(self.current_candles["hourly"].keys())
                self._finalize_candle("hourly", self.current_candles["hourly"].pop(prev_key))
            
            self.current_candles["hourly"][key_hourly] = {
                "timestamp": key_hourly,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": float(volume_delta) if volume_delta else 0,
                "timeframe": "hourly"
            }
        else:
            candle = self.current_candles["hourly"][key_hourly]
            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price
            if volume_delta:
                candle["volume"] = float(candle.get("volume", 0)) + float(volume_delta)
    
    def _finalize_candle(self, timeframe: str, candle: Dict[str, Any]):
        """Finalize and store a completed candle."""
        # Store in Redis
        self.market_memory.store_ohlc(self._instrument_key(), timeframe, candle)
        
        # Store in MongoDB
        try:
            candle_to_store = dict(candle)
            try:
                candle_to_store["instrument"] = settings.instrument_symbol
            except Exception:
                pass
            self.ohlc_collection.insert_one(candle_to_store)
        except Exception as e:
            logger.error(f"Error storing candle in MongoDB: {e}")
    
    def collect_continuously(self, instrument_token: int, interval_seconds: int = 5):
        """Continuously collect LTP data."""
        self.running = True
        logger.info(f"Starting continuous LTP collection (every {interval_seconds} seconds)...")
        
        last_price = None
        price_count = 0
        
        while self.running:
            try:
                # Get current price
                price = self.get_ltp(instrument_token)
                
                if price:
                    timestamp = datetime.now()
                    # Compute volume delta from Redis (cumulative volume via depth collector)
                    volume_delta = 0.0
                    try:
                        if getattr(self.market_memory, "_redis_available", False):
                            key = self._instrument_key()
                            vol_str = self.market_memory.redis_client.get(f"volume:{key}:latest")
                            if vol_str is not None:
                                curr_vol = float(vol_str)
                                if self._last_cum_volume is None:
                                    # initialize baseline for the session
                                    self._last_cum_volume = curr_vol
                                    volume_delta = 0.0
                                else:
                                    # handle daily reset
                                    if curr_vol >= self._last_cum_volume:
                                        volume_delta = max(0.0, curr_vol - self._last_cum_volume)
                                    else:
                                        # reset detected
                                        volume_delta = 0.0
                                    self._last_cum_volume = curr_vol
                    except Exception as e:
                        logger.debug(f"volume delta calc failed: {e}")
                    
                    # Store tick
                    tick_data = {
                        "instrument_token": instrument_token,
                        "last_price": price,
                        "timestamp": timestamp.isoformat()
                    }
                    self.market_memory.store_tick(self._instrument_key(), tick_data)
                    
                    # Update OHLC
                    self.update_ohlc_from_price(price, timestamp, volume_delta=volume_delta)
                    
                    price_count += 1
                    if price != last_price:
                        logger.debug(f"Price update: {price} (count: {price_count})")
                        last_price = price
                
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Stopping data collection...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in data collection: {e}")
                time.sleep(interval_seconds)
        
        logger.info("Data collection stopped")


def main():
    """Main entry point for LTP data collector."""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Load credentials (try both files)
        cred_path = Path("credentials.json")
        if not cred_path.exists():
            cred_path = Path("kite_credentials.json")
        if not cred_path.exists():
            raise FileNotFoundError("credentials.json not found. Run auto_login.py first.")
        
        with open(cred_path) as f:
            creds = json.load(f)
        
        # Handle different credential file formats
        api_key = creds.get("api_key") or creds.get("apiKey")
        access_token = creds.get("access_token") or creds.get("accessToken")
        
        if not api_key or not access_token:
            raise ValueError("Missing api_key or access_token in credentials file")
        
        # Initialize Kite Connect
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        logger.info("✅ Kite Connect initialized")
        
        # Initialize market memory
        market_memory = MarketMemory()
        logger.info("✅ Market memory initialized")
        
        # Initialize collector
        collector = LTPDataCollector(kite, market_memory)
        
        # Get instrument token
        instrument_token = collector.get_instrument_token()
        if not instrument_token:
            logger.error("Could not find Bank Nifty instrument token")
            return
        
        logger.info(f"✅ Found instrument token: {instrument_token}")
        logger.info("Starting continuous data collection...")
        logger.info("Press Ctrl+C to stop")
        
        # Start collection (every 5 seconds)
        collector.collect_continuously(instrument_token, interval_seconds=5)
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

