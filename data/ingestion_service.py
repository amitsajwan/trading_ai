"""Real-time data ingestion service for Zerodha Kite Connect."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from kiteconnect import KiteConnect, KiteTicker
from data.market_memory import MarketMemory
from mongodb_schema import get_mongo_client, setup_mongodb, get_collection
from config.settings import settings

logger = logging.getLogger(__name__)


class DataIngestionService:
    """
    Real-time data ingestion service using Zerodha Kite WebSocket.
    Subscribes to Bank Nifty instruments and buffers OHLCV data.
    """
    
    def __init__(self, kite: KiteConnect, market_memory: MarketMemory):
        """Initialize data ingestion service."""
        self.kite = kite
        self.market_memory = market_memory
        self.ticker: Optional[KiteTicker] = None
        self.running = False
        
        # OHLC buffers for different timeframes
        self.ohlc_buffers: Dict[str, List[Dict[str, Any]]] = {
            "1min": [],
            "5min": [],
            "15min": [],
            "hourly": [],
            "daily": []
        }
        
        # MongoDB connection
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.ohlc_collection = get_collection(self.db, "ohlc_history")
        
        # Current candles being built (for proper OHLC aggregation)
        self.current_candles = {
            "1min": {},
            "5min": {},
            "15min": {},
            "hourly": {}
        }
        
        # Current candles being built (for proper OHLC aggregation)
        self.current_candles = {
            "1min": {},
            "5min": {},
            "15min": {},
            "hourly": {},
            "daily": {}
        }
    
    def get_instrument_token(self, instrument: Optional[str] = None) -> Optional[int]:
        """Get instrument token for the configured instrument symbol."""
        try:
            # Use configured instrument symbol if not provided
            if instrument is None:
                instrument = settings.instrument_symbol
            
            # If token is directly configured, use it
            if settings.instrument_token and settings.instrument_token.isdigit():
                return int(settings.instrument_token)
            
            # Get instrument list from configured exchange
            exchange = settings.instrument_exchange
            instruments = self.kite.instruments(exchange)
            
            # Find instrument by symbol or name
            for inst in instruments:
                if (inst.get("tradingsymbol") == instrument or 
                    inst.get("name") == instrument or
                    inst.get("tradingsymbol") == settings.instrument_symbol or
                    inst.get("name") == settings.instrument_name):
                    return inst["instrument_token"]
            
            # Fallback: try to parse if it's already a token
            if instrument.isdigit():
                return int(instrument)
            
            logger.warning(f"Instrument '{instrument}' not found in {exchange}")
            return None
        except Exception as e:
            logger.error(f"Error getting instrument token: {e}")
            return None
    
    def on_ticks(self, ws, ticks):
        """Handle incoming ticks from Kite WebSocket."""
        if not hasattr(self, '_tick_count'):
            self._tick_count = 0
        
        if not ticks:
            logger.warning("Received empty ticks array")
            return
        
        logger.info(f"📊 CALLBACK FIRED: Received {len(ticks)} ticks")
        
        for tick in ticks:
            try:
                instrument_token = tick.get("instrument_token")
                last_price = tick.get("last_price", 0.0)
                volume = tick.get("volume", 0)
                timestamp = datetime.now()
                
                if not last_price or last_price == 0:
                    logger.warning(f"Invalid price in tick: {tick}")
                    continue
                
                self._tick_count += 1
                
                # Extract all available tick data (MODE_FULL provides more fields)
                tick_ohlc = tick.get("ohlc", {})
                buy_quantity = tick.get("buy_quantity", 0)
                sell_quantity = tick.get("sell_quantity", 0)
                average_price = tick.get("average_price", last_price)
                change = tick.get("change", 0.0)
                net_change = tick.get("net_change", 0.0)
                last_traded_price = tick.get("last_traded_price", last_price)
                last_traded_quantity = tick.get("last_traded_quantity", 0)
                
                # Extract market depth (bid/ask)
                depth = tick.get("depth", {})
                buy_depth = depth.get("buy", [])
                sell_depth = depth.get("sell", [])
                
                # Get best bid/ask
                best_bid_price = buy_depth[0].get("price") if buy_depth else None
                best_bid_quantity = buy_depth[0].get("quantity") if buy_depth else 0
                best_ask_price = sell_depth[0].get("price") if sell_depth else None
                best_ask_quantity = sell_depth[0].get("quantity") if sell_depth else 0
                
                # Calculate derived signals
                bid_ask_spread = (best_ask_price - best_bid_price) if (best_bid_price and best_ask_price) else None
                buy_sell_imbalance = (buy_quantity / (buy_quantity + sell_quantity)) if (buy_quantity + sell_quantity > 0) else 0.5
                
                # Log first few ticks and then every 100th tick
                if self._tick_count <= 10 or self._tick_count % 100 == 0:
                    logger.info(f"📊 Tick #{self._tick_count}: Price={last_price:.2f}, Volume={volume}, "
                              f"Buy={buy_quantity}, Sell={sell_quantity}, Spread={bid_ask_spread}")
                
                # Store comprehensive tick data
                try:
                    tick_data = {
                        "instrument_token": instrument_token,
                        "last_price": last_price,
                        "price": last_price,  # Also store as "price" for compatibility
                        "volume": volume,
                        "timestamp": timestamp.isoformat(),
                        # OHLC from tick (if available)
                        "ohlc": tick_ohlc,
                        # Order flow data
                        "buy_quantity": buy_quantity,
                        "sell_quantity": sell_quantity,
                        "buy_sell_imbalance": buy_sell_imbalance,
                        # Bid/Ask data
                        "best_bid_price": best_bid_price,
                        "best_bid_quantity": best_bid_quantity,
                        "best_ask_price": best_ask_price,
                        "best_ask_quantity": best_ask_quantity,
                        "bid_ask_spread": bid_ask_spread,
                        # Price change data
                        "average_price": average_price,
                        "change": change,
                        "net_change": net_change,
                        "last_traded_price": last_traded_price,
                        "last_traded_quantity": last_traded_quantity,
                        # Market depth (store top 3 levels)
                        "depth_buy": buy_depth[:3] if buy_depth else [],
                        "depth_sell": sell_depth[:3] if sell_depth else []
                    }
                    # Use configured instrument symbol for storage
                instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
                self.market_memory.store_tick(instrument_key, tick_data)
                except Exception as e:
                    logger.error(f"Error storing tick: {e}", exc_info=True)
                
                # Update OHLC buffers
                self._update_ohlc_buffers(instrument_token, last_price, volume, timestamp)
                
            except Exception as e:
                logger.error(f"Error processing tick: {e}", exc_info=True)
    
    def _update_ohlc_buffers(self, instrument_token: int, price: float, volume: int, timestamp: datetime):
        """Update OHLC buffers for different timeframes."""
        # Note: Tick is already stored in on_ticks, so we don't need to store it again here
        
        # Update OHLC candles (simplified - in production, aggregate ticks properly)
        minute = timestamp.minute
        hour = timestamp.hour
        
        # Create/update 1-minute candle
        candle_key = f"{instrument_token}:1min"
        if candle_key not in self.current_candles.get("1min", {}):
            # Start new candle
            self.current_candles.setdefault("1min", {})[candle_key] = {
                "instrument": settings.instrument_symbol,
                "instrument_token": instrument_token,
                "timestamp": timestamp.replace(second=0, microsecond=0).isoformat(),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "timeframe": "1min"
            }
        else:
            # Update existing candle
            candle = self.current_candles["1min"][candle_key]
            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price
            candle["volume"] += volume
        
        # Store updated candle
        candle = self.current_candles["1min"][candle_key]
        self._add_candle("1min", candle)
        
        # 5-minute candle
        if minute % 5 == 0:
            candle = {
                "instrument_token": instrument_token,
                "timestamp": timestamp.replace(second=0, microsecond=0).isoformat(),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "timeframe": "5min"
            }
            self._add_candle("5min", candle)
        
        # 15-minute candle
        if minute % 15 == 0:
            candle = {
                "instrument_token": instrument_token,
                "timestamp": timestamp.replace(second=0, microsecond=0).isoformat(),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "timeframe": "15min"
            }
            self._add_candle("15min", candle)
        
        # Hourly candle
        if minute == 0:
            candle = {
                "instrument_token": instrument_token,
                "timestamp": timestamp.replace(minute=0, second=0, microsecond=0).isoformat(),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "timeframe": "hourly"
            }
            self._add_candle("hourly", candle)
    
    def _add_candle(self, timeframe: str, candle: Dict[str, Any]):
        """Add candle to buffer and store in Redis/MongoDB."""
        # Ensure instrument field is set
        if "instrument" not in candle:
            candle["instrument"] = settings.instrument_symbol
        
        buffer = self.ohlc_buffers[timeframe]
        buffer.append(candle)
        
        # Keep only last 100 candles in buffer
        if len(buffer) > 100:
            buffer.pop(0)
        
        # Store in Redis (remove _id if present)
        try:
            candle_for_redis = {k: v for k, v in candle.items() if k != '_id'}
            self.market_memory.store_ohlc("BANKNIFTY", timeframe, candle_for_redis)
        except Exception as e:
            logger.error(f"Error storing OHLC in Redis: {e}", exc_info=True)
        
        # Store in MongoDB (use update_one with upsert to avoid duplicates)
        try:
            # Use timestamp + instrument as unique key to avoid duplicates
            filter_dict = {
                "instrument": candle["instrument"],
                "timestamp": candle.get("timestamp"),
                "timeframe": candle.get("timeframe", timeframe)
            }
            # Remove _id before inserting/updating
            candle_for_mongo = {k: v for k, v in candle.items() if k != '_id'}
            self.ohlc_collection.update_one(
                filter_dict,
                {"$set": candle_for_mongo},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error storing OHLC in MongoDB: {e}", exc_info=True)
    
    def on_connect(self, ws, response):
        """Handle WebSocket connection."""
        logger.info("=" * 60)
        logger.info("✅ WebSocket CONNECTED!")
        logger.info(f"Connection response: {response}")
        logger.info("=" * 60)
        
        # Subscribe to Bank Nifty using pre-fetched token
        if hasattr(self, '_instrument_token') and self._instrument_token:
            logger.info(f"Subscribing to token: {self._instrument_token}")
            ws.subscribe([self._instrument_token])
            ws.set_mode(ws.MODE_FULL, [self._instrument_token])
                logger.info(f"✅ Subscribed to {settings.instrument_name} (token: {self._instrument_token})")
            logger.info("✅ Waiting for market data...")
            logger.info("=" * 60)
        else:
            logger.error(f"❌ Instrument token not available - trying to fetch now...")
            # Fallback: try to get token now (might be slow)
            instrument_token = self.get_instrument_token("NIFTY BANK")
            if instrument_token:
                self._instrument_token = instrument_token
                logger.info(f"Subscribing to token: {instrument_token}")
                ws.subscribe([instrument_token])
                ws.set_mode(ws.MODE_FULL, [instrument_token])
                logger.info(f"✅ Subscribed to Bank Nifty (token: {instrument_token})")
            else:
                logger.error(f"❌ Could not find instrument token for {settings.instrument_name} ({settings.instrument_symbol})")
                logger.error("Please check if market is open or instrument list is accessible")
    
    def on_close(self, ws, code, reason):
        """Handle WebSocket close."""
        logger.warning(f"⚠️  WebSocket closed: {code} - {reason}")
        self.running = False
    
    def on_error(self, ws, code, reason):
        """Handle WebSocket error."""
        logger.error(f"❌ WebSocket error: {code} - {reason}")
        self.running = False
    
    def start(self):
        """Start the data ingestion service."""
        if self.running:
            logger.warning("Data ingestion service already running")
            return
        
        try:
            access_token = self.kite.access_token
            api_key = self.kite.api_key
            
            # Get instrument token BEFORE connecting (faster and more reliable)
            logger.info(f"Fetching {settings.instrument_name} ({settings.instrument_symbol}) instrument token...")
            self._instrument_token = self.get_instrument_token()
            if not self._instrument_token:
                raise ValueError(f"Could not find {settings.instrument_name} ({settings.instrument_symbol}) instrument token")
            logger.info(f"✅ Found instrument token: {self._instrument_token}")
            
            logger.info("Initializing Zerodha WebSocket...")
            self.ticker = KiteTicker(api_key, access_token)
            
            # Set callbacks
            self.ticker.on_ticks = self.on_ticks
            self.ticker.on_connect = self.on_connect
            self.ticker.on_close = self.on_close
            self.ticker.on_error = self.on_error
            
            self.running = True
            logger.info("Connecting to Zerodha WebSocket...")
            self.ticker.connect(threaded=True)
            logger.info("WebSocket connection initiated (connecting in background thread)")
            
        except Exception as e:
            logger.error(f"❌ Error starting data ingestion service: {e}", exc_info=True)
            self.running = False
            raise
    
    def stop(self):
        """Stop the data ingestion service."""
        if self.ticker:
            self.ticker.close()
        self.running = False
        logger.info("Data ingestion service stopped")
    
    def get_ohlc_data(self, timeframe: str, count: int = 60) -> List[Dict[str, Any]]:
        """Get OHLC data for a specific timeframe."""
        return self.market_memory.get_recent_ohlc("BANKNIFTY", timeframe, count)

