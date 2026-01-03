"""ARCHIVED: The original check script was archived and the archive folder was later removed (2026-01-03).
The compressed backup for this file was permanently deleted on 2026-01-03 per repository cleanup."""

print("This check script's original content was archived and the compressed backup was permanently deleted on 2026-01-03. Contact maintainers to request restoration.")

def check_websocket_from_redis():
    """Check WebSocket status by looking at Redis data."""
    print("\n" + "=" * 70)
    print("WEBSOCKET STATUS CHECK")
    print("=" * 70)
    
    try:
        import redis
        from config.settings import settings
        
        r = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
            socket_connect_timeout=2
        )
        r.ping()
        
        instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
        latest_price_key = f"price:{instrument_key}:latest"
        latest_ts_key = f"price:{instrument_key}:latest_ts"
        
        price = r.get(latest_price_key)
        ts = r.get(latest_ts_key)
        
        if not price or not ts:
            print("[FAIL] No price data in Redis")
            print("WebSocket is NOT storing ticks")
            return False
        
        # Parse timestamp
        try:
            ts_val = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            if ts_val.tzinfo:
                ts_val = ts_val.replace(tzinfo=None)
            age = (datetime.now() - ts_val).total_seconds()
            
            print(f"[INFO] Latest tick:")
            print(f"  Price: ${float(price):,.2f}")
            print(f"  Timestamp: {ts}")
            print(f"  Age: {age:.1f} seconds")
            
            if age < 10:
                print("\n[OK] Ticks are FRESH - WebSocket is working!")
                return True
            elif age < 60:
                print("\n[WARNING] Ticks are RECENT but not fresh")
                print("WebSocket may be connected but slow")
                return None
            else:
                print("\n[FAIL] Ticks are STALE - WebSocket is NOT working")
                print("WebSocket is either:")
                print("  1. Not connected")
                print("  2. Connected but not receiving messages")
                print("  3. Receiving but not storing")
                return False
        except Exception as e:
            print(f"[ERROR] Could not parse timestamp: {e}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Redis error: {e}")
        return False

def check_tick_count():
    """Check how many ticks are stored."""
    try:
        import redis
        from config.settings import settings
        
        r = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=False,
            socket_connect_timeout=2
        )
        
        # Count tick keys
        tick_keys = r.keys(f"tick:*")
        print(f"\n[INFO] Total tick keys in Redis: {len(tick_keys)}")
        
        if len(tick_keys) > 0:
            print("[OK] Ticks have been stored before")
        else:
            print("[FAIL] No ticks ever stored")
        
        return len(tick_keys)
    except Exception as e:
        print(f"[ERROR] Could not count ticks: {e}")
        return 0

def main():
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    status = check_websocket_from_redis()
    tick_count = check_tick_count()
    
    print("\n" + "=" * 70)
    print("DIAGNOSIS")
    print("=" * 70)
    
    if status is True:
        print("[OK] WebSocket is working - ticks are fresh")
    elif status is False:
        print("[FAIL] WebSocket is NOT working")
        print("\nPossible causes:")
        print("  1. WebSocket never connected")
        print("  2. WebSocket disconnected and not reconnecting")
        print("  3. WebSocket connected but Binance not sending data")
        print("  4. Network/firewall blocking WebSocket")
        print("\nCheck logs for:")
        print("  - '[OK] Connected to Binance WebSocket'")
        print("  - '[TICK #]' messages")
        print("  - Any WebSocket errors")
    else:
        print("[WARNING] WebSocket status unclear")
    
    if tick_count > 0:
        print(f"\n[INFO] {tick_count} ticks stored previously")
        print("WebSocket WAS working before")
    
    print("\n" + "=" * 70 + "\n")

if __name__ == "__main__":
    main()

