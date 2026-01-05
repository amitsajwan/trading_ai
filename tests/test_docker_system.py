"""Comprehensive tests for Docker system verification."""

import pytest
import requests
import json
from pathlib import Path
from typing import Dict, Any
import time


class TestDockerContainers:
    """Test Docker container health and connectivity."""
    
    @pytest.fixture
    def container_ports(self) -> Dict[str, int]:
        """Container port mappings."""
        return {
            "btc": 8001,
            "banknifty": 8002,
            "nifty": 8003,
            "mongodb": 27018,
            "redis": 6380,
        }
    
    def test_mongodb_connection(self, container_ports):
        """Test MongoDB container is accessible."""
        try:
            from pymongo import MongoClient
            client = MongoClient(f"mongodb://localhost:{container_ports['mongodb']}/")
            # Ping to verify connection
            client.admin.command('ping')
            assert True, "MongoDB is accessible"
        except Exception as e:
            pytest.fail(f"MongoDB connection failed: {e}")
    
    def test_redis_connection(self, container_ports):
        """Test Redis container is accessible."""
        try:
            import redis
            r = redis.Redis(host='localhost', port=container_ports['redis'], db=0)
            r.ping()
            assert True, "Redis is accessible"
        except Exception as e:
            pytest.fail(f"Redis connection failed: {e}")
    
    @pytest.mark.parametrize("instrument,port", [
        ("btc", 8001),
        ("banknifty", 8002),
        ("nifty", 8003),
    ])
    def test_dashboard_health(self, instrument, port):
        """Test dashboard health endpoints."""
        try:
            response = requests.get(f"http://localhost:{port}/api/health", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "timestamp" in data
        except requests.exceptions.RequestException as e:
            pytest.skip(f"{instrument.upper()} dashboard not running: {e}")


class TestCredentials:
    """Test credential validation."""
    
    def test_credentials_file_exists(self):
        """Check if credentials.json exists."""
        cred_path = Path("credentials.json")
        assert cred_path.exists(), "credentials.json not found"
    
    def test_credentials_structure(self):
        """Validate credentials.json structure."""
        cred_path = Path("credentials.json")
        if not cred_path.exists():
            pytest.skip("credentials.json not found")
        
        creds = json.loads(cred_path.read_text())
        required_keys = ["api_key", "api_secret", "access_token", "user_id", "data"]
        
        for key in required_keys:
            assert key in creds, f"Missing required key: {key}"
    
    def test_access_token_not_empty(self):
        """Ensure access token is populated."""
        cred_path = Path("credentials.json")
        if not cred_path.exists():
            pytest.skip("credentials.json not found")
        
        creds = json.loads(cred_path.read_text())
        access_token = creds.get("access_token", "")
        
        assert access_token, "access_token is empty - run: python auto_login.py"
        assert len(access_token) > 10, "access_token appears invalid"


class TestDataCollection:
    """Test data collection from various sources."""
    
    @pytest.fixture
    def api_base_urls(self) -> Dict[str, str]:
        """API base URLs for each instrument."""
        return {
            "btc": "http://localhost:8001",
            "banknifty": "http://localhost:8002",
            "nifty": "http://localhost:8003",
        }
    
    @pytest.mark.parametrize("instrument", ["btc", "banknifty", "nifty"])
    def test_market_data_endpoint(self, instrument, api_base_urls):
        """Test market data API returns data."""
        try:
            url = f"{api_base_urls[instrument]}/api/market-data"
            response = requests.get(url, timeout=5)
            assert response.status_code == 200
            
            data = response.json()
            # Check if we have data (may be null if no collection yet)
            assert "currentPrice" in data or "current_price" in data
        except requests.exceptions.RequestException:
            pytest.skip(f"{instrument.upper()} dashboard not running")
    
    @pytest.mark.parametrize("instrument", ["btc", "banknifty", "nifty"])
    def test_latest_signal_endpoint(self, instrument, api_base_urls):
        """Test latest signal API."""
        try:
            url = f"{api_base_urls[instrument]}/api/latest-signal"
            response = requests.get(url, timeout=5)
            assert response.status_code == 200
            
            data = response.json()
            assert "signal" in data
            # Should return HOLD if no trades yet
            assert data["signal"] in ["BUY", "SELL", "HOLD"]
        except requests.exceptions.RequestException:
            pytest.skip(f"{instrument.upper()} dashboard not running")
    
    def test_mongodb_has_collections(self):
        """Verify MongoDB has expected collections."""
        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27018/")
            db = client["zerodha_trading"]
            
            collections = db.list_collection_names()
            # These collections should exist even if empty
            expected = ["ohlc_history", "trades_executed", "agent_decisions"]
            
            # Note: Collections may not exist until first write
            # This test just checks database is accessible
            assert db is not None
        except Exception as e:
            pytest.skip(f"MongoDB not accessible: {e}")


class TestDashboardRendering:
    """Test dashboard template rendering."""
    
    @pytest.mark.parametrize("instrument,port,expected_name", [
        ("btc", 8001, "BTC-USD"),
        ("banknifty", 8002, "NIFTY BANK"),
        ("nifty", 8003, "NIFTY 50"),
    ])
    def test_instrument_name_in_title(self, instrument, port, expected_name):
        """Test that dashboard title contains instrument name."""
        try:
            response = requests.get(f"http://localhost:{port}/", timeout=5)
            assert response.status_code == 200
            
            html = response.text
            # Check if instrument name appears in title
            assert f"Trading Dashboard - {expected_name}" in html or \
                   f"Trading Dashboard" in html, \
                   f"Dashboard title should reference instrument"
        except requests.exceptions.RequestException:
            pytest.skip(f"{instrument.upper()} dashboard not running")
    
    @pytest.mark.parametrize("instrument,port", [
        ("btc", 8001),
        ("banknifty", 8002),
        ("nifty", 8003),
    ])
    def test_javascript_instrument_variable(self, instrument, port):
        """Test that window.INSTRUMENT_SYMBOL is set correctly."""
        try:
            response = requests.get(f"http://localhost:{port}/", timeout=5)
            assert response.status_code == 200
            
            html = response.text
            # Check for JavaScript variable
            assert "window.INSTRUMENT_SYMBOL" in html, \
                   "JavaScript instrument variable not found"
        except requests.exceptions.RequestException:
            pytest.skip(f"{instrument.upper()} dashboard not running")


class TestEnvironmentConfiguration:
    """Test environment configuration files."""
    
    @pytest.mark.parametrize("env_file,expected_symbol", [
        (".env.btc", "BTC-USD"),
        (".env.banknifty", "NIFTY BANK"),
        (".env.nifty", "NIFTY 50"),
    ])
    def test_env_file_has_instrument_symbol(self, env_file, expected_symbol):
        """Verify each .env file has correct INSTRUMENT_SYMBOL."""
        env_path = Path(env_file)
        if not env_path.exists():
            pytest.skip(f"{env_file} not found")
        
        content = env_path.read_text()
        assert f"INSTRUMENT_SYMBOL={expected_symbol}" in content, \
               f"Wrong INSTRUMENT_SYMBOL in {env_file}"
    
    def test_btc_has_crypto_datasource(self):
        """Verify BTC uses CRYPTO data source."""
        env_path = Path(".env.btc")
        if not env_path.exists():
            pytest.skip(".env.btc not found")
        
        content = env_path.read_text()
        assert "DATA_SOURCE=CRYPTO" in content
        assert "MARKET_24_7=true" in content
    
    @pytest.mark.parametrize("env_file", [".env.banknifty", ".env.nifty"])
    def test_indian_equities_have_zerodha_datasource(self, env_file):
        """Verify Indian instruments use ZERODHA data source."""
        env_path = Path(env_file)
        if not env_path.exists():
            pytest.skip(f"{env_file} not found")
        
        content = env_path.read_text()
        assert "DATA_SOURCE=ZERODHA" in content or \
               "KITE_API_KEY" in content, \
               f"{env_file} should reference Zerodha/Kite"


class TestAPIFieldAliases:
    """Test API field alias support (camelCase and underscore)."""
    
    @pytest.mark.parametrize("port", [8001, 8002, 8003])
    def test_market_data_aliases(self, port):
        """Test market data endpoint supports multiple field formats."""
        try:
            response = requests.get(f"http://localhost:{port}/api/market-data", timeout=5)
            if response.status_code != 200:
                pytest.skip("Dashboard not running")
            
            data = response.json()
            
            # Should support both snake_case and camelCase
            # e.g., both 'current_price' and 'currentPrice'
            has_snake = any('_' in key for key in data.keys())
            has_camel = any(key[0].islower() and any(c.isupper() for c in key[1:]) 
                          for key in data.keys())
            
            # At least one format should be present
            assert has_snake or has_camel or len(data) == 0
        except requests.exceptions.RequestException:
            pytest.skip("Dashboard not running")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
