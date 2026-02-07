import pytest

from engine_module.services.position_manager import PositionManager


@pytest.mark.asyncio
async def test_position_manager_close_long_executes():
    pm = PositionManager(initial_equity=1_000_000, max_positions=5)

    # Open a long position
    pos = await pm.open_position(
        symbol="BANKNIFTY",
        action="BUY",
        quantity=1,
        entry_price=45000,
        stop_loss=44750,
        take_profit=45500,
        tags=["test"],
    )
    assert pos is not None
    assert pos.status == "active"

    # Close it via execute_trading_decision
    res = await pm.execute_trading_decision(
        instrument="BANKNIFTY",
        decision="CLOSE_LONG",
        confidence=0.8,
        analysis_details={"current_price": 45100},
    )

    assert res["status"] == "EXECUTED"
    assert res["action"] == "CLOSE"
    assert res["symbol"] == "BANKNIFTY"

    # Position should now be closed
    p = pm.get_position_by_id(res["position_id"])
    assert p is not None
    assert p["status"] == "closed"

