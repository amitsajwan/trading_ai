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
    cohere_api_key: Optional[str] = Field(default=None)
    ai21_api_key: Optional[str] = Field(default=None)
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
    llm_model: str = Field(default="llama-3.3-70b-versatile")  # Model name varies by provider
    llm_temperature: float = Field(default=0.3)  # Lower temperature for more deterministic outputs
    max_tokens: int = Field(default=4000)  # Increased for structured JSON outputs (raised to 4000)
    
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
    
    # RSS Feed Configuration
    rss_feeds_enabled: bool = Field(default=True)  # Enable RSS feeds
    rss_moneycontrol_latest: str = Field(default="https://www.moneycontrol.com/rss/latestnews.xml")
    rss_moneycontrol_economy: str = Field(default="https://www.moneycontrol.com/rss/economy.xml")
    rss_moneycontrol_markets: str = Field(default="https://www.moneycontrol.com/rss/markets.xml")
    rss_moneycontrol_business: str = Field(default="https://www.moneycontrol.com/rss/businessnews.xml")
    rss_keywords: str = Field(default="Nifty,Bank Nifty,RBI,FII,DII,volatility,OI,options,expire,bank,sensex,index,market,stock,bse,nse,rupee,dollar,economy,growth,inflation,policy,rate,hike,cut,gdp,monsoon,export,import,fiscal,budget")  # RSS filter keywords
    rss_update_interval_seconds: int = Field(default=60)  # Poll RSS every 60 seconds
    
    # Macro Data Configuration
    macro_data_enabled: bool = Field(default=True)  # Enable RBI/macro data (false for crypto)
    crypto_macro_indicators: Optional[str] = Field(default=None)  # Crypto-specific indicators
    
    # Market Hours
    market_open_time: str = Field(default="09:15:00")
    market_close_time: str = Field(default="15:30:00")
    market_24_7: bool = Field(default=False)  # true for crypto (24/7 trading)
    
    # Data Collection
    finnhub_api_key: Optional[str] = Field(default=None)
    news_api_provider: str = Field(default="newsapi")  # "newsapi", "finnhub"
    news_update_interval_minutes: int = Field(default=5)
    sentiment_update_interval_minutes: int = Field(default=10)
    
    # Trading Loop Configuration
    trading_loop_interval_seconds: int = Field(default=900)  # 15 minutes - agent discussions inform trading decisions
    
    # Monitoring
    enable_alerts: bool = Field(default=True)
    slack_webhook_url: Optional[str] = Field(default=None)
    email_alerts: Optional[str] = Field(default=None)
    
    # Paper Trading
    paper_trading_mode: bool = Field(default=True)  # Start in paper trading mode
    
    # Feature Flags for Staged Rollout
    enable_json_validation: bool = Field(default=True)  # Enable JSON completeness validation
    enable_circuit_breaker: bool = Field(default=True)  # Enable circuit breaker for providers/endpoints
    enable_provider_health_checks: bool = Field(default=True)  # Enable background provider health checks
    enable_token_quota_enforcement: bool = Field(default=True)  # Enable token quota tracking and alerts
    enable_field_aliasing: bool = Field(default=True)  # Enable camelCase field aliases in API responses
    enable_schema_validation: bool = Field(default=False)  # Enable MongoDB schema validation (moderate mode)
    llm_health_check_interval: int = Field(default=60)  # Provider health check interval (seconds)
    
    # Logging
    log_level: str = Field(default="INFO")
    log_file: Optional[str] = Field(default=None)
    
    # Feature Flags (for gradual rollout)
    enable_json_validation_retry: bool = Field(default=True)  # Retry incomplete JSON responses
    enable_circuit_breaker: bool = Field(default=True)  # Circuit breaker for providers/endpoints
    enable_health_monitoring: bool = Field(default=True)  # Background health checks for LLM providers
    enable_token_quota_enforcement: bool = Field(default=False)  # Block requests when quota exceeded (default off)
    
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
            cohere_api_key=os.getenv("COHERE_API_KEY"),
            ai21_api_key=os.getenv("AI21_API_KEY"),
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
            llm_model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("MAX_TOKENS", "4000")),
            
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
            
            # RSS Feed Configuration
            rss_feeds_enabled=os.getenv("RSS_FEEDS_ENABLED", "true").lower() == "true",
            rss_moneycontrol_latest=os.getenv("RSS_MONEYCONTROL_LATEST", "https://www.moneycontrol.com/rss/latestnews.xml"),
            rss_moneycontrol_economy=os.getenv("RSS_MONEYCONTROL_ECONOMY", "https://www.moneycontrol.com/rss/economy.xml"),
            rss_moneycontrol_markets=os.getenv("RSS_MONEYCONTROL_MARKETS", "https://www.moneycontrol.com/rss/markets.xml"),
            rss_moneycontrol_business=os.getenv("RSS_MONEYCONTROL_BUSINESS", "https://www.moneycontrol.com/rss/businessnews.xml"),
            rss_keywords=os.getenv("RSS_KEYWORDS", "Nifty,Bank Nifty,RBI,FII,DII,volatility,OI,options,expire,bank,sensex,index,market,stock,bse,nse,rupee,dollar,economy,growth,inflation,policy,rate,hike,cut,gdp,monsoon,export,import,fiscal,budget"),
            rss_update_interval_seconds=int(os.getenv("RSS_UPDATE_INTERVAL_SECONDS", "60")),
            
            # Macro Data Configuration
            macro_data_enabled=os.getenv("MACRO_DATA_ENABLED", "true").lower() == "true",
            crypto_macro_indicators=os.getenv("CRYPTO_MACRO_INDICATORS"),
            
            # Market Hours
            market_open_time=os.getenv("MARKET_OPEN_TIME", "09:15:00"),
            market_close_time=os.getenv("MARKET_CLOSE_TIME", "15:30:00"),
            market_24_7=os.getenv("MARKET_24_7", "false").lower() == "true",
            
            # Data Collection
            finnhub_api_key=os.getenv("FINNHUB_API_KEY"),
            news_api_provider=os.getenv("NEWS_API_PROVIDER", "newsapi"),
            news_update_interval_minutes=int(os.getenv("NEWS_UPDATE_INTERVAL_MINUTES", "5")),
            sentiment_update_interval_minutes=int(os.getenv("SENTIMENT_UPDATE_INTERVAL_MINUTES", "10")),
            
            # Trading Loop Configuration
            trading_loop_interval_seconds=int(os.getenv("TRADING_LOOP_INTERVAL_SECONDS", "900")),  # Default: 15 minutes
            
            # Monitoring
            enable_alerts=os.getenv("ENABLE_ALERTS", "true").lower() == "true",
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
            email_alerts=os.getenv("EMAIL_ALERTS"),
            
            # Paper Trading
            paper_trading_mode=os.getenv("PAPER_TRADING_MODE", "true").lower() == "true",
            
            # Logging
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE"),
            
            # Feature Flags
            enable_json_validation_retry=os.getenv("ENABLE_JSON_VALIDATION_RETRY", "true").lower() == "true",
            enable_circuit_breaker=os.getenv("ENABLE_CIRCUIT_BREAKER", "true").lower() == "true",
            enable_health_monitoring=os.getenv("ENABLE_HEALTH_MONITORING", "true").lower() == "true",
            enable_token_quota_enforcement=os.getenv("ENABLE_TOKEN_QUOTA_ENFORCEMENT", "false").lower() == "true",
        )


# Global configuration instance
settings = TradingConfig.from_env()


