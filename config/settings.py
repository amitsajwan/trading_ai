"""Configuration management for the trading system."""

import os
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class TradingConfig(BaseModel):
    """Trading system configuration."""
    
    # API Keys
    kite_api_key: str = Field(default="")
    kite_api_secret: str = Field(default="")
    openai_api_key: Optional[str] = Field(default=None)
    groq_api_key: Optional[str] = Field(default=None)
    azure_openai_endpoint: Optional[str] = Field(default=None)
    azure_openai_api_key: Optional[str] = Field(default=None)
    azure_openai_api_version: str = Field(default="2024-02-15-preview")
    huggingface_api_key: Optional[str] = Field(default=None)
    together_api_key: Optional[str] = Field(default=None)
    google_api_key: Optional[str] = Field(default=None)
    openrouter_api_key: Optional[str] = Field(default=None)
    ollama_base_url: str = Field(default="http://localhost:11434")  # Local Ollama
    
    # Database Connections
    mongodb_uri: str = Field(default="mongodb://localhost:27017/")
    mongodb_db_name: str = Field(default="zerodha_trading")
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)
    
    # Trading Parameters
    max_position_size_pct: float = Field(default=5.0)  # Max 5% of account per trade
    max_leverage: float = Field(default=2.0)  # Max 1:2 leverage
    max_concurrent_trades: int = Field(default=3)
    daily_loss_limit_pct: float = Field(default=2.0)  # Max 2% daily loss
    order_timeout_seconds: int = Field(default=30)
    
    # Risk Management
    default_stop_loss_pct: float = Field(default=1.5)  # Default 1.5% stop loss
    default_take_profit_pct: float = Field(default=3.0)  # Default 3% take profit
    max_drawdown_pct: float = Field(default=15.0)  # Max 15% drawdown
    
    # Agent Configuration
    llm_provider: str = Field(default="groq")  # "groq", "openai", "azure", "ollama", "huggingface", "together", "gemini"
    llm_model: str = Field(default="llama-3.1-8b-instant")  # OPTIMIZED: Faster model (was llama-3.3-70b-versatile)
    llm_temperature: float = Field(default=0.3)  # Lower temperature for more deterministic outputs
    max_tokens: int = Field(default=2000)
    
    # Market Data - Instrument Configuration
    instrument_symbol: str = Field(default="NIFTY BANK")  # Trading symbol (e.g., NIFTY BANK, BTC-USD)
    instrument_name: str = Field(default="Bank Nifty")  # Display name (e.g., Bank Nifty, Bitcoin)
    instrument_exchange: str = Field(default="NSE")  # Exchange (NSE, CRYPTO, BINANCE, etc.)
    instrument_token: Optional[str] = Field(default=None)  # Optional: Direct token if known
    
    # Data Source Configuration
    data_source: str = Field(default="ZERODHA")  # ZERODHA, CRYPTO, BINANCE, etc.
    data_source_api_key: Optional[str] = Field(default=None)
    data_source_secret: Optional[str] = Field(default=None)
    
    # News Configuration
    news_query: str = Field(default="Bank Nifty OR banking sector OR RBI")  # News API query
    news_keywords: str = Field(default="Bank Nifty,banking sector,RBI")  # Comma-separated keywords
    
    # Macro Data Configuration
    macro_data_enabled: bool = Field(default=True)  # Enable RBI/macro data (false for crypto)
    crypto_macro_indicators: Optional[str] = Field(default=None)  # Crypto-specific indicators
    
    # Market Hours
    market_open_time: str = Field(default="09:15:00")
    market_close_time: str = Field(default="15:30:00")
    market_24_7: bool = Field(default=False)  # true for crypto (24/7 trading)
    
    # Data Collection
    news_api_key: Optional[str] = Field(default=None)
    news_update_interval_minutes: int = Field(default=5)
    sentiment_update_interval_minutes: int = Field(default=10)
    
    # Monitoring
    enable_alerts: bool = Field(default=True)
    slack_webhook_url: Optional[str] = Field(default=None)
    email_alerts: Optional[str] = Field(default=None)
    
    # Paper Trading
    paper_trading_mode: bool = Field(default=True)  # Start in paper trading mode
    
    # Logging
    log_level: str = Field(default="INFO")
    log_file: Optional[str] = Field(default=None)
    
    @classmethod
    def from_env(cls) -> "TradingConfig":
        """Create configuration from environment variables."""
        return cls(
            # API Keys
            kite_api_key=os.getenv("KITE_API_KEY", ""),
            kite_api_secret=os.getenv("KITE_API_SECRET", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            groq_api_key=os.getenv("GROQ_API_KEY"),
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            huggingface_api_key=os.getenv("HUGGINGFACE_API_KEY"),
            together_api_key=os.getenv("TOGETHER_API_KEY"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            
            # Database
            mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017/"),
            mongodb_db_name=os.getenv("MONGODB_DB_NAME", "zerodha_trading"),
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_db=int(os.getenv("REDIS_DB", "0")),
            
            # Trading Parameters
            max_position_size_pct=float(os.getenv("MAX_POSITION_SIZE_PCT", "5.0")),
            max_leverage=float(os.getenv("MAX_LEVERAGE", "2.0")),
            max_concurrent_trades=int(os.getenv("MAX_CONCURRENT_TRADES", "3")),
            daily_loss_limit_pct=float(os.getenv("DAILY_LOSS_LIMIT_PCT", "2.0")),
            order_timeout_seconds=int(os.getenv("ORDER_TIMEOUT_SECONDS", "30")),
            
            # Risk Management
            default_stop_loss_pct=float(os.getenv("DEFAULT_STOP_LOSS_PCT", "1.5")),
            default_take_profit_pct=float(os.getenv("DEFAULT_TAKE_PROFIT_PCT", "3.0")),
            max_drawdown_pct=float(os.getenv("MAX_DRAWDOWN_PCT", "15.0")),
            
            # Agent Configuration
            llm_provider=os.getenv("LLM_PROVIDER", "groq"),
            llm_model=os.getenv("LLM_MODEL", "llama-3.1-8b-instant"),  # OPTIMIZED: Faster model
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("MAX_TOKENS", "2000")),
            
            # Market Data - Instrument Configuration
            instrument_symbol=os.getenv("INSTRUMENT_SYMBOL", "NIFTY BANK"),
            instrument_name=os.getenv("INSTRUMENT_NAME", "Bank Nifty"),
            instrument_exchange=os.getenv("INSTRUMENT_EXCHANGE", "NSE"),
            instrument_token=os.getenv("INSTRUMENT_TOKEN"),
            
            # Data Source Configuration
            data_source=os.getenv("DATA_SOURCE", "ZERODHA"),
            data_source_api_key=os.getenv("DATA_SOURCE_API_KEY"),
            data_source_secret=os.getenv("DATA_SOURCE_SECRET"),
            
            # News Configuration
            news_query=os.getenv("NEWS_QUERY", "Bank Nifty OR banking sector OR RBI"),
            news_keywords=os.getenv("NEWS_KEYWORDS", "Bank Nifty,banking sector,RBI"),
            
            # Macro Data Configuration
            macro_data_enabled=os.getenv("MACRO_DATA_ENABLED", "true").lower() == "true",
            crypto_macro_indicators=os.getenv("CRYPTO_MACRO_INDICATORS"),
            
            # Market Hours
            market_open_time=os.getenv("MARKET_OPEN_TIME", "09:15:00"),
            market_close_time=os.getenv("MARKET_CLOSE_TIME", "15:30:00"),
            market_24_7=os.getenv("MARKET_24_7", "false").lower() == "true",
            
            # Data Collection
            news_api_key=os.getenv("NEWS_API_KEY"),
            news_update_interval_minutes=int(os.getenv("NEWS_UPDATE_INTERVAL_MINUTES", "5")),
            sentiment_update_interval_minutes=int(os.getenv("SENTIMENT_UPDATE_INTERVAL_MINUTES", "10")),
            
            # Monitoring
            enable_alerts=os.getenv("ENABLE_ALERTS", "true").lower() == "true",
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
            email_alerts=os.getenv("EMAIL_ALERTS"),
            
            # Paper Trading
            paper_trading_mode=os.getenv("PAPER_TRADING_MODE", "true").lower() == "true",
            
            # Logging
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE"),
        )


# Global configuration instance
settings = TradingConfig.from_env()

