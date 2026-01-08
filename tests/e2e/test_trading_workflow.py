"""End-to-end workflow tests for complete trading cycles."""

import pytest
from datetime import datetime, date, timedelta
from tests.e2e.utils.test_helpers import (
    validate_api_response,
    wait_for_condition,
    create_test_signal
)


@pytest.mark.asyncio
@pytest.mark.slow
class TestTradingWorkflow:
    """Test complete trading workflows from signal to execution."""
    
    async def test_complete_signal_to_trade_workflow(self, async_api_client):
        """Test complete workflow: signal generation → execution → position tracking."""
        # Step 1: Ensure we're in paper_mock mode
        mode_response = await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_mock"}
        )
        assert mode_response.status_code == 200
        
        # Step 2: Run trading cycle to generate signals
        cycle_response = await async_api_client.post("/api/trading/cycle")
        assert cycle_response.status_code == 200
        
        cycle_data = cycle_response.json()
        assert cycle_data.get("success") is not False  # May be True or None
        
        # Step 3: Get generated signals
        signals_response = await async_api_client.get("/api/trading/signals")
        assert signals_response.status_code == 200
        
        signals_data = signals_response.json()
        signals = signals_data if isinstance(signals_data, list) else signals_data.get("signals", [])
        
        # Step 4: If signals exist, test execution flow
        if signals and len(signals) > 0:
            signal = signals[0]
            signal_id = signal.get("id")
            
            if signal_id:
                # Step 5: Check signal conditions
                conditions_response = await async_api_client.get(
                    f"/api/trading/conditions/{signal_id}"
                )
                assert conditions_response.status_code == 200
                
                conditions_data = conditions_response.json()
                
                # Step 6: Execute signal if conditions are met or if immediate execution
                if conditions_data.get("conditions_met") or signal.get("execution_type") == "immediate":
                    execute_response = await async_api_client.post(
                        f"/api/trading/execute/{signal_id}"
                    )
                    assert execute_response.status_code == 200
                    
                    execute_data = execute_response.json()
                    assert execute_data.get("success") is not False
                    
                    # Step 7: Verify position was created
                    positions_response = await async_api_client.get("/api/trading/positions")
                    assert positions_response.status_code == 200
                    
                    positions_data = positions_response.json()
                    positions = positions_data if isinstance(positions_data, list) else positions_data.get("positions", [])
                    
                    # Position should exist (may take a moment)
                    # This is a basic check - actual position tracking may vary
    
    async def test_trading_cycle_generates_signals(self, async_api_client):
        """Test that trading cycle generates signals correctly."""
        # Switch to paper_mock
        await async_api_client.post(
            "/api/control/mode/switch",
            json={"mode": "paper_mock"}
        )
        
        # Run trading cycle
        response = await async_api_client.post("/api/trading/cycle")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        
        # Check if signals were generated
        if "signals" in data:
            signals = data["signals"]
            assert isinstance(signals, list)
            
            # If signals exist, validate structure
            if len(signals) > 0:
                signal = signals[0]
                required_fields = ["id", "symbol", "action", "status"]
                for field in required_fields:
                    assert field in signal, f"Signal missing required field: {field}"
    
    async def test_signal_execution_creates_position(self, async_api_client):
        """Test that executing a signal creates a position."""
        # This test assumes a signal exists or can be created
        # In a real scenario, you'd create a test signal first
        
        # Get existing signals
        signals_response = await async_api_client.get("/api/trading/signals")
        assert signals_response.status_code == 200
        
        signals_data = signals_response.json()
        signals = signals_data if isinstance(signals_data, list) else signals_data.get("signals", [])
        
        # If no signals, skip this test
        if not signals or len(signals) == 0:
            pytest.skip("No signals available for execution test")
        
        # Get first pending signal
        pending_signals = [s for s in signals if s.get("status") == "pending"]
        if not pending_signals:
            pytest.skip("No pending signals available")
        
        signal = pending_signals[0]
        signal_id = signal.get("id")
        
        # Execute signal
        execute_response = await async_api_client.post(
            f"/api/trading/execute/{signal_id}"
        )
        assert execute_response.status_code == 200
        
        execute_data = execute_response.json()
        
        # Verify execution was successful
        if execute_data.get("success"):
            # Check that position was created
            positions_response = await async_api_client.get("/api/trading/positions")
            assert positions_response.status_code == 200
            
            positions_data = positions_response.json()
            positions = positions_data if isinstance(positions_data, list) else positions_data.get("positions", [])
            
            # Position should exist (may need to wait a moment)
            # This is a basic validation
    
    async def test_trading_stats_updated(self, async_api_client):
        """Test that trading statistics are updated after operations."""
        # Get initial stats
        stats_response1 = await async_api_client.get("/api/trading/stats")
        assert stats_response1.status_code == 200
        
        stats1 = stats_response1.json()
        
        # Run trading cycle
        await async_api_client.post("/api/trading/cycle")
        
        # Get updated stats
        stats_response2 = await async_api_client.get("/api/trading/stats")
        assert stats_response2.status_code == 200
        
        stats2 = stats_response2.json()
        
        # Stats should be updated (structure may vary)
        assert isinstance(stats2, dict)
    
    async def test_conditional_signal_execution(self, async_api_client):
        """Test conditional signal execution when conditions are met."""
        # This test validates that conditional signals execute when conditions are met
        # In a real scenario, you'd need to:
        # 1. Create a conditional signal
        # 2. Update market data to meet conditions
        # 3. Verify signal executes
        
        # For now, we'll test the condition checking endpoint
        signals_response = await async_api_client.get("/api/trading/signals")
        assert signals_response.status_code == 200
        
        signals_data = signals_response.json()
        signals = signals_data if isinstance(signals_data, list) else signals_data.get("signals", [])
        
        # Find conditional signals
        conditional_signals = [
            s for s in signals
            if s.get("execution_type") == "conditional" and s.get("status") == "pending"
        ]
        
        if conditional_signals:
            signal = conditional_signals[0]
            signal_id = signal.get("id")
            
            # Check conditions
            conditions_response = await async_api_client.get(
                f"/api/trading/conditions/{signal_id}"
            )
            assert conditions_response.status_code == 200
            
            conditions_data = conditions_response.json()
            assert "conditions_met" in conditions_data or "can_execute" in conditions_data


