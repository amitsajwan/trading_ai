#!/usr/bin/env python3
"""Demonstrate the 15-minute options trading analysis cycle."""

import asyncio
import sys
sys.path.insert(0, 'engine_module/src')
sys.path.insert(0, 'data_niftybank/src')

from engine_module.api import build_orchestrator
from engine_module.agents.technical_agent import TechnicalAgent
from engine_module.agents.sentiment_agent import SentimentAgent
from engine_module.agents.macro_agent import MacroAgent

class MockLLMClient:
    async def request(self, request):
        class MockResponse:
            content = '''{
                "decision": "BUY_CALL",
                "confidence": 0.75,
                "strategy": "Buy ATM Call option for next 15 minutes",
                "reasoning": "Strong technical momentum with positive indicators",
                "risk_notes": "Position size limited to 2% of capital",
                "timeframe": "Hold for next 15-30 minutes",
                "entry_conditions": "Enter on next 15-minute candle open"
            }'''
        
        return MockResponse()
    
    async def generate(self, request):
        """Bridge method for compatibility with orchestrator."""
        return await self.request(request)

class MockMarketStore:
    async def get_latest_ticks(self, instrument, limit=100):
        return [{'last_price': 60125.0, 'timestamp': '2026-01-05T14:30:00Z'}]

    async def get_ohlc(self, instrument, timeframe, start=None, end=None):
        # Generate trending OHLC data
        data = []
        base_price = 60000
        for i in range(16):  # 4 hours of 15-min data
            trend = i * 15  # Upward trend
            volatility = (i % 4 - 2) * 25  # Some volatility
            price = base_price + trend + volatility

            data.append({
                'timestamp': f'2026-01-05T{10+i//4:02d}:{(i%4)*15:02d}:00Z',
                'open': price - 20,
                'high': price + 50,
                'low': price - 50,
                'close': price,
                'volume': 10000 + i * 500
            })
        return data

class MockOptionsData:
    async def fetch_chain(self, instrument):
        return {
            'expiries': ['2026-01-09', '2026-01-16'],
            'calls': [
                {'strike': 60000, 'price': 180, 'oi': 150000},
                {'strike': 60100, 'price': 125, 'oi': 200000},
                {'strike': 60200, 'price': 85, 'oi': 180000}
            ],
            'puts': [
                {'strike': 60000, 'price': 95, 'oi': 175000},
                {'strike': 60100, 'price': 145, 'oi': 160000}
            ],
            'underlying_price': 60125.0,
            'pcr': 1.15
        }

async def demonstrate_15min_cycle():
    """Demonstrate the complete 15-minute options trading analysis cycle."""

    print("15-MINUTE OPTIONS TRADING ANALYSIS CYCLE")
    print("=" * 50)

    # Setup mock dependencies
    llm_client = MockLLMClient()
    market_store = MockMarketStore()
    options_data = MockOptionsData()

    # Configure agents
    agents = [
        TechnicalAgent(),
        SentimentAgent(),
        MacroAgent()
    ]

    print(f"🔧 Configured {len(agents)} agents for analysis")
    print("   - Technical Agent: Price action & indicators")
    print("   - Sentiment Agent: Market psychology")
    print("   - Macro Agent: Economic conditions")

    # Build orchestrator
    orchestrator = build_orchestrator(
        llm_client=llm_client,
        market_store=market_store,
        options_data=options_data,
        agents=agents
    )

    print("\n📊 EXECUTING ANALYSIS CYCLE")
    print("-" * 30)
    print("Instrument: BANKNIFTY")
    print("Timeframe: 15-minute analysis")
    print("Market Status: OPEN")

    # Execute the analysis cycle
    context = {
        'instrument': 'BANKNIFTY',
        'market_hours': True,
        'cycle_interval': '15min',
        'timestamp': '2026-01-05T14:45:00Z'
    }

    result = await orchestrator.run_cycle(context)

    print("\n🎯 ANALYSIS RESULTS")
    print("=" * 20)
    print(f"Decision: {result.decision}")
    print(f"Confidence: {result.confidence:.1%}")
    print(f"Strategy: {result.details.get('strategy', 'N/A')}")

    # Show agent breakdown
    aggregated = result.details.get('aggregated_analysis', {})
    breakdown = aggregated.get('agent_breakdown', {})
    print("\nAgent Signals:")
    print(f"  Buy: {breakdown.get('buy_signals', 0)}")
    print(f"  Sell: {breakdown.get('sell_signals', 0)}")
    print(f"  Hold: {breakdown.get('hold_signals', 0)}")
    print(f"  Consensus: {aggregated.get('consensus_direction', 'N/A')}")

    print("\nKey Insights:")
    insights = aggregated.get('key_insights', [])
    for insight in insights[:2]:
        print(f"  • {insight}")

    print("\nRisk Assessment:")
    print(f"  Level: {aggregated.get('risk_assessment', 'UNKNOWN')}")
    print(f"  Recommended Strategy: {aggregated.get('options_strategy', 'HOLD')}")

    print("\n🎉 ANALYSIS CYCLE COMPLETE!")
    print("The orchestrator successfully analyzed market conditions")
    print("and provided an options trading strategy for the next 15 minutes!")

if __name__ == '__main__':
    asyncio.run(demonstrate_15min_cycle())

