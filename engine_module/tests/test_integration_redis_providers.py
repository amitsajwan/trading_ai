import pytest
import json
import asyncio
from datetime import datetime, timedelta
from engine_module.api import build_orchestrator
from engine_module.agent_factory import create_default_agents

# Minimal in-memory Redis mock supporting the methods used by our providers
class InMemoryRedis:
    def __init__(self):
        self.store = {}
        self.sorted_sets = {}
    def ping(self):
        return True
    def zadd(self, key, mapping):
        self.sorted_sets.setdefault(key, []).extend(mapping.keys())
    def zrange(self, key, start, end):
        arr = self.sorted_sets.get(key, [])
        if not arr:
            return []
        # support negative indices
        if start < 0:
            start = max(0, len(arr) + start)
        if end < 0:
            end = len(arr) + end + 1
        return arr[start:end+1]
    def keys(self, pattern):
        import fnmatch
        return [k for k in self.store.keys() if fnmatch.fnmatch(k, pattern)]
    def get(self, key):
        return self.store.get(key)
    def set(self, key, value):
        self.store[key] = value

@pytest.mark.asyncio
async def test_orchestrator_with_redis_providers():
    # Setup in-memory redis and populate with 15min ohlc and indicators
    r = InMemoryRedis()
    symbol = 'BANKNIFTY'

    # Create 60 bars of 15min data as JSON strings and push into sorted set
    key = f"ohlc_sorted:{symbol}:15min"
    bars = []
    base = 60000
    for i in range(60):
        payload = {
            'instrument': symbol,
            'timeframe': '15min',
            'open': float(base + i),
            'high': float(base + i + 10),
            'low': float(base + i - 10),
            'close': float(base + i + 5),
            'volume': 1000 + i*10,
            'start_at': (datetime.utcnow() - timedelta(minutes=15*(60-i))).isoformat()
        }
        bars.append(json.dumps(payload))
    # emulate zrange storing
    r.sorted_sets[key] = bars

    # Set indicators
    r.set(f"indicators:{symbol}:rsi", '65.0')
    r.set(f"indicators:{symbol}:sma_20", '60350.0')
    r.set(f"indicators:{symbol}:sma_50", '60300.0')
    r.set(f"price:{symbol}:latest", '60250')

    # Build orchestrator with redis client
    llm = None  # test fallback decision path
    agents = create_default_agents(profile='balanced')
    orchestrator = build_orchestrator(llm_client=llm, redis_client=r, agents=agents)

    res = await orchestrator.run_cycle({'instrument': symbol, 'market_hours': True, 'timestamp': datetime.utcnow().isoformat(), 'cycle_interval':'15min'})
    assert res is not None
    details = res.details
    assert details.get('data_points', 0) > 0
    agg = details.get('aggregated_analysis', {})
    # technical signals should reflect agent names
    tech = agg.get('technical_signals', [])
    assert isinstance(tech, list)
    if tech:
        assert all('agent' in t for t in tech)
