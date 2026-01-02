"""Tests for configuration management."""

import pytest
import os
from config.settings import TradingConfig


def test_config_from_env():
    """Test loading configuration from environment."""
    # Set some test env vars
    os.environ["KITE_API_KEY"] = "test_key"
    os.environ["KITE_API_SECRET"] = "test_secret"
    os.environ["MAX_POSITION_SIZE_PCT"] = "5.0"
    
    config = TradingConfig.from_env()
    
    assert config.kite_api_key == "test_key"
    assert config.kite_api_secret == "test_secret"
    assert config.max_position_size_pct == 5.0


def test_config_defaults():
    """Test configuration defaults."""
    config = TradingConfig()
    
    assert config.max_position_size_pct == 5.0
    assert config.max_leverage == 2.0
    assert config.max_concurrent_trades == 3
    assert config.paper_trading_mode == True

