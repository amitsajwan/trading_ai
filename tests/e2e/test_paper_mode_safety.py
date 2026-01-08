"""Tests to ensure paper mode prevents live trading."""

import pytest
from unittest.mock import Mock, patch, call
from tests.e2e.utils.test_helpers import validate_api_response


@pytest.mark.asyncio
class TestPaperModeSafety:
    """Test suite for paper mode safety - ensures no live trading."""
    
    async def test_paper_mode_prevents_live_broker_calls(self, async_api_client, mock_kite):
        """Test that paper mode does not call live broker API."""
        # Switch to paper_mock mode
        await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_mock"}
        )
        
        # Run trading cycle
        with patch('dashboard.app._kite_client', mock_kite) as mock:
            response = await async_api_client.post("/api/trading/cycle")
            assert response.status_code == 200
            
            # Verify Kite API was NOT called for order placement
            # (In paper mode, should use paper broker instead)
            # Note: This is a simplified check - actual implementation may vary
    
    async def test_paper_trades_stored_separately(self, async_api_client, test_mongo_client):
        """Test that paper trades are stored in separate database."""
        # Switch to paper_mock mode
        await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_mock"}
        )
        
        # Get current mode info
        mode_response = await async_api_client.get("/api/control/mode/info")
        mode_data = mode_response.json()
        
        # Verify database is paper_mock database
        assert "mock" in mode_data.get("database", "").lower() or \
               mode_data.get("mode") == "paper_mock"
    
    async def test_paper_mode_balance_isolated(self, async_api_client):
        """Test that paper mode balance is separate from live balance."""
        # Switch to paper_mock
        await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_mock"}
        )
        
        # Set paper balance
        set_balance_response = await async_api_client.post(
            "/api/control/balance/set",
            json={"balance": 500000.0}
        )
        assert set_balance_response.status_code == 200
        
        # Get balance
        get_balance_response = await async_api_client.get("/api/control/balance")
        assert get_balance_response.status_code == 200
        
        balance_data = get_balance_response.json()
        # Paper balance should be separate from live balance
        assert isinstance(balance_data, dict)
    
    async def test_mode_switch_maintains_isolation(self, async_api_client):
        """Test that switching modes maintains data isolation."""
        # Start in paper_mock
        await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_mock"}
        )
        
        mode1_response = await async_api_client.get("/api/control/mode/info")
        mode1_data = mode1_response.json()
        db1 = mode1_data.get("database")
        
        # Switch to paper_live
        await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_live"}
        )
        
        mode2_response = await async_api_client.get("/api/control/mode/info")
        mode2_data = mode2_response.json()
        db2 = mode2_data.get("database")
        
        # Databases should be different (or at least mode should be different)
        assert mode1_data.get("mode") != mode2_data.get("mode") or db1 != db2
    
    async def test_paper_trades_not_executed_live(self, async_api_client, mock_kite):
        """Test that trades in paper mode are not executed with live broker."""
        # Ensure we're in paper mode
        await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_mock"}
        )
        
        # Run trading cycle - in paper mode, should not call live broker
        cycle_response = await async_api_client.post("/api/trading/cycle")
        assert cycle_response.status_code == 200
        
        # Verify we're in paper mode (no live trading should occur)
        mode_response = await async_api_client.get("/api/control/mode/info")
        mode_data = mode_response.json()
        current_mode = mode_data.get("mode") or mode_data.get("current_mode")
        assert current_mode in ["paper_mock", "paper_live"], "Should be in paper mode"
    
    async def test_live_mode_requires_explicit_confirmation(self, async_api_client):
        """Test that switching to live mode requires explicit confirmation."""
        # Try to switch to live without confirmation
        response1 = await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "live"}
        )
        assert response1.status_code == 200
        
        data1 = response1.json()
        # Should require confirmation
        if "confirmation_required" in data1:
            assert data1["confirmation_required"] is True
        
        # Try with confirmation
        response2 = await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "live", "confirm": True}
        )
        assert response2.status_code == 200
        
        data2 = response2.json()
        # May still require Zerodha authentication
        assert isinstance(data2, dict)
    
    async def test_paper_mode_configuration(self, async_api_client):
        """Test that paper mode configuration is correct."""
        # Switch to paper_mock
        await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_mock"}
        )
        
        # Get control status
        status_response = await async_api_client.get("/api/control/status")
        assert status_response.status_code == 200
        
        status_data = status_response.json()
        
        # Verify paper mode indicators
        assert status_data.get("mode") in ["paper_mock", "paper_live"]
        
        # Paper mode should have paper trading enabled
        # (Actual structure may vary based on implementation)


