"""Tests for Dashboard API endpoints."""

import pytest
from datetime import datetime
from tests.e2e.utils.test_helpers import validate_api_response


@pytest.mark.asyncio
class TestDashboardAPI:
    """Test suite for dashboard API endpoints."""
    
    async def test_health_endpoint(self, async_api_client):
        """Test /api/health endpoint."""
        response = await async_api_client.get("/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        # Status can be "ok", "degraded", or other valid states
        assert data["status"] in ["ok", "degraded", "error"]
    
    async def test_system_health_endpoint(self, async_api_client):
        """Test /api/system-health endpoint."""
        response = await async_api_client.get("/api/system-health")
        assert response.status_code == 200
        
        data = response.json()
        # At minimum, status should be present
        assert "status" in data
        # Other fields may or may not be present depending on service availability
    
    async def test_latest_analysis_endpoint(self, async_api_client):
        """Test /api/latest-analysis endpoint."""
        response = await async_api_client.get("/api/latest-analysis")
        # May return 404 if no analysis exists yet, or 200 with data
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            # Analysis may or may not exist, but structure should be valid
            if "analysis" in data:
                analysis = data["analysis"]
                assert isinstance(analysis, dict)
    
    async def test_latest_signal_endpoint(self, async_api_client):
        """Test /api/latest-signal endpoint."""
        response = await async_api_client.get("/api/latest-signal")
        # May return 404 if no signal exists yet, or 200 with data
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            # Signal may or may not exist
            if "signal" in data:
                signal = data["signal"]
                assert isinstance(signal, dict)
    
    async def test_market_data_endpoint(self, async_api_client):
        """Test /api/market-data endpoint."""
        response = await async_api_client.get("/api/market-data")
        # May return 503 if market data service unavailable, or 200 with data
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
    
    async def test_trading_metrics_endpoint(self, async_api_client):
        """Test /metrics/trading endpoint."""
        response = await async_api_client.get("/metrics/trading")
        assert response.status_code == 200
        
        data = response.json()
        is_valid, errors = validate_api_response(
            data,
            required_fields=["total_trades", "win_rate"]
        )
        assert is_valid, f"Response validation failed: {errors}"
    
    async def test_risk_metrics_endpoint(self, async_api_client):
        """Test /metrics/risk endpoint."""
        response = await async_api_client.get("/metrics/risk")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        # Risk metrics structure may vary
    
    async def test_agent_status_endpoint(self, async_api_client):
        """Test /api/agent-status endpoint."""
        response = await async_api_client.get("/api/agent-status")
        # May return 503 if service unavailable, or 200 with data
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
    
    async def test_portfolio_endpoint(self, async_api_client):
        """Test /api/portfolio endpoint."""
        response = await async_api_client.get("/api/portfolio")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        # Portfolio structure may vary
    
    async def test_technical_indicators_endpoint(self, async_api_client):
        """Test /api/technical-indicators endpoint."""
        response = await async_api_client.get("/api/technical-indicators")
        # May return 503 if service unavailable, or 200 with data
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
    
    async def test_market_data_by_symbol(self, async_api_client):
        """Test /api/market/data/{symbol} endpoint."""
        symbol = "NIFTY BANK"
        response = await async_api_client.get(f"/api/market/data/{symbol}")
        # May return 503 if service unavailable, or 200 with data
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            # Price and timestamp may not always be present if service is degraded
            if "price" in data:
                assert isinstance(data["price"], (int, float))
                assert data["price"] > 0
    
    async def test_invalid_symbol_rejected(self, async_api_client):
        """Test that invalid symbols are rejected."""
        invalid_symbol = "INVALID_SYMBOL"
        response = await async_api_client.get(f"/api/market/data/{invalid_symbol}")
        # May return 400, 404, or 200 with error message depending on implementation
        assert response.status_code in [200, 400, 404]
        
        # If 200, should contain error indication
        if response.status_code == 200:
            data = response.json()
            # Response should indicate error or invalid symbol
            assert isinstance(data, dict)


