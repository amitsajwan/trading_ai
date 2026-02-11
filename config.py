"""Configuration module for market data system.

Provides configuration based on environment variables.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """System configuration."""
    instrument_symbol: str = "BANKNIFTY26FEBFUT"
    instrument_key: str = "BANKNIFTY26FEBFUT"
    instrument_trading_symbol: str = "BANKNIFTY26FEBFUT"
    instrument_exchange: str = "NFO"
    exchange: str = "NFO"
    mode: str = "live"  # live, historical, paper
    
    def get_redis_config(self):
        """Get Redis configuration from environment."""
        return {
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", "6379")),
            "db": 0,
            "decode_responses": True
        }
    
    @property
    def redis_price_key(self):
        """Get Redis price key for this instrument."""
        return f"price:{self.instrument_key}"
    

def get_config() -> Config:
    """Get system configuration from environment variables.
    
    Returns:
        Config object with instrument and system settings
    """
    # Get from environment or use defaults
    instrument_symbol = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY26FEBFUT")
    instrument_key = os.getenv("INSTRUMENT_KEY", instrument_symbol)
    instrument_trading_symbol = os.getenv("INSTRUMENT_TRADING_SYMBOL", instrument_symbol)
    instrument_exchange = os.getenv("INSTRUMENT_EXCHANGE", "NFO")
    exchange = os.getenv("EXCHANGE", instrument_exchange)
    mode = os.getenv("MODE", "live")
    
    return Config(
        instrument_symbol=instrument_symbol,
        instrument_key=instrument_key,
        instrument_trading_symbol=instrument_trading_symbol,
        instrument_exchange=instrument_exchange,
        exchange=exchange,
        mode=mode
    )


if __name__ == "__main__":
    config = get_config()
    print(f"Configuration loaded:")
    print(f"  Instrument: {config.instrument_symbol}")
    print(f"  Key: {config.instrument_key}")
    print(f"  Exchange: {config.exchange}")
    print(f"  Mode: {config.mode}")
