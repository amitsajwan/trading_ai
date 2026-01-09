import pytest
import asyncio
from datetime import datetime
from decimal import Decimal

from user_module.stores import MongoTradeStore
from user_module.contracts import Trade


@pytest.mark.asyncio
async def test_trade_persists_signal_id(test_mongo_client):
    """Ensure that recording a trade with signal_id persists and is retrievable."""
    db = test_mongo_client
    trade_store = MongoTradeStore(db)

    trade_id = f"test_trade_{int(datetime.utcnow().timestamp())}"
    t = Trade(
        user_id="test_user",
        trade_id=trade_id,
        order_id="ord_123",
        instrument="BANKNIFTY",
        side="BUY",
        quantity=25,
        price=Decimal("1234.56"),
        order_type="MARKET",
        timestamp=datetime.utcnow(),
        status="EXECUTED",
        broker_fees=Decimal("1.0"),
        exchange_fees=Decimal("0.5"),
        signal_id="sig_abc123"
    )

    ok = await trade_store.record_trade(t)
    assert ok is True

    fetched = await trade_store.get_trade(trade_id)
    assert fetched is not None
    assert getattr(fetched, "signal_id", None) == "sig_abc123"

    # Also ensure get_user_trades returns it
    trades = await trade_store.get_user_trades("test_user", limit=10)
    assert any(getattr(tr, "signal_id", None) == "sig_abc123" for tr in trades)
