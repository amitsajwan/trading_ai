"""
Central configuration for the trading system.
All components should use this for configuration instead of hardcoded values.
"""

import os
import logging
import logging.config
from typing import Dict, Any


class TradingConfig:
    """Central configuration class for the trading system."""

    def __init__(self):
        # Database
        self.mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/zerodha_trading")
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))

        # Trading instrument (configurable)
        self.instrument_symbol = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY26FEBFUT")
        self.instrument_trading_symbol = os.getenv("INSTRUMENT_TRADING_SYMBOL", "")
        self.instrument_exchange = os.getenv("INSTRUMENT_EXCHANGE", "NFO")

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

        # Logging configuration
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_format = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        self.log_file = os.getenv("LOG_FILE", "logs/trading_system.log")
        self.enable_json_logging = os.getenv("ENABLE_JSON_LOGGING", "false").lower() == "true"

        # Performance monitoring
        self.enable_performance_monitoring = os.getenv("ENABLE_PERFORMANCE_MONITORING", "true").lower() == "true"
        self.performance_log_interval = int(os.getenv("PERFORMANCE_LOG_INTERVAL", "300"))  # 5 minutes

        # Error handling
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.retry_delay = float(os.getenv("RETRY_DELAY", "1.0"))

        # Rate limiting
        self.api_rate_limit = int(os.getenv("API_RATE_LIMIT", "100"))  # requests per minute
        self.llm_rate_limit = int(os.getenv("LLM_RATE_LIMIT", "10"))   # requests per minute

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

    def setup_logging(self):
        """Setup centralized logging configuration for the trading system with module-specific log files."""
        # Ensure main logs directory exists (guard against empty LOG_FILE)
        if not self.log_file:
            # Fallback to default logs path when LOG_FILE env is empty
            self.log_file = "logs/trading_system.log"
        # Determine directory to create (use 'logs' if dirname is empty)
        log_dir = os.path.dirname(self.log_file) or "logs"
        os.makedirs(log_dir, exist_ok=True)

        # Define all modules with their log directories
        modules = [
            'backtesting_module',
            'core_kernel',
            'dashboard',
            'data',
            'engine_module',
            'genai_module',
            'market_data',
            'monitoring',
            'news_module',
            'redis_ws_gateway',
            'risk_module',
            'services',
            'ui_shell',
            'user_module'
        ]

        # Ensure module log directories exist
        for module in modules:
            module_log_dir = os.path.join(module, 'logs')
            os.makedirs(module_log_dir, exist_ok=True)

        # Base logging configuration
        log_config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': self.log_format,
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                'json': {
                    'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
                    'datefmt': '%Y-%m-%dT%H:%M:%SZ'
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'formatter': 'standard' if not self.enable_json_logging else 'json',
                    'level': self.log_level,
                    'stream': 'ext://sys.stdout'
                },
                'console_utf8': {
                    'class': 'logging.StreamHandler',
                    'formatter': 'standard' if not self.enable_json_logging else 'json',
                    'level': self.log_level,
                    'stream': 'ext://sys.stdout'
                },
                'main_file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'formatter': 'standard' if not self.enable_json_logging else 'json',
                    'level': self.log_level,
                    'filename': self.log_file,
                    'maxBytes': 10 * 1024 * 1024,  # 10MB
                    'backupCount': 5
                }
            },
            'root': {
                'handlers': ['console', 'main_file'],
                'level': self.log_level,
            },
            'loggers': {}
        }

        # Add module-specific handlers and loggers
        for module in modules:
            module_log_file = os.path.join(module, 'logs', f'{module}.log')
            handler_name = f'{module}_file'

            # Add module-specific file handler
            log_config['handlers'][handler_name] = {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'standard' if not self.enable_json_logging else 'json',
                'level': self.log_level,
                'filename': module_log_file,
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 5
            }

            # Add module-specific logger
            log_config['loggers'][module] = {
                'handlers': ['console', handler_name],
                'level': self.log_level,
                'propagate': False
            }

        logging.config.dictConfig(log_config)
        logger = logging.getLogger(__name__)
        logger.info("Module-specific logging configuration applied")
        logger.info(f"Log level: {self.log_level}, JSON logging: {self.enable_json_logging}")
        logger.info(f"Created separate log files for {len(modules)} modules")

    def get_logger(self, name: str) -> logging.Logger:
        """Get a configured logger for the given module name."""
        return logging.getLogger(name)


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