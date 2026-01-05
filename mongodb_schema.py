"""MongoDB schema setup for GenAI trading system."""

from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime
import os
from typing import Optional

# Backwards-compatible global db name (some tests rely on overriding this variable)
trading_system = "zerodha_trading"


def get_mongo_client(connection_string: Optional[str] = None):
    """Get MongoDB client connection."""
    if connection_string is None:
        connection_string = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    return MongoClient(connection_string)


def setup_mongodb(db_name: Optional[str] = None):
    """
    Set up MongoDB collections with proper indexes for the trading system.

    This function accepts an optional `db_name`. If `db_name` is not provided
    it falls back to the module-level `trading_system` name for backwards
    compatibility with older tests that monkeypatch that global variable.
    """
    # Backwards compatible: allow tests to override module-level `trading_system`
    db_name = db_name or trading_system
    client = get_mongo_client()
    db = client[db_name]

    # 1. OHLC History Collection
    ohlc_history = db["ohlc_history"]
    ohlc_history.create_index([("instrument", ASCENDING), ("timestamp", DESCENDING)])
    ohlc_history.create_index([("instrument", ASCENDING), ("timeframe", ASCENDING), ("timestamp", DESCENDING)])
    ohlc_history.create_index("timestamp", expireAfterSeconds=2592000)  # 30-day TTL for raw ticks
    
    # 2. Trades Executed Collection
    trades_executed = db["trades_executed"]
    trades_executed.create_index("trade_id", unique=True)
    trades_executed.create_index([("entry_timestamp", DESCENDING)])
    trades_executed.create_index([("exit_timestamp", DESCENDING)])
    trades_executed.create_index("status")  # OPEN, CLOSED, CANCELLED
    
    # 3. Agent Decisions Collection
    agent_decisions = db["agent_decisions"]
    agent_decisions.create_index([("timestamp", DESCENDING)])
    agent_decisions.create_index([("agent_name", ASCENDING), ("timestamp", DESCENDING)])
    agent_decisions.create_index("trade_id")  # Link to trades
    
    # 4. Backtest Results Collection
    backtest_results = db["backtest_results"]
    backtest_results.create_index([("backtest_id", ASCENDING), ("timestamp", DESCENDING)])
    backtest_results.create_index("strategy_name")
    
    # 5. Strategy Parameters Collection
    strategy_parameters = db["strategy_parameters"]
    strategy_parameters.create_index("strategy_name", unique=True)
    strategy_parameters.create_index([("updated_at", DESCENDING)])
    
    # 6. Market Events Collection
    market_events = db["market_events"]
    market_events.create_index([("event_timestamp", DESCENDING)])
    market_events.create_index("event_type")  # RBI_ANNOUNCEMENT, NEWS, MACRO_DATA, etc.
    market_events.create_index("source")
    
    # 7. Historical Data (legacy - keep for backward compatibility)
    historical_data = db["historical_data"]
    historical_data.create_index("timestamp")
    
    # 8. Trade Logs (legacy - keep for backward compatibility)
    trade_logs = db["trade_logs"]
    trade_logs.create_index("trade_id", unique=True)
    
    print(f"MongoDB schema setup completed for database: {db_name}")
    print(f"Collections created: ohlc_history, trades_executed, agent_decisions, "
          f"backtest_results, strategy_parameters, market_events")
    
    return db


def apply_schema_validators(db):
    """Apply JSON schema validators to critical collections to prevent schema drift."""
    try:
        # Trades executed validator
        trades_validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["trade_id", "instrument", "entry_timestamp", "entry_price", "quantity", "status"],
                "properties": {
                    "trade_id": {"bsonType": "string"},
                    "instrument": {"bsonType": "string"},
                    "entry_timestamp": {"bsonType": ["date", "string"]},
                    "entry_price": {"bsonType": ["double", "int", "long"]},
                    "exit_price": {"bsonType": ["double", "int", "long", "null"]},
                    "quantity": {"bsonType": ["int", "double", "long"]},
                    "status": {"bsonType": "string"}
                }
            }
        }
        db.command({"collMod": "trades_executed", "validator": trades_validator, "validationLevel": "moderate"})
    except Exception as e:
        print(f"Failed to apply trades_executed validator: {e}")

    try:
        agent_validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["timestamp", "instrument", "agent_decisions"],
                "properties": {
                    "timestamp": {"bsonType": ["date", "string"]},
                    "instrument": {"bsonType": "string"},
                    "agent_decisions": {"bsonType": "object"}
                }
            }
        }
        db.command({"collMod": "agent_decisions", "validator": agent_validator, "validationLevel": "moderate"})
    except Exception as e:
        print(f"Failed to apply agent_decisions validator: {e}")


def migrate_trades_add_defaults(db):
    """Backfill missing fields in trades_executed with sensible defaults."""
    trades = db.get_collection("trades_executed")
    # Ensure status exists
    trades.update_many({"status": {"$exists": False}}, {"$set": {"status": "OPEN"}})
    # Ensure entry_price exists
    trades.update_many({"entry_price": {"$exists": False}}, {"$set": {"entry_price": 0}})
    # Ensure quantity exists
    trades.update_many({"quantity": {"$exists": False}}, {"$set": {"quantity": 0}})
    # Normalize timestamp fields to ISO strings if necessary (best-effort)
    from datetime import datetime
    for t in trades.find({}):
        if "entry_timestamp" in t and not isinstance(t["entry_timestamp"], str):
            try:
                trades.update_one({"_id": t["_id"]}, {"$set": {"entry_timestamp": t["entry_timestamp"].isoformat()}})
            except Exception:
                pass


def migrate_agents_instrument_field(db, instrument):
    """Ensure agent_decisions documents have correct instrument field for filtering."""
    agents = db.get_collection("agent_decisions")
    agents.update_many({"instrument": {"$exists": False}}, {"$set": {"instrument": instrument}})


def get_collection(db, collection_name: str):
    """Get a collection by name."""
    return db[collection_name]


if __name__ == "__main__":
    setup_mongodb()