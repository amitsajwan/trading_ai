#!/usr/bin/env python3
"""OHLC Aggregator Service - Consumes enhanced ticks and generates OHLC candles.

This service:
1. Subscribes to enhanced_ticks Redis channel
2. Aggregates ticks into 1-minute OHLC bars
3. Stores bars in Redis for API consumption

Compatible with mock, live, and historical data sources.
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

import redis

# Add parent directory to path for redis_key_manager
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redis_key_manager import get_redis_key, get_execution_mode

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))

@dataclass
class OHLCBar:
    """OHLC bar data."""
    instrument: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    start_at: datetime

class OHLCAggregator:
    """Aggregates ticks into OHLC candles."""
    
    def __init__(self):
        self.instrument = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY26FEBFUT")
        self.execution_mode = get_execution_mode()
        
        # Redis setup
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6380"))
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        self.pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
        
        # Current candle state
        self.current_candle: Dict[str, Any] = {}
        self.candle_start_time: Optional[datetime] = None
        
        print(f"OHLC Aggregator initialized for {self.instrument}")
        print(f"Execution mode: {self.execution_mode.upper()}")
        print(f"Subscribing to: {get_redis_key(f'enhanced_ticks:{self.instrument}')}")
    
    def _get_candle_start_time(self, tick_time: datetime) -> datetime:
        """Get the start time of the 1-minute candle for a given tick time."""
        # Round down to the nearest minute
        return tick_time.replace(second=0, microsecond=0)
    
    def _init_candle(self, tick_data: Dict[str, Any], candle_time: datetime):
        """Initialize a new candle."""
        price = tick_data["last_price"]
        self.current_candle = {
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": tick_data.get("volume", 0),
            "start_time": candle_time
        }
        self.candle_start_time = candle_time
        print(f"[OHLC] New candle started at {candle_time.strftime('%H:%M:%S')} - Open: Rs {price:.2f}")
    
    def _update_candle(self, tick_data: Dict[str, Any]):
        """Update current candle with new tick."""
        price = tick_data["last_price"]
        volume = tick_data.get("volume", 0)
        
        self.current_candle["high"] = max(self.current_candle["high"], price)
        self.current_candle["low"] = min(self.current_candle["low"], price)
        self.current_candle["close"] = price
        self.current_candle["volume"] = volume  # Use latest volume
    
    def _close_candle(self):
        """Close current candle and store it."""
        if not self.current_candle or not self.candle_start_time:
            return
        
        # Create OHLC bar dict
        bar_data = {
            "instrument": self.instrument,
            "timeframe": "1min",
            "open": self.current_candle["open"],
            "high": self.current_candle["high"],
            "low": self.current_candle["low"],
            "close": self.current_candle["close"],
            "volume": self.current_candle["volume"],
            "start_at": self.candle_start_time.isoformat(),
            "timestamp": self.candle_start_time.isoformat()
        }
        
        # Store in Redis sorted set (same format as market_data.api)
        key = get_redis_key(f"ohlc_sorted:{self.instrument}:1min")
        score = self.candle_start_time.timestamp()
        self.redis_client.zadd(key, {json.dumps(bar_data): score})
        
        # Keep only last 1000 bars
        self.redis_client.zremrangebyrank(key, 0, -1001)
        
        # Publish to multi-timeframe aggregator
        publish_channel = get_redis_key(f"1min_candle:{self.instrument}")
        self.redis_client.publish(publish_channel, json.dumps(bar_data))
        
        print(f"[OHLC] Candle closed: {self.candle_start_time.strftime('%H:%M')} | "
              f"O:{bar_data['open']:.2f} H:{bar_data['high']:.2f} L:{bar_data['low']:.2f} C:{bar_data['close']:.2f} V:{bar_data['volume']}")
        
        # Reset for next candle
        self.current_candle = {}
        self.candle_start_time = None
    
    def process_tick(self, tick_data: Dict[str, Any]):
        """Process an enhanced tick and update OHLC."""
        try:
            # Parse timestamp
            timestamp_str = tick_data.get("timestamp", datetime.now(IST).isoformat())
            tick_time = datetime.fromisoformat(timestamp_str)
            if tick_time.tzinfo is None:
                tick_time = tick_time.replace(tzinfo=IST)
            
            # Get candle start time for this tick
            candle_time = self._get_candle_start_time(tick_time)
            
            # Check if we need to close current candle and start new one
            if self.candle_start_time is None:
                # First tick - initialize candle
                self._init_candle(tick_data, candle_time)
            elif candle_time > self.candle_start_time:
                # New minute - close old candle and start new one
                self._close_candle()
                self._init_candle(tick_data, candle_time)
            else:
                # Same minute - update current candle
                self._update_candle(tick_data)
        
        except Exception as e:
            print(f"[ERROR] Failed to process tick: {e}")
            import traceback
            traceback.print_exc()
    
    def run(self):
        """Run the OHLC aggregator service."""
        print("Starting OHLC Aggregator Service...")
        
        # Subscribe to enhanced ticks (prefixed + legacy)
        channel = get_redis_key(f"enhanced_ticks:{self.instrument}")
        legacy_channel = f"enhanced_ticks:{self.instrument}"
        channels = [channel]
        if legacy_channel not in channels:
            channels.append(legacy_channel)
        self.pubsub.subscribe(*channels)
        
        try:
            print(f"Listening for enhanced ticks on {', '.join(channels)}...")
            for message in self.pubsub.listen():
                if message['type'] == 'message':
                    tick_data = json.loads(message['data'])
                    self.process_tick(tick_data)
        
        except KeyboardInterrupt:
            print("\nStopping OHLC Aggregator Service...")
            # Close any open candle
            if self.current_candle:
                self._close_candle()
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.pubsub.close()

if __name__ == "__main__":
    aggregator = OHLCAggregator()
    aggregator.run()
