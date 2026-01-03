"""Check if WebSocket is actually connected and receiving data RIGHT NOW."""

import sys
import os
import time
import asyncio
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO)  # Show info logs

async def test_websocket_connection():
    """Test WebSocket connection directly."""
    print("\n" + "=" * 70)
    print("TESTING WEBSOCKET CONNECTION")
    print("=" * 70)
    
    try:
        import websockets
        import json
        from config.settings import settings
        
        # Get Binance symbol
        symbol_map = {
            "BTC-USD": "btcusdt",
            "BTCUSD": "btcusdt",
            "BTC": "btcusdt",
        }
        symbol_upper = settings.instrument_symbol.upper().replace("-", "")
        binance_symbol = symbol_map.get(symbol_upper, symbol_upper.lower() + "usdt")
        
        ws_url = f"wss://stream.binance.com:9443/ws/{binance_symbol}@ticker"
        print(f"Connecting to: {ws_url}")
        print(f"Symbol: {binance_symbol} (from {settings.instrument_symbol})")
        
        ticks_received = 0
        start_time = time.time()
        
        try:
            async with websockets.connect(ws_url) as ws:
                print("[OK] Connected to Binance WebSocket!")
                print("Waiting for ticker updates (10 seconds)...\n")
                
                # Receive messages for 10 seconds
                timeout = time.time() + 10
                while time.time() < timeout:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        data = json.loads(message)
                        
                        price = float(data.get("c", 0))
                        symbol = data.get("s", "")
                        
                        if price > 0:
                            ticks_received += 1
                            elapsed = time.time() - start_time
                            print(f"  [{elapsed:.1f}s] Tick #{ticks_received}: {symbol} @ ${price:,.2f}")
                            
                            if ticks_received >= 3:
                                print(f"\n[OK] Received {ticks_received} ticks in {elapsed:.1f} seconds")
                                print("WebSocket IS working and receiving data!")
                                return True
                    except asyncio.TimeoutError:
                        print("  (waiting for data...)")
                        continue
                    except Exception as e:
                        print(f"  Error receiving: {e}")
                        continue
                
                if ticks_received > 0:
                    print(f"\n[!] Received {ticks_received} tick(s) but may be slow")
                    return False
                else:
                    print("\n[X] No ticks received in 10 seconds")
                    print("WebSocket connected but not receiving data")
                    return False
                    
        except websockets.exceptions.ConnectionClosed:
            print("[X] WebSocket connection closed")
            return False
        except Exception as e:
            print(f"[X] Error connecting: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except ImportError:
        print("[X] websockets library not installed")
        print("Install with: pip install websockets")
        return False
    except Exception as e:
        print(f"[X] Error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_tick_storage():
    """Test if tick storage is working."""
    print("\n" + "=" * 70)
    print("TESTING TICK STORAGE")
    print("=" * 70)
    
    try:
        from data.market_memory import MarketMemory
        from config.settings import settings
        
        mm = MarketMemory()
        
        if not mm._redis_available:
            print("[X] Redis not available - ticks cannot be stored")
            return False
        
        print("[OK] Redis is available")
        
        # Test storing a tick
        instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
        test_tick = {
            "last_price": 90000.0,
            "price": 90000.0,
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"Storing test tick for {instrument_key}...")
        mm.store_tick(instrument_key, test_tick)
        
        # Check if it was stored
        import redis
        r = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
            socket_connect_timeout=2
        )
        
        latest_price_key = f"price:{instrument_key}:latest"
        latest_ts_key = f"price:{instrument_key}:latest_ts"
        
        price = r.get(latest_price_key)
        ts = r.get(latest_ts_key)
        
        if price and ts:
            print(f"[OK] Test tick stored successfully!")
            print(f"  Latest price: ${float(price):,.2f}")
            print(f"  Timestamp: {ts}")
            return True
        else:
            print("[X] Test tick NOT stored")
            print(f"  Latest price key exists: {price is not None}")
            print(f"  Timestamp key exists: {ts is not None}")
            return False
            
    except Exception as e:
        print(f"[X] Error testing storage: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run tests."""
    print("\n" + "=" * 70)
    print("WEBSOCKET & TICK STORAGE DIAGNOSTIC")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Test 1: WebSocket connection
    ws_ok = await test_websocket_connection()
    
    # Test 2: Tick storage
    storage_ok = await test_tick_storage()
    
    # Summary
    print("\n" + "=" * 70)
    print("DIAGNOSTIC RESULTS")
    print("=" * 70)
    
    if ws_ok:
        print("[OK] WebSocket: Working - receiving data from Binance")
    else:
        print("[X] WebSocket: NOT working - not receiving data")
    
    if storage_ok:
        print("[OK] Tick Storage: Working - can store ticks in Redis")
    else:
        print("[X] Tick Storage: NOT working - cannot store ticks")
    
    if ws_ok and storage_ok:
        print("\n[OK] Both components working - issue may be in integration")
        print("Check if crypto_feed.start() is actually being called")
        print("Check logs for WebSocket connection messages")
    elif not ws_ok:
        print("\n[X] WebSocket not working - fix this first")
        print("Check network connectivity and Binance API status")
    elif not storage_ok:
        print("\n[X] Tick storage not working - fix this first")
        print("Check Redis is running and accessible")
    
    print("=" * 70 + "\n")
    
    return ws_ok and storage_ok

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nDiagnostic interrupted")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nDiagnostic failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

