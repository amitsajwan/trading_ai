"""Data source factory - creates appropriate fetcher for any instrument/region/currency."""

import logging
from typing import Optional
from kiteconnect import KiteConnect
from engines.instrument_detector import InstrumentProfile
from data.derivatives_fetcher import DerivativesFetcher

logger = logging.getLogger(__name__)


class DataSourceFactory:
    """
    Factory to create appropriate data fetcher.
    Completely generic - no hardcoding of instruments, regions, currencies.
    """
    
    def __init__(self, kite: Optional[KiteConnect] = None):
        """
        Initialize factory.
        
        Args:
            kite: Optional KiteConnect instance (for Zerodha)
        """
        self.kite = kite
        self._fetcher_cache: dict[str, DerivativesFetcher] = {}
    
    def create_derivatives_fetcher(
        self, 
        profile: InstrumentProfile
    ) -> DerivativesFetcher:
        """
        Create appropriate fetcher based on instrument profile.
        No hardcoding - works for any instrument, region, currency.
        
        Args:
            profile: InstrumentProfile from InstrumentDetector
        
        Returns:
            Appropriate DerivativesFetcher implementation
        
        Raises:
            ValueError: If data source not supported
        """
        # Create cache key
        cache_key = f"{profile.data_source}:{profile.symbol}:{profile.exchange}"
        
        # Return cached fetcher if exists
        if cache_key in self._fetcher_cache:
            logger.debug(f"Returning cached fetcher for {cache_key}")
            return self._fetcher_cache[cache_key]
        
        # Create new fetcher based on data source
        data_source_upper = profile.data_source.upper()
        
        if data_source_upper == "ZERODHA":
            fetcher = self._create_zerodha_fetcher(profile)
        elif data_source_upper == "BINANCE":
            fetcher = self._create_binance_fetcher(profile)
        elif data_source_upper == "COINBASE":
            fetcher = self._create_coinbase_fetcher(profile)
        elif data_source_upper == "IBKR":
            fetcher = self._create_ibkr_fetcher(profile)
        elif data_source_upper == "ALPACA":
            fetcher = self._create_alpaca_fetcher(profile)
        else:
            raise ValueError(
                f"Unsupported data source: {profile.data_source}. "
                f"Supported: ZERODHA, BINANCE, COINBASE, IBKR, ALPACA"
            )
        
        # Cache fetcher
        self._fetcher_cache[cache_key] = fetcher
        
        logger.info(
            f"Created {profile.data_source} fetcher for {profile.symbol} "
            f"({profile.currency}, {profile.region})"
        )
        
        return fetcher
    
    def _create_zerodha_fetcher(self, profile: InstrumentProfile) -> DerivativesFetcher:
        """Create Zerodha fetcher - works for any Indian instrument."""
        if not self.kite:
            raise ValueError("KiteConnect instance required for Zerodha data source")
        
        # Import here to avoid circular dependencies
        from data.zerodha_options_fetcher import ZerodhaOptionsChainFetcher
        from data.zerodha_futures_fetcher import ZerodhaFuturesFetcher
        
        if profile.has_options:
            return ZerodhaOptionsChainFetcher(
                kite=self.kite,
                instrument_symbol=profile.symbol,
                exchange=profile.exchange,
                currency=profile.currency
            )
        elif profile.has_futures:
            return ZerodhaFuturesFetcher(
                kite=self.kite,
                instrument_symbol=profile.symbol,
                exchange=profile.exchange,
                currency=profile.currency
            )
        else:
            # Spot only - use options fetcher as base (it can handle spot)
            return ZerodhaOptionsChainFetcher(
                kite=self.kite,
                instrument_symbol=profile.symbol,
                exchange=profile.exchange,
                currency=profile.currency
            )
    
    def _create_binance_fetcher(self, profile: InstrumentProfile) -> DerivativesFetcher:
        """Create Binance fetcher - works for any crypto instrument."""
        from data.binance_futures_fetcher import BinanceFuturesFetcher
        from data.binance_spot_fetcher import BinanceSpotFetcher
        
        binance_symbol = self._convert_to_binance_symbol(profile.symbol)
        
        # Prefer futures if available (more data)
        if profile.has_futures:
            return BinanceFuturesFetcher(
                symbol=binance_symbol,
                currency=profile.currency
            )
        else:
            return BinanceSpotFetcher(
                symbol=binance_symbol,
                currency=profile.currency
            )
    
    def _create_coinbase_fetcher(self, profile: InstrumentProfile) -> DerivativesFetcher:
        """Create Coinbase fetcher - works for any crypto instrument."""
        # Similar to Binance, implement when needed
        raise NotImplementedError("Coinbase fetcher not yet implemented")
    
    def _create_ibkr_fetcher(self, profile: InstrumentProfile) -> DerivativesFetcher:
        """Create Interactive Brokers fetcher - works for US/international instruments."""
        # Implement when needed
        raise NotImplementedError("IBKR fetcher not yet implemented")
    
    def _create_alpaca_fetcher(self, profile: InstrumentProfile) -> DerivativesFetcher:
        """Create Alpaca fetcher - works for US stocks."""
        # Implement when needed
        raise NotImplementedError("Alpaca fetcher not yet implemented")
    
    def _convert_to_binance_symbol(self, symbol: str) -> str:
        """
        Convert symbol to Binance format.
        Generic conversion - works for any crypto pair.
        """
        symbol_upper = symbol.upper().replace("-", "").replace("_", "")
        
        # Common mappings
        symbol_map = {
            "BTCUSD": "BTCUSDT",
            "BTC-USD": "BTCUSDT",
            "ETHUSD": "ETHUSDT",
            "ETH-USD": "ETHUSDT",
        }
        
        if symbol_upper in symbol_map:
            return symbol_map[symbol_upper]
        
        # If ends with USD, add T
        if symbol_upper.endswith("USD"):
            return symbol_upper + "T"
        
        # If just symbol (BTC, ETH), add USDT
        if len(symbol_upper) <= 5 and symbol_upper.isalpha():
            return symbol_upper + "USDT"
        
        # Return as-is (might already be correct)
        return symbol_upper
    
    def clear_cache(self):
        """Clear fetcher cache."""
        self._fetcher_cache.clear()
        logger.debug("Cleared fetcher cache")

