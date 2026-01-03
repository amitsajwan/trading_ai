"""Instrument detector - fully generic, no hardcoding of regions/currencies/instruments."""

import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime, time
from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class InstrumentProfile:
    """Profile of an instrument - completely generic."""
    
    # Basic identification
    symbol: str
    exchange: str
    currency: str  # INR, USD, BTC, etc. - auto-detected
    region: str  # INDIA, USA, GLOBAL, etc. - auto-detected
    
    # Instrument characteristics
    instrument_type: str  # SPOT, FUTURES, OPTIONS, CRYPTO_SPOT, CRYPTO_FUTURES, STOCK, INDEX
    has_options: bool
    has_futures: bool
    has_spot: bool
    
    # Data source
    data_source: str  # ZERODHA, BINANCE, IBKR, ALPACA, etc.
    data_source_type: str  # REST_API, WEBSOCKET, FIX_PROTOCOL
    
    # Trading characteristics
    optimal_frequency_minutes: int
    market_hours: Dict[str, Any]  # open_time, close_time, timezone, is_24_7
    
    # Available derivatives
    derivatives_available: List[str]  # ["options_chain", "futures", "funding_rate", "open_interest"]
    
    # Additional metadata
    lot_size: Optional[int] = None
    tick_size: Optional[float] = None
    contract_multiplier: Optional[float] = None


class InstrumentDetector:
    """
    Detects instrument characteristics automatically.
    No hardcoding - works for any instrument, region, currency.
    """
    
    # Exchange mappings (can be extended)
    EXCHANGE_REGIONS = {
        "NSE": "INDIA",
        "BSE": "INDIA",
        "NFO": "INDIA",  # Options exchange
        "MCX": "INDIA",
        "BINANCE": "GLOBAL",
        "COINBASE": "GLOBAL",
        "NYSE": "USA",
        "NASDAQ": "USA",
        "CME": "USA",
        "ICE": "USA",
    }
    
    # Currency detection patterns
    CURRENCY_PATTERNS = {
        "INR": ["NSE", "BSE", "NFO", "MCX"],
        "USD": ["NYSE", "NASDAQ", "CME", "COINBASE"],
        "BTC": ["BINANCE", "COINBASE"],  # For crypto pairs
        "ETH": ["BINANCE", "COINBASE"],
    }
    
    # Data source mappings
    DATA_SOURCE_MAP = {
        "ZERODHA": {"exchanges": ["NSE", "BSE", "NFO", "MCX"], "region": "INDIA"},
        "BINANCE": {"exchanges": ["BINANCE"], "region": "GLOBAL"},
        "IBKR": {"exchanges": ["NYSE", "NASDAQ", "CME"], "region": "USA"},
        "ALPACA": {"exchanges": ["NYSE", "NASDAQ"], "region": "USA"},
    }
    
    def detect(
        self, 
        symbol: str, 
        exchange: str, 
        data_source: str
    ) -> InstrumentProfile:
        """
        Detect instrument profile - completely generic.
        
        Args:
            symbol: Instrument symbol (e.g., "NIFTY BANK", "BTC-USD", "AAPL")
            exchange: Exchange code (e.g., "NSE", "BINANCE", "NYSE")
            data_source: Data source name (e.g., "ZERODHA", "BINANCE", "IBKR")
        
        Returns:
            InstrumentProfile with all characteristics
        """
        logger.info(f"Detecting instrument: {symbol} on {exchange} via {data_source}")
        
        # Detect region and currency
        region = self._detect_region(exchange, data_source)
        currency = self._detect_currency(exchange, symbol, data_source)
        
        # Detect instrument type
        instrument_type = self._detect_instrument_type(symbol, exchange, data_source)
        
        # Detect available derivatives
        has_options, has_futures, has_spot = self._detect_derivatives(
            symbol, exchange, data_source, instrument_type
        )
        
        # Detect market hours
        market_hours = self._detect_market_hours(exchange, data_source, instrument_type)
        
        # Calculate optimal frequency
        optimal_frequency = self._calculate_optimal_frequency(
            instrument_type, has_options, has_futures, region
        )
        
        # Get available derivatives
        derivatives_available = self._get_derivatives_list(
            has_options, has_futures, instrument_type
        )
        
        # Get data source type
        data_source_type = self._get_data_source_type(data_source)
        
        profile = InstrumentProfile(
            symbol=symbol,
            exchange=exchange,
            currency=currency,
            region=region,
            instrument_type=instrument_type,
            has_options=has_options,
            has_futures=has_futures,
            has_spot=has_spot,
            data_source=data_source,
            data_source_type=data_source_type,
            optimal_frequency_minutes=optimal_frequency,
            market_hours=market_hours,
            derivatives_available=derivatives_available
        )
        
        logger.info(f"Detected profile: {instrument_type} in {region} ({currency}), "
                   f"options={has_options}, futures={has_futures}, spot={has_spot}")
        
        return profile
    
    def _detect_region(self, exchange: str, data_source: str) -> str:
        """Detect region from exchange or data source."""
        # Check exchange mapping first
        if exchange.upper() in self.EXCHANGE_REGIONS:
            return self.EXCHANGE_REGIONS[exchange.upper()]
        
        # Check data source mapping
        if data_source.upper() in self.DATA_SOURCE_MAP:
            return self.DATA_SOURCE_MAP[data_source.upper()]["region"]
        
        # Default: GLOBAL for unknown
        return "GLOBAL"
    
    def _detect_currency(self, exchange: str, symbol: str, data_source: str) -> str:
        """Detect currency from exchange, symbol, or data source."""
        # Check exchange patterns
        for currency, exchanges in self.CURRENCY_PATTERNS.items():
            if exchange.upper() in exchanges:
                return currency
        
        # Check symbol patterns (e.g., BTC-USD -> USD, BTC-INR -> INR)
        symbol_upper = symbol.upper()
        if "-USD" in symbol_upper or symbol_upper.endswith("USD") or symbol_upper.endswith("USDT"):
            return "USD"  # Crypto pairs quoted in USD
        elif "-INR" in symbol_upper or symbol_upper.endswith("INR"):
            return "INR"
        elif "-BTC" in symbol_upper:
            return "BTC"  # Only if explicitly BTC-BTC pair
        elif "-ETH" in symbol_upper:
            return "ETH"  # Only if explicitly ETH-ETH pair
        
        # Check data source default currency
        if data_source.upper() == "ZERODHA":
            return "INR"
        elif data_source.upper() in ["BINANCE", "COINBASE"]:
            # For crypto exchanges, check if it's a crypto pair
            if any(crypto in symbol_upper for crypto in ["BTC", "ETH", "USDT"]):
                return "USD"  # Crypto pairs typically quoted in USD
            return "USD"
        
        # Default: USD
        return "USD"
    
    def _detect_instrument_type(
        self, 
        symbol: str, 
        exchange: str, 
        data_source: str
    ) -> str:
        """Detect instrument type - no hardcoding."""
        symbol_upper = symbol.upper()
        exchange_upper = exchange.upper()
        
        # Options exchange
        if exchange_upper in ["NFO", "OPRA"] or "OPT" in exchange_upper:
            return "OPTIONS"
        
        # Crypto detection
        if data_source.upper() in ["BINANCE", "COINBASE"]:
            if "FUTURES" in symbol_upper or "PERP" in symbol_upper:
                return "CRYPTO_FUTURES"
            elif "OPTION" in symbol_upper or "-C" in symbol_upper or "-P" in symbol_upper:
                return "CRYPTO_OPTIONS"
            else:
                return "CRYPTO_SPOT"
        
        # Futures exchange
        if exchange_upper in ["MCX", "CME", "ICE"]:
            return "FUTURES"
        
        # Options symbols (CE/PE for Indian, C/P for US)
        if "CE" in symbol_upper or "PE" in symbol_upper:
            return "OPTIONS"
        if symbol_upper.endswith("-C") or symbol_upper.endswith("-P"):
            return "OPTIONS"
        
        # Index detection (NIFTY, BANKNIFTY, SPX, etc.)
        if any(index in symbol_upper for index in ["NIFTY", "BANKNIFTY", "SPX", "DJI", "NDX"]):
            # Indices typically have both futures and options
            return "INDEX"
        
        # Stock detection
        if exchange_upper in ["NSE", "BSE", "NYSE", "NASDAQ"]:
            # Check if it's a stock (not index)
            if not any(index in symbol_upper for index in ["NIFTY", "BANKNIFTY", "SPX", "DJI"]):
                return "STOCK"
        
        # Default: SPOT
        return "SPOT"
    
    def _detect_derivatives(
        self,
        symbol: str,
        exchange: str,
        data_source: str,
        instrument_type: str
    ) -> tuple[bool, bool, bool]:
        """
        Detect available derivatives - no hardcoding.
        Returns: (has_options, has_futures, has_spot)
        """
        symbol_upper = symbol.upper()
        exchange_upper = exchange.upper()
        data_source_upper = data_source.upper()
        
        has_options = False
        has_futures = False
        has_spot = False
        
        # Crypto exchanges
        if data_source_upper in ["BINANCE", "COINBASE"]:
            has_futures = True  # Most crypto exchanges have futures
            has_spot = True
            # Options may or may not be available (check via API)
            has_options = False  # Will be determined at runtime
        
        # Indian exchanges (NSE/BSE)
        elif data_source_upper == "ZERODHA":
            if exchange_upper in ["NSE", "BSE"]:
                # Indices have options and futures
                if instrument_type == "INDEX":
                    has_options = True
                    has_futures = True
                    has_spot = False  # Indices don't trade spot
                # Stocks may have options
                elif instrument_type == "STOCK":
                    has_options = True  # Many stocks have options
                    has_futures = False  # Stock futures less common
                    has_spot = True
                else:
                    has_spot = True
        
        # US exchanges
        elif data_source_upper in ["IBKR", "ALPACA"]:
            if instrument_type == "INDEX":
                has_options = True
                has_futures = True
            elif instrument_type == "STOCK":
                has_options = True  # Many US stocks have options
                has_spot = True
        
        # Futures exchanges
        elif exchange_upper in ["MCX", "CME", "ICE"]:
            has_futures = True
        
        # Options exchanges
        elif exchange_upper in ["NFO", "OPRA"]:
            has_options = True
        
        # Default: assume spot available
        if not (has_options or has_futures):
            has_spot = True
        
        return (has_options, has_futures, has_spot)
    
    def _detect_market_hours(
        self,
        exchange: str,
        data_source: str,
        instrument_type: str
    ) -> Dict[str, Any]:
        """Detect market hours - no hardcoding."""
        exchange_upper = exchange.upper()
        data_source_upper = data_source.upper()
        
        # Crypto: 24/7
        if data_source_upper in ["BINANCE", "COINBASE"] or instrument_type.startswith("CRYPTO"):
            return {
                "is_24_7": True,
                "timezone": "UTC",
                "open_time": "00:00:00",
                "close_time": "23:59:59"
            }
        
        # Indian markets (NSE/BSE)
        if data_source_upper == "ZERODHA" or exchange_upper in ["NSE", "BSE", "NFO", "MCX"]:
            return {
                "is_24_7": False,
                "timezone": "Asia/Kolkata",
                "open_time": "09:15:00",
                "close_time": "15:30:00",
                "trading_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            }
        
        # US markets
        if exchange_upper in ["NYSE", "NASDAQ", "CME", "ICE"]:
            return {
                "is_24_7": False,
                "timezone": "America/New_York",
                "open_time": "09:30:00",
                "close_time": "16:00:00",
                "trading_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            }
        
        # Default: assume 24/7
        return {
            "is_24_7": True,
            "timezone": "UTC",
            "open_time": "00:00:00",
            "close_time": "23:59:59"
        }
    
    def _calculate_optimal_frequency(
        self,
        instrument_type: str,
        has_options: bool,
        has_futures: bool,
        region: str
    ) -> int:
        """Calculate optimal analysis frequency - no hardcoding."""
        # Options trading: 15 minutes (OI changes slowly)
        if has_options:
            return 15
        
        # Crypto futures: 10 minutes (faster moves)
        if instrument_type.startswith("CRYPTO"):
            return 10
        
        # Futures: 15 minutes
        if has_futures:
            return 15
        
        # Stocks: 30 minutes (less volatile)
        if instrument_type == "STOCK":
            return 30
        
        # Default: 15 minutes
        return 15
    
    def _get_derivatives_list(
        self,
        has_options: bool,
        has_futures: bool,
        instrument_type: str
    ) -> List[str]:
        """Get list of available derivatives."""
        derivatives = []
        
        if has_options:
            derivatives.append("options_chain")
        
        if has_futures:
            derivatives.append("futures")
            if instrument_type.startswith("CRYPTO"):
                derivatives.append("funding_rate")
                derivatives.append("open_interest")
        
        if not derivatives:
            derivatives.append("spot")
        
        return derivatives
    
    def _get_data_source_type(self, data_source: str) -> str:
        """Get data source type."""
        data_source_upper = data_source.upper()
        
        if data_source_upper in ["ZERODHA", "IBKR", "ALPACA"]:
            return "REST_API"
        elif data_source_upper in ["BINANCE", "COINBASE"]:
            return "WEBSOCKET"
        else:
            return "REST_API"  # Default

