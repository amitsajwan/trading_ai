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

    # Create test market tick data
    tick_data = {
        "instrument": "BANKNIFTY",
        "last_price": 60123.45,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "volume": 1250,
        "oi": 45000
    }

    print("\n[TEST] Publishing test market tick to Redis...")
    print(f'Tick data: {json.dumps(tick_data, indent=2)}')

    try:
        # Publish to market tick channel
        r.publish("market:tick:BANKNIFTY", json.dumps(tick_data))
        print(f"[OK] Published to market:tick:BANKNIFTY: {r.pubsub_numsub('market:tick:BANKNIFTY')[0][1]} subscribers")

        print("[SUCCESS] Test market tick sent! Check browser console for WebSocket reception.")
    except Exception as e:
        print(f"[ERROR] Failed to publish market tick to Redis: {e}")

if __name__ == "__main__":
    main()