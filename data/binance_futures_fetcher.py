"""Binance Futures Fetcher - Generic for any crypto futures, currency/region agnostic."""

import asyncio
import json
import logging
import websockets
from datetime import datetime
from typing import Dict, Any, Optional
from data.derivatives_fetcher import DerivativesFetcher

logger = logging.getLogger(__name__)


class BinanceFuturesFetcher(DerivativesFetcher):
    """
    Fetches futures data from Binance.
    Completely generic - works for any crypto futures (BTC, ETH, etc.).
    No hardcoding of symbols, currencies, or regions.
    """
    
    def __init__(self, symbol: str, currency: str = "USD"):
        """
        Initialize Binance futures fetcher.
        
        Args:
            symbol: Crypto symbol (e.g., "BTCUSDT", "ETHUSDT")
            currency: Base currency (e.g., "USD", "BTC")
        """
        self.symbol = symbol.upper()
        self.currency = currency
        self.region = "GLOBAL"
        self.exchange = "BINANCE"
        
        # WebSocket connections
        self.ws_futures: Optional[websockets.WebSocketClientProtocol] = None
        self.ws_funding: Optional[websockets.WebSocketClientProtocol] = None
        self.ws_oi: Optional[websockets.WebSocketClientProtocol] = None
        
        # Latest data cache
        self.latest_futures_data: Dict[str, Any] = {}
        self.latest_funding_data: Dict[str, Any] = {}
        self.latest_oi_data: Dict[str, Any] = {}
        
        # Connection status
        self.connected = False
        self.running = False
        
        # Background tasks
        self._receive_tasks: list[asyncio.Task] = []
    
    async def initialize(self) -> None:
        """Initialize WebSocket connections."""
        logger.info(f"Initializing Binance Futures Fetcher for {self.symbol}")
        
        try:
            # Connect to futures ticker stream
            symbol_lower = self.symbol.lower()
            futures_uri = f"wss://fstream.binance.com/ws/{symbol_lower}@ticker"
            
            self.ws_futures = await websockets.connect(
                futures_uri,
                ping_interval=20,
                ping_timeout=10
            )
            logger.info(f"[OK] Connected to Binance Futures WebSocket: {futures_uri}")
            
            # Connect to funding rate stream
            funding_uri = f"wss://fstream.binance.com/ws/{symbol_lower}@markPrice"
            self.ws_funding = await websockets.connect(
                funding_uri,
                ping_interval=20,
                ping_timeout=10
            )
            logger.info(f"[OK] Connected to Binance Funding Rate WebSocket: {funding_uri}")
            
            # Connect to open interest stream (if available)
            try:
                oi_uri = f"wss://fstream.binance.com/ws/{symbol_lower}@openInterest"
                self.ws_oi = await websockets.connect(
                    oi_uri,
                    ping_interval=20,
                    ping_timeout=10
                )
                logger.info(f"[OK] Connected to Binance Open Interest WebSocket: {oi_uri}")
            except Exception as e:
                logger.warning(f"Open Interest stream not available: {e}")
                self.ws_oi = None
            
            # Start background tasks to receive data
            self.running = True
            self._receive_tasks = [
                asyncio.create_task(self._receive_futures_data()),
                asyncio.create_task(self._receive_funding_data()),
            ]
            
            if self.ws_oi:
                self._receive_tasks.append(
                    asyncio.create_task(self._receive_oi_data())
                )
            
            self.connected = True
            
            # Wait a moment for initial data
            await asyncio.sleep(2)
            
            logger.info(f"[OK] Binance Futures Fetcher initialized for {self.symbol}")
            
        except Exception as e:
            logger.error(f"Error initializing Binance Futures Fetcher: {e}", exc_info=True)
            self.connected = False
            raise
    
    async def _receive_futures_data(self):
        """Receive futures ticker data."""
        while self.running:
            try:
                if not self.ws_futures:
                    break
                
                message = await self.ws_futures.recv()
                data = json.loads(message)
                
                # Parse ticker data
                self.latest_futures_data = {
                    "futures_price": float(data.get("c", 0)),  # Last price
                    "volume": float(data.get("v", 0)),  # 24h volume
                    "high_24h": float(data.get("h", 0)),
                    "low_24h": float(data.get("l", 0)),
                    "open_24h": float(data.get("o", 0)),
                    "price_change_24h": float(data.get("P", 0)),  # Price change %
                    "timestamp": datetime.now().isoformat()
                }
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Futures WebSocket closed, reconnecting...")
                await self._reconnect_futures()
            except Exception as e:
                logger.error(f"Error receiving futures data: {e}")
                await asyncio.sleep(5)
    
    async def _receive_funding_data(self):
        """Receive funding rate data."""
        while self.running:
            try:
                if not self.ws_funding:
                    break
                
                message = await self.ws_funding.recv()
                data = json.loads(message)
                
                # Parse funding rate data
                self.latest_funding_data = {
                    "mark_price": float(data.get("p", 0)),
                    "funding_rate": float(data.get("r", 0)),  # Funding rate
                    "next_funding_time": datetime.fromtimestamp(
                        data.get("T", 0) / 1000
                    ).isoformat() if data.get("T") else None,
                    "timestamp": datetime.now().isoformat()
                }
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Funding WebSocket closed, reconnecting...")
                await self._reconnect_funding()
            except Exception as e:
                logger.error(f"Error receiving funding data: {e}")
                await asyncio.sleep(5)
    
    async def _receive_oi_data(self):
        """Receive open interest data."""
        while self.running:
            try:
                if not self.ws_oi:
                    break
                
                message = await self.ws_oi.recv()
                data = json.loads(message)
                
                # Parse open interest data
                self.latest_oi_data = {
                    "open_interest": float(data.get("openInterest", 0)),
                    "timestamp": datetime.now().isoformat()
                }
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Open Interest WebSocket closed, will try REST API fallback")
                self.ws_oi = None
                # Start REST API fallback task
                if not hasattr(self, '_oi_rest_task') or self._oi_rest_task.done():
                    self._oi_rest_task = asyncio.create_task(self._fetch_oi_via_rest())
                break
            except Exception as e:
                logger.error(f"Error receiving OI data: {e}, trying REST API fallback")
                self.ws_oi = None
                # Start REST API fallback task
                if not hasattr(self, '_oi_rest_task') or self._oi_rest_task.done():
                    self._oi_rest_task = asyncio.create_task(self._fetch_oi_via_rest())
                break
    
    async def _fetch_oi_via_rest(self):
        """Fallback: Fetch open interest via REST API."""
        import aiohttp
        while self.running:
            try:
                # Binance REST API for open interest
                url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={self.symbol}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self.latest_oi_data = {
                                "open_interest": float(data.get("openInterest", 0)),
                                "timestamp": datetime.now().isoformat()
                            }
                            logger.debug(f"Fetched OI via REST: {self.latest_oi_data['open_interest']}")
                        else:
                            logger.warning(f"REST API OI fetch failed: {resp.status}")
                # Update every 30 seconds via REST
                await asyncio.sleep(30)
            except Exception as e:
                logger.debug(f"REST API OI fetch error: {e}")
                await asyncio.sleep(30)
    
    async def _reconnect_futures(self):
        """Reconnect futures WebSocket."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                symbol_lower = self.symbol.lower()
                uri = f"wss://fstream.binance.com/ws/{symbol_lower}@ticker"
                self.ws_futures = await websockets.connect(uri, ping_interval=20)
                logger.info(f"[OK] Reconnected to futures stream (attempt {attempt + 1})")
                return
            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(f"Reconnect attempt {attempt + 1} failed, waiting {wait_time}s")
                await asyncio.sleep(wait_time)
    
    async def _reconnect_funding(self):
        """Reconnect funding WebSocket."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                symbol_lower = self.symbol.lower()
                uri = f"wss://fstream.binance.com/ws/{symbol_lower}@markPrice"
                self.ws_funding = await websockets.connect(uri, ping_interval=20)
                logger.info(f"[OK] Reconnected to funding stream (attempt {attempt + 1})")
                return
            except Exception as e:
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
    
    async def fetch_futures(
        self,
        contract: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch futures data.
        
        Args:
            contract: Optional contract identifier (not used for perpetuals)
            **kwargs: Additional parameters
        
        Returns:
            Futures data dictionary
        """
        if not self.connected or not self.latest_futures_data:
            # Return empty if not connected
            return {
                "futures_price": 0.0,
                "currency": self.currency,
                "timestamp": datetime.now().isoformat(),
                "exchange": self.exchange,
                "region": self.region
            }
        
        # Combine futures, funding, and OI data
        futures_data = {
            "futures_price": self.latest_futures_data.get("futures_price", 0.0),
            "volume": self.latest_futures_data.get("volume", 0.0),
            "high_24h": self.latest_futures_data.get("high_24h", 0.0),
            "low_24h": self.latest_futures_data.get("low_24h", 0.0),
            "price_change_24h": self.latest_futures_data.get("price_change_24h", 0.0),
            "currency": self.currency,
            "contract": "PERPETUAL",  # Binance perpetual futures
            "timestamp": self.latest_futures_data.get("timestamp", datetime.now().isoformat()),
            "exchange": self.exchange,
            "region": self.region
        }
        
        # Add funding rate if available
        if self.latest_funding_data:
            futures_data["funding_rate"] = self.latest_funding_data.get("funding_rate", 0.0)
            futures_data["mark_price"] = self.latest_funding_data.get("mark_price", 0.0)
            futures_data["next_funding_time"] = self.latest_funding_data.get("next_funding_time")
        
        # Add open interest if available
        if self.latest_oi_data:
            futures_data["open_interest"] = self.latest_oi_data.get("open_interest", 0.0)
        
        return futures_data
    
    async def fetch_options_chain(
        self,
        strikes: Optional[list] = None,
        expiry: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch options chain - not available for Binance via WebSocket.
        Returns empty dict.
        """
        logger.debug("Binance options not available via WebSocket")
        return {}
    
    def supports_options(self) -> bool:
        """Binance options not available via standard WebSocket."""
        return False
    
    def supports_futures(self) -> bool:
        """Binance supports futures."""
        return True
    
    def supports_spot(self) -> bool:
        """Binance supports spot."""
        return True
    
    def get_currency(self) -> str:
        """Get base currency."""
        return self.currency
    
    def get_region(self) -> str:
        """Get region."""
        return self.region
    
    def get_exchange(self) -> str:
        """Get exchange name."""
        return self.exchange
    
    async def stop(self):
        """Stop WebSocket connections."""
        self.running = False
        
        # Cancel receive tasks
        for task in self._receive_tasks:
            task.cancel()
        
        # Close WebSocket connections
        if self.ws_futures:
            await self.ws_futures.close()
        if self.ws_funding:
            await self.ws_funding.close()
        if self.ws_oi:
            await self.ws_oi.close()
        
        self.connected = False
        logger.info(f"Binance Futures Fetcher stopped for {self.symbol}")

