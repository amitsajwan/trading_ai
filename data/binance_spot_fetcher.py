"""Binance Spot Fetcher - Generic for any crypto spot, currency/region agnostic."""

import asyncio
import json
import logging
import websockets
from datetime import datetime
from typing import Dict, Any, Optional
from data.derivatives_fetcher import DerivativesFetcher

logger = logging.getLogger(__name__)


class BinanceSpotFetcher(DerivativesFetcher):
    """
    Fetches spot data from Binance.
    Completely generic - works for any crypto spot pair.
    """
    
    def __init__(self, symbol: str, currency: str = "USD"):
        """
        Initialize Binance spot fetcher.
        
        Args:
            symbol: Crypto symbol (e.g., "BTCUSDT", "ETHUSDT")
            currency: Base currency (e.g., "USD")
        """
        self.symbol = symbol.upper()
        self.currency = currency
        self.region = "GLOBAL"
        self.exchange = "BINANCE"
        
        # WebSocket connection
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.latest_data: Dict[str, Any] = {}
        self.connected = False
        self.running = False
    
    async def initialize(self) -> None:
        """Initialize WebSocket connection."""
        logger.info(f"Initializing Binance Spot Fetcher for {self.symbol}")
        
        try:
            symbol_lower = self.symbol.lower()
            uri = f"wss://stream.binance.com:9443/ws/{symbol_lower}@ticker"
            
            self.ws = await websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=10
            )
            
            self.running = True
            self.connected = True
            
            # Start receiving data
            asyncio.create_task(self._receive_data())
            
            # Wait for initial data
            await asyncio.sleep(2)
            
            logger.info(f"[OK] Binance Spot Fetcher initialized for {self.symbol}")
            
        except Exception as e:
            logger.error(f"Error initializing Binance Spot Fetcher: {e}", exc_info=True)
            self.connected = False
            raise
    
    async def _receive_data(self):
        """Receive spot ticker data."""
        while self.running:
            try:
                if not self.ws:
                    break
                
                message = await self.ws.recv()
                data = json.loads(message)
                
                self.latest_data = {
                    "spot_price": float(data.get("c", 0)),
                    "volume": float(data.get("v", 0)),
                    "high_24h": float(data.get("h", 0)),
                    "low_24h": float(data.get("l", 0)),
                    "price_change_24h": float(data.get("P", 0)),
                    "timestamp": datetime.now().isoformat()
                }
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Spot WebSocket closed, reconnecting...")
                await self._reconnect()
            except Exception as e:
                logger.error(f"Error receiving spot data: {e}")
                await asyncio.sleep(5)
    
    async def _reconnect(self):
        """Reconnect WebSocket."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                symbol_lower = self.symbol.lower()
                uri = f"wss://stream.binance.com:9443/ws/{symbol_lower}@ticker"
                self.ws = await websockets.connect(uri, ping_interval=20)
                logger.info(f"[OK] Reconnected to spot stream")
                return
            except Exception as e:
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
    
    async def fetch_futures(self, **kwargs) -> Dict[str, Any]:
        """Spot fetcher doesn't provide futures data."""
        return {}
    
    async def fetch_options_chain(self, **kwargs) -> Dict[str, Any]:
        """Spot fetcher doesn't provide options data."""
        return {}
    
    async def fetch_spot(self) -> Dict[str, Any]:
        """Fetch spot data."""
        if not self.connected or not self.latest_data:
            return {
                "spot_price": 0.0,
                "currency": self.currency,
                "timestamp": datetime.now().isoformat(),
                "exchange": self.exchange,
                "region": self.region
            }
        
        return {
            **self.latest_data,
            "currency": self.currency,
            "exchange": self.exchange,
            "region": self.region
        }
    
    def supports_options(self) -> bool:
        return False
    
    def supports_futures(self) -> bool:
        return False
    
    def supports_spot(self) -> bool:
        return True
    
    def get_currency(self) -> str:
        return self.currency
    
    def get_region(self) -> str:
        return self.region
    
    def get_exchange(self) -> str:
        return self.exchange
    
    async def stop(self):
        """Stop WebSocket connection."""
        self.running = False
        if self.ws:
            await self.ws.close()
        self.connected = False

