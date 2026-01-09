import asyncio
from datetime import datetime
from engine_module.api import build_orchestrator
from engine_module.agent_factory import create_default_agents

class ConflictingLLM:
    async def generate(self, request):
        class R:
            content = '{"decision":"BUY_CALL","confidence":0.9}'
        return R()

class StubMarketNeutral:
    async def get_latest_ticks(self, instrument, limit=100):
        return [{'last_price': 60200.0, 'timestamp': datetime.utcnow().isoformat()}]
    async def get_ohlc(self, instrument, timeframe, start=None, end=None):
        data = []
        for i in range(30):
            data.append({'timestamp': datetime.utcnow().isoformat(), 'open': 60200, 'high':60250, 'low':60150, 'close':60225, 'volume':1000})
        return data

class MockOptionsData:
    async def fetch_chain(self, instrument):
        return {'expiries':[], 'calls':[], 'puts':[], 'underlying_price':60200.0, 'pcr':1.0}

async def run():
    llm = ConflictingLLM()
    market = StubMarketNeutral()
    options = MockOptionsData()
    agents = create_default_agents(profile='balanced')
    orchestrator = build_orchestrator(llm_client=llm, market_store=market, options_data=options, agents=agents, llm_override_min_strength=0.9)
    res = await orchestrator.run_cycle({'instrument':'BANKNIFTY','market_hours':True,'timestamp':datetime.utcnow().isoformat(),'cycle_interval':'15min'})
    print('Decision', res.decision)
    print('Aggregated:', res.details.get('aggregated_analysis'))

if __name__ == '__main__':
    asyncio.run(run())