import asyncio
import pytest
from datetime import datetime

from engine_module.api import build_orchestrator
from engine_module.agent_factory import create_default_agents

class MockLLMClient:
    async def generate(self, request):
        class R:
            content = '{"decision":"HOLD","confidence":0.3}'
        return R()

class StubMarketStoreSimple:
    async def get_latest_ticks(self, instrument, limit=100):
        return [{'last_price': 60200.0, 'timestamp': datetime.utcnow().isoformat()}]
    async def get_ohlc(self, instrument, timeframe, start=None, end=None):
        data = []
        for i in range(30):
            data.append({'timestamp': datetime.utcnow().isoformat(), 'open': 60200+i, 'high':60250+i, 'low':60150+i, 'close':60225+i, 'volume':1000})
        return data

class MockOptionsData:
    async def fetch_chain(self, instrument):
        return {'expiries':['2026-01-09'],'calls':[],'puts':[],'underlying_price':60200.0,'pcr':1.0}

@pytest.mark.asyncio
async def test_orchestrator_attaches_agent_names():
    llm = MockLLMClient()
    market_store = StubMarketStoreSimple()
    options = MockOptionsData()
    agents = create_default_agents(profile='balanced')

    orchestrator = build_orchestrator(llm_client=llm, market_store=market_store, options_data=options, agents=agents)
    res = await orchestrator.run_cycle({'instrument':'BANKNIFTY','market_hours':True,'timestamp':datetime.utcnow().isoformat(),'cycle_interval':'15min'})
    agg = res.details.get('aggregated_analysis', {})
    # If agents produced technical_signals, each should have non-empty 'agent' field
    t = agg.get('technical_signals', [])
    for entry in t:
        assert entry.get('agent') is not None and entry.get('agent') != ''
