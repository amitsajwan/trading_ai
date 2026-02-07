#!/usr/bin/env python3
"""
Multi-Timeframe OHLC Aggregator Service

Aggregates 1-minute OHLC candles into multiple timeframes:
- 5-minute
- 15-minute  
- 1-hour
- 4-hour
- Daily

Stores all timeframes in Redis for API consumption.
"""

import redis
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from threading import Thread
import time

# Add parent directory to path for redis_key_manager
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redis_key_manager import get_redis_key, get_redis_pattern, get_execution_mode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6380"))
REDIS_DB = 0

# Timeframes in minutes
TIMEFRAMES = {
    '5min': 5,
    '15min': 15,
    '1h': 60,
    '4h': 240,
    '1d': 1440
}

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))


class MultiTimeframeAggregator:
    def __init__(self):
        self.execution_mode = get_execution_mode()
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )
        self.candles = defaultdict(lambda: defaultdict(dict))
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized in {self.execution_mode.upper()} mode")
        
    def get_candle_start_time(self, timestamp, timeframe_minutes):
        """Round timestamp to the start of the candle period."""
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        
        minutes_since_midnight = dt.hour * 60 + dt.minute
        candle_start_minute = (minutes_since_midnight // timeframe_minutes) * timeframe_minutes
        
        candle_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        candle_start += timedelta(minutes=candle_start_minute)
        
        return candle_start.isoformat()
    
    def process_1min_candle(self, instrument, candle_data):
        """Process a 1-minute candle and aggregate into larger timeframes."""
        try:
            start_at = candle_data.get('start_at')
            
            for timeframe_name, timeframe_minutes in TIMEFRAMES.items():
                candle_start = self.get_candle_start_time(start_at, timeframe_minutes)
                
                # Initialize candle if not exists
                if candle_start not in self.candles[instrument][timeframe_name]:
                    self.candles[instrument][timeframe_name][candle_start] = {
                        'open': candle_data['open'],
                        'high': candle_data['high'],
                        'low': candle_data['low'],
                        'close': candle_data['close'],
                        'volume': candle_data['volume'],
                        'start_at': candle_start,
                        'instrument': instrument,
                        'timeframe': timeframe_name
                    }
                else:
                    # Update existing candle
                    candle = self.candles[instrument][timeframe_name][candle_start]
                    candle['high'] = max(candle['high'], candle_data['high'])
                    candle['low'] = min(candle['low'], candle_data['low'])
                    candle['close'] = candle_data['close']
                    candle['volume'] += candle_data['volume']  # SUM volumes from all 1min bars
                
                # Store in Redis
                self._store_candle(instrument, timeframe_name, candle_start)
                
        except Exception as e:
            self.logger.error(f"Error processing candle: {e}")
    
    def _store_candle(self, instrument, timeframe, candle_start):
        """Store candle in Redis sorted set."""
        try:
            candle = self.candles[instrument][timeframe][candle_start]
            redis_key = get_redis_key(f"ohlc_sorted:{instrument}:{timeframe}")
            
            # Convert timestamp to Unix timestamp for sorting
            dt = datetime.fromisoformat(candle_start)
            timestamp = int(dt.timestamp())
            
            # Store as JSON in sorted set
            self.redis_client.zadd(
                redis_key,
                {json.dumps(candle): timestamp}
            )
            
            # Keep only last 1000 candles
            self.redis_client.zremrangebyrank(redis_key, 0, -1001)
            
        except Exception as e:
            self.logger.error(f"Error storing candle: {e}")
    
    def subscribe_to_1min_candles(self):
        """Subscribe to 1-minute OHLC candles and aggregate."""
        try:
            pubsub = self.redis_client.pubsub()
            channel_pattern = get_redis_pattern('1min_candle:*')
            pubsub.psubscribe(channel_pattern)
            
            self.logger.info(f"Listening for 1-minute candles on {channel_pattern}...")
            
            for message in pubsub.listen():
                if message['type'] == 'pmessage':
                    try:
                        data = json.loads(message['data'])
                        instrument = data.get('instrument')
                        
                        self.process_1min_candle(instrument, data)
                        
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        self.logger.error(f"Error processing message: {e}")
                        
        except Exception as e:
            self.logger.error(f"Subscription error: {e}")


def main():
    """Main entry point."""
    aggregator = MultiTimeframeAggregator()
    
    logger.info("=" * 60)
    logger.info("Multi-Timeframe OHLC Aggregator Service")
    logger.info("=" * 60)
    logger.info(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    logger.info(f"Timeframes: {', '.join(TIMEFRAMES.keys())}")
    logger.info("=" * 60)
    
    # Start subscription
    aggregator.subscribe_to_1min_candles()


if __name__ == "__main__":
    main()
