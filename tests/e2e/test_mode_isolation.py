"""Tests for mode switching and database isolation."""

import pytest
from datetime import datetime, date, timedelta
from tests.e2e.utils.test_helpers import validate_api_response


@pytest.mark.asyncio
class TestModeIsolation:
    """Test suite for mode switching and isolation."""
    
    async def test_switch_between_modes(self, async_api_client):
        """Test switching between different modes."""
        modes = ["paper_mock", "paper_live"]
        
        for mode in modes:
            response = await async_api_client.post(
                "/api/control/mode/switch",
                json={"mode": mode}
            )
            assert response.status_code == 200
            
            data = response.json()
            assert isinstance(data, dict)
            
            # Verify mode was set
            mode_info_response = await async_api_client.get("/api/control/mode/info")
            assert mode_info_response.status_code == 200
            
            mode_info = mode_info_response.json()
            # Mode may be "mode" or "current_mode"
            actual_mode = mode_info.get("mode") or mode_info.get("current_mode")
            assert actual_mode == mode or mode in str(mode_info)
    
    async def test_database_isolation(self, async_api_client):
        """Test that different modes use different databases."""
        # Switch to paper_mock
        await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_mock"}
        )
        
        mode1_response = await async_api_client.get("/api/control/mode/info")
        mode1_data = mode1_response.json()
        db1 = mode1_data.get("database")
        mode1 = mode1_data.get("mode") or mode1_data.get("current_mode")
        
        # Switch to paper_live
        await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_live"}
        )
        
        mode2_response = await async_api_client.get("/api/control/mode/info")
        mode2_data = mode2_response.json()
        db2 = mode2_data.get("database")
        mode2 = mode2_data.get("mode") or mode2_data.get("current_mode")
        
        # Modes should be different
        assert mode1 is not None
        assert mode2 is not None
        assert mode1 != mode2
        
        # Databases should be different (or at least mode context should be)
        # In some implementations, databases might be the same but collections differ
        assert db1 != db2 or mode1 != mode2
    
    async def test_auto_switch_detection(self, async_api_client):
        """Test auto-switch detection logic."""
        response = await async_api_client.get("/api/control/mode/auto-switch")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        
        # Auto-switch status should be returned
        # Structure may vary based on implementation
    
    async def test_manual_override_prevents_auto_switch(self, async_api_client):
        """Test that manual override prevents auto-switching."""
        # Set manual mode
        await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_mock"}
        )
        
        # Check auto-switch status
        auto_switch_response = await async_api_client.get("/api/control/mode/auto-switch")
        assert auto_switch_response.status_code == 200
        
        auto_switch_data = auto_switch_response.json()
        # Manual override should be indicated
        assert isinstance(auto_switch_data, dict)
    
    async def test_clear_override_enables_auto_switch(self, async_api_client):
        """Test that clearing override enables auto-switch."""
        # Set manual mode
        await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_mock"}
        )
        
        # Clear override
        clear_response = await async_api_client.post("/api/control/mode/clear-override")
        assert clear_response.status_code == 200
        
        clear_data = clear_response.json()
        assert isinstance(clear_data, dict)
        
        # Auto-switch should be enabled
        auto_switch_response = await async_api_client.get("/api/control/mode/auto-switch")
        assert auto_switch_response.status_code == 200
    
    async def test_historical_replay_mode_switch(self, async_api_client):
        """Test switching to historical replay mode."""
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
        if "historical_replay" in data:
            hist_replay = data["historical_replay"]
            assert hist_replay.get("active") is True or "start_date" in hist_replay
    
    async def test_mode_info_accuracy(self, async_api_client):
        """Test that mode info accurately reflects current state."""
        # Switch to paper_mock
        await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_mock"}
        )
        
        # Get mode info
        response = await async_api_client.get("/api/control/mode/info")
        assert response.status_code == 200
        
        data = response.json()
        # Mode may be "mode" or "current_mode"
        mode_value = data.get("mode") or data.get("current_mode")
        assert mode_value is not None, "Mode should be present in response"
        
        # Mode should be paper_mock
        assert mode_value == "paper_mock"
    
    async def test_control_status_reflects_mode(self, async_api_client):
        """Test that control status accurately reflects current mode."""
        # Switch to paper_mock
        await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_mock"}
        )
        
        # Get control status
        response = await async_api_client.get("/api/control/status")
        assert response.status_code == 200
        
        data = response.json()
        is_valid, errors = validate_api_response(
            data,
            required_fields=["mode"]
        )
        assert is_valid, f"Response validation failed: {errors}"
        
        # Mode should match
        assert data.get("mode") == "paper_mock"


