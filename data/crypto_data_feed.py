"""Real-time crypto data feed using Binance WebSocket (free)."""

import asyncio
import json
import logging
import time
import websockets
from datetime import datetime
from typing import Dict, Any, Optional
from data.market_memory import MarketMemory
from data.binance_futures_fetcher import BinanceFuturesFetcher
from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings

logger = logging.getLogger(__name__)


class CryptoDataFeed:
    """
    Real-time crypto data feed using Binance WebSocket.
    Supports Bitcoin and other cryptocurrencies.
    Free, no API key required for public streams.
    """
    
    def __init__(self, market_memory: MarketMemory):
        """Initialize crypto data feed."""
        self.market_memory = market_memory
        self.ws: Optional[websockets.WebSocketServerProtocol] = None
        self.running = False
        self.connected = False  # Track connection status

        # Futures data fetcher (perpetual futures: funding rate, OI)
        self.futures_fetcher: Optional[BinanceFuturesFetcher] = None
        self._futures_task: Optional[asyncio.Task] = None
        self._futures_initialized = False
        
        # MongoDB connection
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.ohlc_collection = get_collection(self.db, "ohlc_history")
        
        # OHLC buffers
        self.current_candles = {
            "1min": {},
            "5min": {},
            "15min": {},
            "hourly": {}
        }
        
        # Map instrument symbol to Binance symbol
        self.symbol_map = {
            "BTC-USD": "btcusdt",
            "BTCUSD": "btcusdt",
            "BTC": "btcusdt",
            "ETH-USD": "ethusdt",
            "ETHUSD": "ethusdt",
            "ETH": "ethusdt",
        }

    async def _start_futures_fetcher(self) -> None:
        """Start Binance futures fetcher and continuously store futures metrics into Redis."""
        if self._futures_initialized:
            return

        try:
            binance_symbol = self._get_binance_symbol(settings.instrument_symbol).upper()
            instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()

            self.futures_fetcher = BinanceFuturesFetcher(symbol=binance_symbol, currency="USD")
            await self.futures_fetcher.initialize()
            self._futures_initialized = True
            logger.info(f"✅ Futures fetcher started for {binance_symbol} (publishing to Redis key futures:{instrument_key}:latest)")

            async def _publish_loop():
                # publish every ~1s (dashboard refreshes every 5s)
                while self.running:
                    try:
                        if self.futures_fetcher and getattr(self.futures_fetcher, "connected", False):
                            futures = await self.futures_fetcher.fetch_futures()
                            if futures and (
                                futures.get("futures_price", 0) > 0
                                or futures.get("open_interest", 0) > 0
                                or futures.get("funding_rate") is not None
                            ):
                                self.market_memory.store_futures_data(instrument_key, futures)
                        await asyncio.sleep(1.0)
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.debug(f"Futures publish loop error: {e}")
                        await asyncio.sleep(2.0)

            self._futures_task = asyncio.create_task(_publish_loop())
        except Exception as e:
            logger.warning(f"⚠️ Could not start futures fetcher for dashboard/rules: {e}", exc_info=True)
            self.futures_fetcher = None
            self._futures_initialized = False
    
    def _get_binance_symbol(self, symbol: str) -> str:
        """Convert instrument symbol to Binance format."""
        # Normalize symbol
        symbol_upper = symbol.upper().replace("-", "")
        
        # Check mapping
        if symbol_upper in self.symbol_map:
            return self.symbol_map[symbol_upper]
        
        # Default: assume format is already correct or try to convert
        # BTC-USD -> BTCUSDT, BTC -> BTCUSDT
        if symbol_upper.endswith("USD"):
            return symbol_upper + "T"  # BTCUSD -> BTCUSDT
        elif len(symbol_upper) <= 5:  # Likely just symbol like BTC
            return symbol_upper + "USDT"
        
        return symbol_upper.lower()
    
    async def _process_ticker(self, data: Dict[str, Any]):
        """Process ticker data from Binance WebSocket."""
        try:
            symbol = data.get("s", "")  # Symbol (e.g., BTCUSDT)
            price = float(data.get("c", 0))  # Last price
            volume = float(data.get("v", 0))  # 24h volume
            timestamp = datetime.now()
            
            if not price or price == 0:
                logger.warning(f"Invalid price in ticker: {data}")
                return
            
            # Create tick data
            tick_data = {
                "instrument_token": symbol,
                "last_price": price,
                "price": price,
                "volume": volume,
                "timestamp": timestamp.isoformat(),
                "bid_price": float(data.get("b", price)),  # Best bid
                "ask_price": float(data.get("a", price)),  # Best ask
                "bid_quantity": float(data.get("B", 0)),  # Best bid qty
                "ask_quantity": float(data.get("A", 0)),  # Best ask qty
                "high_24h": float(data.get("h", price)),
                "low_24h": float(data.get("l", price)),
                "open_24h": float(data.get("o", price)),
                "change_24h": float(data.get("P", 0)),  # Price change percent
            }
            
            # Store tick
            instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
            self.market_memory.store_tick(instrument_key, tick_data)
            
            # Log tick reception periodically (every 10 ticks to avoid spam)
            if not hasattr(self, '_tick_count'):
                self._tick_count = 0
            self._tick_count += 1
            if self._tick_count % 10 == 0:
                logger.info(f"Received {self._tick_count} ticks for {symbol} @ ${price:,.2f}")
            
            # Log first few ticks to confirm it's working
            if self._tick_count <= 3:
                logger.info(f"[TICK #{self._tick_count}] Stored tick: {symbol} @ ${price:,.2f}")
            
            # Update OHLC buffers
            self._update_ohlc_buffers(symbol, price, volume, timestamp)
            
            logger.debug(f"Processed tick: {symbol} @ {price}")
            
        except Exception as e:
            logger.error(f"Error processing ticker: {e}", exc_info=True)
    
    def _update_ohlc_buffers(self, symbol: str, price: float, volume: float, timestamp: datetime):
        """Update OHLC buffers for different timeframes."""
        minute = timestamp.minute
        hour = timestamp.hour
        
        # 1-minute candle
        candle_key = f"{symbol}:1min"
        if candle_key not in self.current_candles.get("1min", {}):
            self.current_candles.setdefault("1min", {})[candle_key] = {
                "instrument": settings.instrument_symbol,
                "instrument_token": symbol,
                "timestamp": timestamp.replace(second=0, microsecond=0).isoformat(),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "timeframe": "1min"
            }
        else:
            candle = self.current_candles["1min"][candle_key]
            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price
            candle["volume"] += volume
        
        # Store 1-minute candle
        candle = self.current_candles["1min"][candle_key]
        self._store_candle("1min", candle)
        
        # 5-minute candle (on minute boundaries)
        if minute % 5 == 0:
            candle = {
                "instrument": settings.instrument_symbol,
                "instrument_token": symbol,
                "timestamp": timestamp.replace(second=0, microsecond=0).isoformat(),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "timeframe": "5min"
            }
            self._store_candle("5min", candle)
        
        # 15-minute candle
        if minute % 15 == 0:
            candle = {
                "instrument": settings.instrument_symbol,
                "instrument_token": symbol,
                "timestamp": timestamp.replace(second=0, microsecond=0).isoformat(),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "timeframe": "15min"
            }
            self._store_candle("15min", candle)
        
        # Hourly candle
        if minute == 0:
            candle = {
                "instrument": settings.instrument_symbol,
                "instrument_token": symbol,
                "timestamp": timestamp.replace(minute=0, second=0, microsecond=0).isoformat(),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "timeframe": "hourly"
            }
            self._store_candle("hourly", candle)
    
    def _store_candle(self, timeframe: str, candle: Dict[str, Any]):
        """Store candle in Redis and MongoDB."""
        try:
            # Store in Redis
            instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
            self.market_memory.store_ohlc(instrument_key, timeframe, candle)
            
            # Store in MongoDB
            self.ohlc_collection.update_one(
                {
                    "instrument": candle["instrument"],
                    "timestamp": candle["timestamp"],
                    "timeframe": timeframe
                },
                {"$set": candle},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error storing candle: {e}", exc_info=True)
    
    async def _connect_and_subscribe(self):
        """Connect to Binance WebSocket and subscribe to ticker stream."""
        # Get Binance symbol
        binance_symbol = self._get_binance_symbol(settings.instrument_symbol)
        
        # Binance WebSocket URL (public stream, no auth needed)
        # Format: wss://stream.binance.com:9443/ws/<symbol>@ticker
        ws_url = f"wss://stream.binance.com:9443/ws/{binance_symbol}@ticker"
        
        logger.info(f"Connecting to Binance WebSocket: {ws_url}")
        logger.info(f"Subscribing to: {binance_symbol} (from {settings.instrument_symbol})")
        
        try:
            # Connect to WebSocket with keepalive
            ws = await websockets.connect(
                ws_url,
                ping_interval=20,  # Send ping every 20 seconds to keep alive
                ping_timeout=10,   # Wait 10 seconds for pong
                close_timeout=10
            )
            self.ws = ws
            self.connected = True
            logger.info(f"[OK] Connected to Binance WebSocket for {binance_symbol}")
            logger.info(f"[OK] WebSocket connection established - ready to receive data")
            
            # Receive messages - this loop will exit if connection closes
            message_count = 0
            last_message_time = time.time()
            
            async for message in ws:
                if not self.running:
                    break
                
                message_count += 1
                last_message_time = time.time()
                
                try:
                    data = json.loads(message)
                    await self._process_ticker(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing WebSocket message: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
            
            # If we exit the loop, connection closed
            logger.warning(f"WebSocket message loop exited (received {message_count} messages)")
            self.connected = False
                        
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Binance WebSocket connection closed: {e}")
            self.connected = False
        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"WebSocket invalid status code: {e}")
            self.connected = False
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}", exc_info=True)
            self.connected = False
            raise
        finally:
            # Clean up
            if self.ws:
                try:
                    await self.ws.close()
                except:
                    pass
                self.ws = None
            self.connected = False
    
    async def start(self):
        """Start the crypto data feed with improved reconnection logic and error handling."""
        if self.running:
            logger.warning("Crypto data feed already running")
            return
        
        self.running = True
        self._tick_count = 0
        reconnect_delay = 5  # Start with 5 seconds
        max_reconnect_delay = 60  # Max 60 seconds
        consecutive_failures = 0
        
        logger.info("=" * 60)
        logger.info("Starting Crypto Data Feed (Binance WebSocket)")
        logger.info(f"Instrument: {settings.instrument_name} ({settings.instrument_symbol})")
        logger.info("=" * 60)

        # Start futures fetcher once (in background) so dashboard can show funding/OI
        if not self._futures_initialized:
            await self._start_futures_fetcher()
        
        # Keep reconnecting on failure - CRITICAL: This loop must keep running
        while self.running:
            try:
                logger.info(f"Attempting WebSocket connection (attempt #{consecutive_failures + 1})...")
                await self._connect_and_subscribe()
                # If we get here, connection closed normally - reconnect
                self.connected = False
                consecutive_failures += 1
                if self.running:
                    logger.warning(f"WebSocket connection closed normally. Reconnecting in {reconnect_delay}s... (failure #{consecutive_failures})")
                    await asyncio.sleep(reconnect_delay)
                    # Exponential backoff, but cap at max
                    reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
            except websockets.exceptions.ConnectionClosed:
                self.connected = False
                consecutive_failures += 1
                if self.running:
                    logger.warning(f"WebSocket connection closed. Reconnecting in {reconnect_delay}s... (failure #{consecutive_failures})")
                    await asyncio.sleep(reconnect_delay)
                    # Exponential backoff, but cap at max
                    reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
                else:
                    break
            except Exception as e:
                self.connected = False
                consecutive_failures += 1
                if self.running:
                    logger.error(f"WebSocket error: {e}. Reconnecting in {reconnect_delay}s... (failure #{consecutive_failures})", exc_info=True)
                    await asyncio.sleep(reconnect_delay)
                    # Exponential backoff
                    reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
                else:
                    break
        
        self.connected = False
        logger.info("Crypto data feed stopped")
    
    def stop(self):
        """Stop the crypto data feed."""
        logger.info("Stopping crypto data feed...")
        self.running = False
        if self.ws:
            # Close connection
            asyncio.create_task(self.ws.close())

        # Stop futures publisher + futures fetcher
        if self._futures_task:
            try:
                self._futures_task.cancel()
            except Exception:
                pass
            self._futures_task = None
        if self.futures_fetcher:
            try:
                asyncio.create_task(self.futures_fetcher.stop())
            except Exception:
                pass
            self.futures_fetcher = None
        self._futures_initialized = False

