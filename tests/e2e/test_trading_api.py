"""Tests for Trading API endpoints."""

import pytest
from datetime import datetime
from tests.e2e.utils.test_helpers import validate_api_response, create_test_signal


@pytest.mark.asyncio
class TestTradingAPI:
    """Test suite for trading API endpoints."""
    
    async def test_get_trading_signals(self, async_api_client):
        """Test GET /api/trading/signals endpoint."""
        response = await async_api_client.get("/api/trading/signals")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list) or isinstance(data, dict)
        # Signals should be a list or dict with signals key
    
    async def test_get_active_positions(self, async_api_client):
        """Test GET /api/trading/positions endpoint."""
        response = await async_api_client.get("/api/trading/positions")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list) or isinstance(data, dict)
        # Positions should be a list or dict with positions key
    
    async def test_get_trading_stats(self, async_api_client):
        """Test GET /api/trading/stats endpoint."""
        response = await async_api_client.get("/api/trading/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        # Stats should contain trading statistics
    
    async def test_run_trading_cycle(self, async_api_client):
        """Test POST /api/trading/cycle endpoint."""
        response = await async_api_client.post("/api/trading/cycle")
        assert response.status_code == 200
        
        data = response.json()
        is_valid, errors = validate_api_response(
            data,
            required_fields=["success"]
        )
        assert is_valid, f"Response validation failed: {errors}"
        
        # Should return success status
        assert data["success"] in [True, False]
    
    async def test_execute_signal_invalid_id(self, async_api_client):
        """Test executing signal with invalid ID."""
        invalid_signal_id = "invalid_signal_12345"
        response = await async_api_client.post(f"/api/trading/execute/{invalid_signal_id}")
        
        # May return 200 with error message, or 400/404
        assert response.status_code in [200, 400, 404]
        data = response.json()
        # If 200, should indicate error
        if response.status_code == 200:
            assert "error" in data or data.get("success") is False
    
    async def test_check_signal_conditions_invalid_id(self, async_api_client):
        """Test checking conditions for invalid signal ID."""
        invalid_signal_id = "invalid_signal_12345"
        response = await async_api_client.get(f"/api/trading/conditions/{invalid_signal_id}")
        
        # May return 200 with error message, or 400/404
        assert response.status_code in [200, 400, 404]
        data = response.json()
        # If 200, should indicate error
        if response.status_code == 200:
            assert "error" in data or data.get("success") is False
    
    async def test_trading_dashboard_endpoint(self, async_api_client):
        """Test GET /api/trading/dashboard endpoint."""
        response = await async_api_client.get("/api/trading/dashboard")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        # Dashboard should contain trading information
    
    @pytest.mark.slow
    async def test_complete_trading_workflow(self, async_api_client):
        """Test complete trading workflow: cycle → signals → execution."""
        # Step 1: Run trading cycle
        cycle_response = await async_api_client.post("/api/trading/cycle")
        assert cycle_response.status_code == 200
        
        # Step 2: Get signals
        signals_response = await async_api_client.get("/api/trading/signals")
        assert signals_response.status_code == 200
        
        signals_data = signals_response.json()
        signals = signals_data if isinstance(signals_data, list) else signals_data.get("signals", [])
        
        # Step 3: If signals exist, try to check conditions
        if signals and len(signals) > 0:
            signal_id = signals[0].get("id")
            if signal_id:
                conditions_response = await async_api_client.get(f"/api/trading/conditions/{signal_id}")
                assert conditions_response.status_code == 200
                
                conditions_data = conditions_response.json()
                assert "conditions_met" in conditions_data or "can_execute" in conditions_data


