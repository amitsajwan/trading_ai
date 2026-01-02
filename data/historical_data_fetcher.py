"""Fetch historical OHLC data using Zerodha Kite REST API."""

import logging
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kiteconnect import KiteConnect
from data.market_memory import MarketMemory
from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings

logger = logging.getLogger(__name__)


class HistoricalDataFetcher:
    """Fetch historical OHLC data using Zerodha Kite REST API."""
    
    def __init__(self, kite: KiteConnect, market_memory: MarketMemory):
        """Initialize historical data fetcher."""
        self.kite = kite
        self.market_memory = market_memory
        
        # MongoDB connection
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.ohlc_collection = get_collection(self.db, "ohlc_history")
    
    def get_instrument_token(self) -> Optional[int]:
        """Get Bank Nifty instrument token."""
        try:
            instruments = self.kite.instruments("NSE")
            for inst in instruments:
                if inst["tradingsymbol"] == "NIFTY BANK":
                    return inst["instrument_token"]
            return None
        except Exception as e:
            logger.error(f"Error getting instrument token: {e}")
            return None
    
    def fetch_historical_data(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str = "5minute"
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical OHLC data from Zerodha Kite API.
        
        interval options: "minute", "3minute", "5minute", "15minute", "30minute", "60minute", "day"
        """
        try:
            # Convert to date format
            from_date_str = from_date.strftime("%Y-%m-%d")
            to_date_str = to_date.strftime("%Y-%m-%d")
            
            logger.info(f"Fetching historical data from {from_date_str} to {to_date_str}, interval: {interval}")
            
            # Fetch historical data
            historical_data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval,
                continuous=False,
                oi=False
            )
            
            if not historical_data:
                logger.warning("No historical data returned")
                return []
            
            # Convert to our format
            candles = []
            for candle in historical_data:
                formatted_candle = {
                    "instrument_token": instrument_token,
                    "timestamp": candle["date"].isoformat() if hasattr(candle["date"], "isoformat") else str(candle["date"]),
                    "open": float(candle["open"]),
                    "high": float(candle["high"]),
                    "low": float(candle["low"]),
                    "close": float(candle["close"]),
                    "volume": int(candle["volume"]),
                    "timeframe": interval
                }
                candles.append(formatted_candle)
            
            logger.info(f"Fetched {len(candles)} candles")
            return candles
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return []
    
    def store_candles(self, candles: List[Dict[str, Any]], timeframe: str):
        """Store candles in Redis and MongoDB."""
        stored_count = 0
        # Get instrument key from settings
        instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
        for candle in candles:
            try:
                # Store in Redis
                self.market_memory.store_ohlc(instrument_key, timeframe, candle)
                
                # Store in MongoDB
                self.ohlc_collection.insert_one(candle)
                stored_count += 1
            except Exception as e:
                logger.error(f"Error storing candle: {e}")
        
        logger.info(f"Stored {stored_count} candles for {timeframe}")
    
    def fetch_and_store_recent_data(self, days: int = 5):
        """Fetch and store recent historical data."""
        instrument_token = self.get_instrument_token()
        if not instrument_token:
            logger.error("Could not find Bank Nifty instrument token")
            return
        
        logger.info(f"Fetching last {days} days of historical data...")
        
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        
        # Fetch data for different timeframes
        timeframes = {
            "5minute": "5min",
            "15minute": "15min",
            "60minute": "hourly"
        }
        
        for interval, timeframe_key in timeframes.items():
            candles = self.fetch_historical_data(instrument_token, from_date, to_date, interval)
            if candles:
                self.store_candles(candles, timeframe_key)
        
        logger.info("Historical data fetch completed")


def main():
    """Main entry point for historical data fetcher."""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Load credentials
        cred_path = Path("credentials.json")
        if not cred_path.exists():
            raise FileNotFoundError("credentials.json not found. Run auto_login.py first.")
        
        with open(cred_path) as f:
            creds = json.load(f)
        
        # Initialize Kite Connect
        kite = KiteConnect(api_key=creds["api_key"])
        kite.set_access_token(creds["access_token"])
        
        # Initialize market memory
        market_memory = MarketMemory()
        
        # Initialize fetcher
        fetcher = HistoricalDataFetcher(kite, market_memory)
        
        # Fetch last 5 days of data
        fetcher.fetch_and_store_recent_data(days=5)
        
        logger.info("✅ Historical data fetch completed")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

