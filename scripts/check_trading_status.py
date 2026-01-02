"""Check trading service status and manually trigger analysis if needed."""
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from data.market_memory import MarketMemory
from trading_orchestration.trading_graph import TradingGraph

async def check_status():
    """Check current trading system status."""
    print("=" * 70)
    print("Trading System Status Check")
    print("=" * 70)
    print()
    
    # Check Redis for latest data
    print("1. Checking Market Data...")
    try:
        market_memory = MarketMemory()
        instrument_key = settings.instrument_symbol.replace('-', '').replace(' ', '').upper()
        
        # Get latest price
        price_key = f'price:{instrument_key}:latest'
        latest_price = market_memory.redis_client.get(price_key) if market_memory.redis_client else None
        
        if latest_price:
            print(f"   [OK] Latest price: ${float(latest_price):,.2f}")
        else:
            print("   [WARNING] No price data found in Redis")
        
        # Check for recent ticks
        tick_keys = market_memory.redis_client.keys(f'tick:{instrument_key}:*') if market_memory.redis_client else []
        if tick_keys:
            print(f"   [OK] Found {len(tick_keys)} tick entries in Redis")
        else:
            print("   [WARNING] No tick data found in Redis")
    except Exception as e:
        print(f"   [FAIL] Error checking market data: {e}")
    
    print()
    
    # Check MongoDB for last analysis
    print("2. Checking Last Analysis...")
    try:
        from mongodb_schema import get_mongo_client, get_collection
        client = get_mongo_client()
        db = client[settings.mongodb_db_name]
        trades_collection = get_collection(db, "trades")
        
        # Get last trade/analysis
        last_trade = trades_collection.find_one(
            sort=[("timestamp", -1)]
        )
        
        if last_trade:
            timestamp = last_trade.get('timestamp', 'Unknown')
            signal = last_trade.get('signal', 'Unknown')
            print(f"   [OK] Last analysis: {timestamp}")
            print(f"   [OK] Last signal: {signal}")
        else:
            print("   [WARNING] No analysis found in MongoDB")
    except Exception as e:
        print(f"   [FAIL] Error checking MongoDB: {e}")
    
    print()
    
    # Test trading graph execution
    print("3. Testing Trading Graph...")
    try:
        trading_graph = TradingGraph(kite=None, market_memory=market_memory)
        print("   [OK] Trading graph initialized")
        
        # Try to run a quick test (with timeout)
        print("   [INFO] Attempting to run analysis (with 2 minute timeout)...")
        try:
            result = await asyncio.wait_for(
                trading_graph.arun(),
                timeout=120.0  # 2 minutes for test
            )
            signal = result.final_signal.value if hasattr(result.final_signal, 'value') else str(result.final_signal)
            print(f"   [OK] Analysis completed successfully!")
            print(f"   [OK] Signal: {signal}")
        except asyncio.TimeoutError:
            print("   [FAIL] Analysis timed out after 2 minutes")
            print("   [INFO] This suggests LLM calls are hanging")
        except Exception as e:
            print(f"   [FAIL] Analysis failed: {e}")
    except Exception as e:
        print(f"   [FAIL] Error initializing trading graph: {e}")
    
    print()
    print("=" * 70)
    print("Status Check Complete")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(check_status())

