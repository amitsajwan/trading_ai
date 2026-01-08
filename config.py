"""
Central configuration for the trading system.
All components should use this for configuration instead of hardcoded values.
"""

import os
from typing import Dict, Any


class TradingConfig:
    """Central configuration class for the trading system."""

    def __init__(self):
        # Database
        self.mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/zerodha_trading")
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))

        # Trading instrument (configurable)
        self.instrument_symbol = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY")
        self.instrument_trading_symbol = os.getenv("INSTRUMENT_TRADING_SYMBOL", "")
        self.instrument_exchange = os.getenv("INSTRUMENT_EXCHANGE", "NSE")

        # Kite API
        self.kite_api_key = os.getenv("KITE_API_KEY", "")
        self.kite_api_secret = os.getenv("KITE_API_SECRET", "")

        # LLM API Keys
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.ai21_api_key = os.getenv("AI21_API_KEY", "")
        self.cohere_api_key = os.getenv("COHERE_API_KEY", "")

        # Trading mode
        self.paper_trading = os.getenv("PAPER_TRADING_MODE", "true").lower() == "true"
        self.debug_output = os.getenv("DEBUG_AGENT_OUTPUT", "true").lower() == "true"

        # Service ports
        self.market_data_port = int(os.getenv("MARKET_DATA_PORT", "8004"))
        self.news_port = int(os.getenv("NEWS_PORT", "8005"))
        self.engine_port = int(os.getenv("ENGINE_PORT", "8006"))
        self.dashboard_port = int(os.getenv("DASHBOARD_PORT", "8888"))

    @property
    def instrument_key(self) -> str:
        """Get the normalized instrument key for Redis/MongoDB."""
        return self.instrument_symbol.upper().replace(" ", "")

    @property
    def redis_price_key(self) -> str:
        """Get the Redis price key for this instrument."""
        return f"price:{self.instrument_key}"

    @property
    def redis_volume_key(self) -> str:
        """Get the Redis volume key for this instrument."""
        return f"volume:{self.instrument_key}"

    def get_redis_config(self) -> Dict[str, Any]:
        """Get Redis configuration."""
        return {
            "host": self.redis_host,
            "port": self.redis_port,
            "db": 0,
            "decode_responses": True
        }

    def get_mongo_config(self) -> Dict[str, Any]:
        """Get MongoDB configuration."""
        return {
            "uri": self.mongodb_uri,
            "database": "zerodha_trading"
        }


# Global config instance
config = TradingConfig()


def get_config() -> TradingConfig:
    """Get the global configuration instance."""
    return config


def reload_config() -> TradingConfig:
    """Reload configuration from environment variables."""
    global config
    config = TradingConfig()
    return config