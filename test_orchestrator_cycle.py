#!/usr/bin/env python3
"""Test orchestrator cycle manually."""

import asyncio
import sys
import os

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'engine_module', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'genai_module', 'src'))

async def test_orchestrator_cycle():
    """Manually run orchestrator cycle to test WebSocket publishing."""
    try:
        from engine_module.api import build_orchestrator
        from datetime import datetime

        print("🔧 Building orchestrator...")
        orchestrator = await build_orchestrator()

        if orchestrator is None:
            print("❌ Failed to build orchestrator")
            return

        print("✅ Orchestrator built successfully")

        # Run a cycle
        print("🏃 Running orchestrator cycle...")
        context = {
            'symbol': 'BANKNIFTY',
            'timestamp': datetime.now(),
            'cycle_info': {'cycle_number': 1, 'duration_seconds': 0}
        }

        result = await orchestrator.run_cycle(context)
        print("✅ Cycle completed")

        # Check result
        print(f"Decision: {result.action}")
        print(f"Confidence: {result.confidence:.1%}")
        print(f"Agent signals: {len(result.agent_signals)}")

        # Check if WebSocket publishing worked
        import redis.asyncio as redis_async
        redis_client = redis_async.Redis(host='localhost', port=6379, db=0, decode_responses=True)

        # Check for agent messages
        agent_keys = await redis_client.keys('engine:agent*')
        print(f"Redis agent keys: {len(agent_keys)}")

        # Check for decision messages
        decision_keys = await redis_client.keys('engine:decision*')
        print(f"Redis decision keys: {len(decision_keys)}")

        await redis_client.aclose()

        if agent_keys:
            print("✅ Agent data published to Redis")
        else:
            print("❌ No agent data in Redis")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_orchestrator_cycle())