import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from engine_module.enhanced_orchestrator import EnhancedTradingOrchestrator


@pytest.mark.asyncio
async def test_reconcile_marks_executed(monkeypatch):
    # Create orchestrator with fake position provider
    fake_position_provider = Mock()
    fake_position_provider.get_positions = AsyncMock(return_value=[{'position_id': 'pos1', 'instrument': 'BANKNIFTY', 'action': 'BUY', 'status': 'active', 'signal_id': 'sig100'}])
    orchestrator = EnhancedTradingOrchestrator(market_data_provider=Mock(), technical_data_provider=Mock(), position_provider=fake_position_provider)

    # Fake mongo db with one pending signal
    fake_update_called = {'count': 0}
    class FakeCollection:
        def find(self, q):
            return [{'_id': 'id1', 'condition_id': 'sig100', 'instrument': 'BANKNIFTY', 'action': 'BUY', 'status': 'pending', 'is_active': True}]
        def update_one(self, q, u):
            fake_update_called['count'] += 1
    fake_db = {'signals': FakeCollection()}

    async def fake_mark(sid, status, mongo_db=None, extra=None):
        fake_update_called['count'] += 1
        return True

    monkeypatch.setattr('engine_module.signal_creator.mark_signal_status', fake_mark)

    reconciled = await orchestrator.reconcile_signals_with_positions(fake_db)

    assert reconciled == 1
    assert fake_update_called['count'] == 1