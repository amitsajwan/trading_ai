#!/usr/bin/env python3
"""Emit a single mock tick using the MockProvider and write to Redis.
Useful for smoke-testing mock provider + Redis integration.
"""
import json
import sys
try:
    from providers.factory import get_provider
except Exception:
    # fallback if tests run with different paths
    import sys, os
    sys.path.insert(0, os.getcwd())
    from providers.factory import get_provider

from config import get_config
import redis


def main():
    p = get_provider('mock')
    symbols = [f"{get_config().instrument_exchange}:{get_config().instrument_symbol}"]
    quotes = p.quote(symbols)
    q = quotes[symbols[0]]

    cfg = get_config()
    r = redis.Redis(**cfg.get_redis_config())

    # Normalize quote to dict if needed
    if hasattr(q, 'to_dict'):
        qd = q.to_dict()
    else:
        qd = q

    # Write keys similar to collectors
    price_key = cfg.redis_price_key
    depth_key = f"depth:{cfg.instrument_key}"

    r.set(f"{price_key}:last_price", qd['last_price'])
    r.set(f"{price_key}:latest_ts", qd.get('timestamp') or '')
    r.set(f"{price_key}:quote", json.dumps(qd))

    depth = qd.get('depth', {})
    r.set(f"{depth_key}:buy", json.dumps(depth.get('buy', [])))
    r.set(f"{depth_key}:sell", json.dumps(depth.get('sell', [])))
    r.set(f"{depth_key}:timestamp", qd.get('timestamp') or '')
    r.set(f"{depth_key}:total_bid_qty", sum(d.get('quantity', 0) for d in depth.get('buy', [])))
    r.set(f"{depth_key}:total_ask_qty", sum(d.get('quantity', 0) for d in depth.get('sell', [])))

    print("Wrote mock tick to Redis:")
    print(f"  {price_key}:last_price =", r.get(f"{price_key}:last_price"))
    print(f"  {price_key}:latest_ts =", r.get(f"{price_key}:latest_ts"))
    print(f"  {depth_key}:buy =", r.get(f"{depth_key}:buy"))


if __name__ == '__main__':
    main()
