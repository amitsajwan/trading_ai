"""Test agent analysis before starting system - runs a single analysis cycle."""
import sys
import os
import asyncio
import logging
from pathlib import Path

# Fix Windows encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent))

# Suppress verbose logging during test
logging.basicConfig(level=logging.WARNING)

async def test_agent_analysis():
    """Test that agents can produce analysis."""
    print("Testing agent analysis...")
    
    try:
        from trading_orchestration.trading_graph import TradingGraph
        from data.market_memory import MarketMemory
        from config.settings import settings
    except ImportError as e:
        print('AGENT_TEST_MODULE_MISSING')
        print(f'Required module missing: {str(e)[:50]}')
        return False
    
    # Initialize market memory (may be empty, that's OK for test)
    market_memory = MarketMemory()
    
    # Initialize trading graph (no Kite needed for crypto)
    kite = None
    if settings.instrument_exchange != "CRYPTO":
        # For non-crypto, try to load credentials
        try:
            from kiteconnect import KiteConnect
            cred_path = Path(__file__).parent.parent / "credentials.json"
            if cred_path.exists():
                import json
                with open(cred_path) as f:
                    creds = json.load(f)
                kite = KiteConnect(api_key=creds.get("api_key"))
                kite.set_access_token(creds.get("access_token"))
        except Exception:
            pass  # Will use None, agents can still work
    
    print("   Initializing trading graph...")
    try:
        trading_graph = TradingGraph(kite=kite, market_memory=market_memory)
        print("   [OK] Trading graph initialized")
    except Exception as e:
        print('AGENT_TEST_INIT_ERROR')
        print(f'Failed to initialize trading graph: {str(e)[:100]}')
        return False
    
    # Run a single analysis cycle with timeout
    print("   Running single analysis cycle (this may take 30-60 seconds)...")
    try:
        result = await asyncio.wait_for(
            trading_graph.arun(),
            timeout=120.0  # 2 minutes max
        )
        print("   [OK] Analysis cycle completed")
    except asyncio.TimeoutError:
        print('AGENT_TEST_TIMEOUT')
        print('Agent analysis test timed out after 2 minutes')
        print('This usually means LLM calls are hanging or very slow')
        return False
    except Exception as e:
        print('AGENT_TEST_ERROR')
        print(f'Error during agent analysis: {str(e)[:100]}')
        import traceback
        print(f'Full error: {traceback.format_exc()[:300]}')
        return False
    
    # Verify results - check MongoDB for stored analysis
    try:
        from mongodb_schema import get_mongo_client, get_collection
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        analysis_collection = get_collection(db, "agent_decisions")
        latest = analysis_collection.find_one(sort=[("timestamp", -1)])
        
        if not latest:
            print('AGENT_TEST_NO_RESULTS')
            print('Analysis completed but no results stored in MongoDB')
            return False
        
        agent_decisions = latest.get("agent_decisions", {})
        final_signal = latest.get("final_signal", "UNKNOWN")
        
        # Check required agents
        required_agents = ['technical', 'fundamental', 'sentiment', 'macro']
        missing_agents = []
        empty_agents = []
        
        for agent_name in required_agents:
            if agent_name not in agent_decisions:
                missing_agents.append(agent_name)
            else:
                agent_data = agent_decisions[agent_name]
                if not agent_data or agent_data == {} or agent_data == []:
                    empty_agents.append(agent_name)
                elif isinstance(agent_data, dict):
                    # Check for meaningful content
                    non_empty = [v for v in agent_data.values() 
                                if v is not None and v != "" and v != "No recent news available"]
                    if not non_empty:
                        empty_agents.append(agent_name)
                elif isinstance(agent_data, str):
                    if agent_data.lower() in ['none', 'null', '', 'no recent news available']:
                        empty_agents.append(agent_name)
        
        if missing_agents:
            print('AGENT_TEST_MISSING_AGENTS')
            print(f'Missing agents: {", ".join(missing_agents)}')
            return False
        
        if empty_agents:
            print('AGENT_TEST_EMPTY_AGENTS')
            print(f'Agents with empty analysis: {", ".join(empty_agents)}')
            print('This may indicate LLM is not responding properly or prompts need adjustment')
            return False
        
        # Success
        agent_count = len(agent_decisions)
        signal_str = final_signal.value if hasattr(final_signal, 'value') else str(final_signal)
        
        print('AGENT_TEST_OK')
        print(f'Signal: {signal_str}, Agents: {agent_count}')
        print('All agents produced meaningful analysis')
        return True
        
    except Exception as e:
        print('AGENT_TEST_VERIFY_ERROR')
        print(f'Error verifying results: {str(e)[:100]}')
        import traceback
        print(f'Full error: {traceback.format_exc()[:300]}')
        return False

def main():
    """Main entry point."""
    try:
        success = asyncio.run(test_agent_analysis())
        sys.exit(0 if success else 1)
    except Exception as e:
        print('AGENT_TEST_ERROR')
        print(f'Error in agent test: {str(e)[:100]}')
        import traceback
        print(f'Full error: {traceback.format_exc()[:300]}')
        sys.exit(1)

if __name__ == "__main__":
    main()
