import argparse
import os
from typing import Optional
from pymongo import MongoClient
import redis


def get_redis(host: str, port: int, db: int = 0) -> redis.Redis:
    return redis.Redis(host=host, port=port, db=db, decode_responses=True)


def get_mongo(uri: str, db_name: str) -> MongoClient:
    client = MongoClient(uri)
    return client[db_name]


def purge_redis_for_instrument(r: redis.Redis, instrument_key: str):
    patterns = [
        f"price:{instrument_key}:latest",
        f"price:{instrument_key}:latest_ts",
        f"volume:{instrument_key}:latest",
        f"vwap:{instrument_key}:latest",
        f"oi:{instrument_key}:latest",
        f"tick:{instrument_key}:*",
        f"ohlc:{instrument_key}:*",
        f"ohlc_sorted:{instrument_key}:*",
        f"snapshot:{instrument_key}:latest",
    ]
    total = 0
    for pat in patterns:
        keys = r.keys(pat)
        if keys:
            r.delete(*keys)
            total += len(keys)
    print(f"Deleted {total} Redis keys for {instrument_key}")


def purge_mongo(db, collections: Optional[list] = None):
    cols = collections or ["ohlc_history", "trades_executed", "agent_decisions", "alerts"]
    for name in cols:
        try:
            n = db[name].delete_many({}).deleted_count
            print(f"Dropped {n} documents from {name}")
        except Exception as e:
            print(f"Skip {name}: {e}")


def main():
    ap = argparse.ArgumentParser(description="Reset Redis and Mongo for a given instrument")
    ap.add_argument("instrument", help="Instrument symbol, e.g., 'NIFTY BANK' or 'BANKNIFTY'")
    ap.add_argument("--force", action="store_true", help="Proceed without confirmation")
    ap.add_argument("--redis-host", default=os.getenv("REDIS_HOST", "localhost"))
    ap.add_argument("--redis-port", type=int, default=int(os.getenv("REDIS_PORT", "6379")))
    ap.add_argument("--mongodb-uri", default=os.getenv("MONGODB_URI", "mongodb://localhost:27017/"))
    ap.add_argument("--mongodb-db", default=os.getenv("MONGODB_DB_NAME", "zerodha_trading"))
    args = ap.parse_args()

    sym = args.instrument.upper().replace(" ", "")
    # Normalize to NIFTYBANK for Bank Nifty keys
    instr_key = "NIFTYBANK" if ("BANKNIFTY" in sym or "NIFTYBANK" in sym) else "NIFTY"

    if not args.force:
        ans = input(f"This will delete Redis keys and clear Mongo docs for {instr_key}. Continue? [y/N] ")
        if ans.strip().lower() != "y":
            print("Aborted")
            return

    r = get_redis(args.redis_host, args.redis_port)
    purge_redis_for_instrument(r, instr_key)

    db = get_mongo(args.mongodb_uri, args.mongodb_db)
    purge_mongo(db)

    print("Reset complete.")


if __name__ == "__main__":
    main()
