import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from engine_module.enhanced_orchestrator import EnhancedTradingOrchestrator
from engine_module.signal_monitor import SignalTriggerEvent


@pytest.mark.asyncio
async def test_auto_execute_dry_run(monkeypatch):
    # Build orchestrator with auto_execute in dry-run mode
    orchestrator = EnhancedTradingOrchestrator(market_data_provider=Mock(), technical_data_provider=Mock(), position_provider=Mock(), config={'auto_execute_signals': True, 'auto_execute_dry_run': True})

    # Patch mark_signal_status to capture calls
    called = {'count': 0}
    async def fake_mark(sid, status, mongo_db=None, extra=None):
        called['count'] += 1
        return True
    monkeypatch.setattr('engine_module.signal_creator.mark_signal_status', fake_mark)

    # Create fake event
    event = SignalTriggerEvent(
        condition_id='sig123',
        instrument='BANKNIFTY',
        action='BUY',
        triggered_at=datetime.now().isoformat(),
        indicator_name='current_price',
        indicator_value=45000.0,
        threshold=44900.0,
        current_price=45000.0,
        position_size=1.0,
        confidence=0.8,
        stop_loss=None,
        take_profit=None,
        strategy_type='SPOT',
        all_indicators={}
    )

    await orchestrator._on_signal_triggered(event)

    assert called['count'] == 1


@pytest.mark.asyncio
async def test_auto_execute_execute_path(monkeypatch):
    # Build orchestrator with auto_execute enabled (real execute)
    fake_position_provider = Mock()
    fake_position_provider.execute_trading_decision = AsyncMock(return_value={'success': True, 'trade_id': 't1'})
    orchestrator = EnhancedTradingOrchestrator(market_data_provider=Mock(), technical_data_provider=Mock(), position_provider=fake_position_provider, config={'auto_execute_signals': True, 'auto_execute_dry_run': False})

    # Patch mark_signal_status
    called = {'count': 0, 'status': None}
    async def fake_mark(sid, status, mongo_db=None, extra=None):
        called['count'] += 1
        called['status'] = status
        return True
    monkeypatch.setattr('engine_module.signal_creator.mark_signal_status', fake_mark)

    # Also patch DB query to return non-executed
    class FakeMongoClient:
        def __getitem__(self, name):
            return {'signals': Mock(), 'find_one': Mock(return_value=None)}
    monkeypatch.setattr('engine_module.api_service.get_mongo_client', lambda: FakeMongoClient())

    event = SignalTriggerEvent(
        condition_id='sig456',
        instrument='BANKNIFTY',
        action='SELL',
        triggered_at=datetime.now().isoformat(),
        indicator_name='current_price',
        indicator_value=45000.0,
        threshold=44900.0,
        current_price=45000.0,
        position_size=1.0,
        confidence=0.8,
        stop_loss=None,
        take_profit=None,
        strategy_type='SPOT',
        all_indicators={}
    )

    await orchestrator._on_signal_triggered(event)

    assert called['count'] == 1
    assert called['status'] == 'executed'