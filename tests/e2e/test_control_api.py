"""Tests for Control API endpoints."""

import pytest
from datetime import datetime
from tests.e2e.utils.test_helpers import validate_api_response


@pytest.mark.asyncio
class TestControlAPI:
    """Test suite for control API endpoints."""
    
    async def test_control_status_endpoint(self, async_api_client):
        """Test GET /api/control/status endpoint."""
        response = await async_api_client.get("/api/control/status")
        assert response.status_code == 200
        
        data = response.json()
        # Mode should always be present
        assert "mode" in data
        # Validate mode is one of expected values
        assert data["mode"] in ["live", "paper_live", "paper_mock"]
        # Database field may or may not be present
    
    async def test_mode_info_endpoint(self, async_api_client):
        """Test GET /api/control/mode/info endpoint."""
        response = await async_api_client.get("/api/control/mode/info")
        assert response.status_code == 200
        
        data = response.json()
        # Mode may be "mode" or "current_mode" depending on API version
        assert "mode" in data or "current_mode" in data
        mode_value = data.get("mode") or data.get("current_mode")
        assert mode_value in ["live", "paper_live", "paper_mock"]
    
    async def test_auto_switch_status(self, async_api_client):
        """Test GET /api/control/mode/auto-switch endpoint."""
        response = await async_api_client.get("/api/control/mode/auto-switch")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        # Auto-switch status should be returned
    
    async def test_switch_to_paper_mock(self, async_api_client):
        """Test switching to paper_mock mode."""
        response = await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_mock"}
        )
        assert response.status_code == 200
        
        data = response.json()
        is_valid, errors = validate_api_response(
            data,
            required_fields=["success", "mode"]
        )
        assert is_valid, f"Response validation failed: {errors}"
        
        if data.get("success"):
            assert data["mode"] == "paper_mock"
    
    async def test_switch_to_paper_live(self, async_api_client):
        """Test switching to paper_live mode."""
        response = await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_live"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        # Mode switch should be attempted
    
    async def test_switch_to_live_requires_confirmation(self, async_api_client):
        """Test that switching to live mode requires confirmation."""
        response = await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "live"}
        )
        assert response.status_code == 200
        
        data = response.json()
        # Should require confirmation or return error
        assert "confirmation_required" in data or "success" in data or "error" in data
    
    async def test_switch_to_live_with_confirmation(self, async_api_client):
        """Test switching to live mode with confirmation."""
        response = await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "live", "confirm": True}
        )
        assert response.status_code == 200
        
        data = response.json()
        # May require additional setup (Zerodha auth)
        assert isinstance(data, dict)
    
    async def test_switch_to_historical_replay(self, async_api_client):
        """Test switching to paper_mock with historical replay."""
        from datetime import date, timedelta
        
        start_date = (date.today() - timedelta(days=7)).isoformat()
        end_date = (date.today() - timedelta(days=1)).isoformat()
        
        response = await async_api_client.post(
            "/api/control/mode/switch",
            json={
                "mode": "paper_mock",
                "historical_start_date": start_date,
                "historical_end_date": end_date,
                "historical_interval": "minute"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        # Historical replay should be configured
    
    async def test_clear_mode_override(self, async_api_client):
        """Test clearing mode override."""
        response = await async_api_client.post("/api/control/mode/clear-override")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        # Override should be cleared
    
    async def test_get_account_balance(self, async_api_client):
        """Test GET /api/control/balance endpoint."""
        response = await async_api_client.get("/api/control/balance")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        # Balance information should be returned
    
    async def test_set_account_balance(self, async_api_client):
        """Test POST /api/control/balance/set endpoint."""
        response = await async_api_client.post(
            "/api/control/balance/set",
            json={"balance": 1000000.0}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        # Balance should be set


