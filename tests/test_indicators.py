import redis
import json
import os
from datetime import datetime, timezone

def main():
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))

    try:
        r = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        r.ping()
        print("[OK] Redis connection successful")
    except Exception as e:
        print(f"[ERROR] Redis connection failed: {e}")
        return

    # Create test indicator data
    indicator_data = {
        "rsi_14": 65.23,
        "macd_value": 45.67,
        "macd_signal": 42.15,
        "macd_histogram": 3.52,
        "adx_14": 28.45,
        "atr_14": 156.78,
        "sma_20": 59850.25,
        "ema_12": 59912.34,
        "ema_26": 59866.67,
        "bb_upper": 60200.50,
        "bb_middle": 59850.25,
        "bb_lower": 59500.00,
        "stoch_k": 72.34,
        "stoch_d": 68.92,
        "williams_r": -27.66,
        "cci_20": 125.67,
        "mfi_14": 68.45,
        "volume_sma": 1250000,
        "price_change_pct": 0.85,
        "volatility": 12.34,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    print("\n[TEST] Publishing test indicators to Redis...")
    print(f'Indicator data: {json.dumps(indicator_data, indent=2)}')

    try:
        # Publish to indicators channel (type-specific)
        r.publish("indicators:BANKNIFTY:INDEX", json.dumps(indicator_data))
        print(f"[OK] Published to indicators:BANKNIFTY:INDEX: {r.pubsub_numsub('indicators:BANKNIFTY:INDEX')[0][1]} subscribers")

        print("[SUCCESS] Test indicators sent! Check browser console for WebSocket reception.")
    except Exception as e:
        print(f"[ERROR] Failed to publish indicators to Redis: {e}")

if __name__ == "__main__":
    main()