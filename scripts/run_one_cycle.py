#!/usr/bin/env python3
"""Run a single orchestrator cycle using full agent roster and mock LLM/market providers.

This script runs one cycle, prints the decision and aggregated analysis, and persists to MongoDB
(simulating what the real orchestrator would do). Useful for testing and debugging agents.
"""
import asyncio
from datetime import datetime
from pymongo import MongoClient

import sys
sys.path.insert(0, 'engine_module/src')
sys.path.insert(0, 'data_niftybank/src')
from engine_module.api import build_orchestrator
from engine_module.agent_factory import create_default_agents

class MockLLMClient:
    async def generate(self, request):
        class MockResponse:
            content = '{"decision":"HOLD","confidence":0.3,"strategy":"HOLD - Insufficient conviction","reasoning":"Fallback logic","risk_notes":"No action","timeframe":"15min","entry_conditions":"N/A"}'
        return MockResponse()

class StubMarketStoreSimple:
    async def get_latest_ticks(self, instrument, limit=100):
        return [{'last_price': 60200.0, 'timestamp': datetime.utcnow().isoformat()}]
    async def get_ohlc(self, instrument, timeframe, start=None, end=None):
        # return minimal 15-min bars
        data = []
        base = 60200
        for i in range(24*4):
            data.append({'timestamp': datetime.utcnow().isoformat(), 'open': base, 'high': base+10, 'low': base-10, 'close': base+5, 'volume':1000})
        return data

class MockOptionsData:
    async def fetch_chain(self, instrument):
        return {'expiries':['2026-01-09'],'calls':[],'puts':[],'underlying_price':60200.0,'pcr':1.0}

async def main():
    llm = MockLLMClient()
    market_store = StubMarketStoreSimple()
    options = MockOptionsData()
    agents = create_default_agents(profile='balanced')

    orchestrator = build_orchestrator(llm_client=llm, market_store=market_store, options_data=options, agents=agents)

    ctx = {'instrument':'BANKNIFTY','market_hours':True,'timestamp':datetime.utcnow().isoformat(),'cycle_interval':'15min'}
    print('Running single cycle...')
    res = await orchestrator.run_cycle(ctx)
    print('Decision:', res.decision, 'Confidence:', res.confidence)
    agg = res.details.get('aggregated_analysis')
    print('Aggregated consensus:', agg.get('consensus_direction'))

    # Persist to MongoDB (simulate run_orchestrator persistence)
    client = MongoClient('mongodb://localhost:27017/')
    db = client.zerodha_trading
    doc = {
        'timestamp': datetime.utcnow().isoformat(),
        'instrument': 'BANKNIFTY',
        'final_signal': res.decision,
        'confidence': float(res.confidence),
        'reasoning': res.details.get('reasoning', ''),
        'details': res.details,
    }
    db.agent_decisions.insert_one(doc)
    print('Persisted decision to MongoDB agent_decisions')

    # Also persist agent_discussions flattened
    for entry in agg.get('technical_signals', []) + agg.get('sentiment_signals', []) + agg.get('macro_signals', []):
        discussion = {
            'timestamp': datetime.utcnow().isoformat(),
            'agent_name': entry.get('agent'),
            'signal': entry.get('signal'),
            'confidence': entry.get('confidence'),
            'details': entry,
        }
        db.agent_discussions.insert_one(discussion)
    print('Persisted agent discussions')

if __name__ == '__main__':
    asyncio.run(main())
