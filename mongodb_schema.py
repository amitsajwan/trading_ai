"""MongoDB schema setup for GenAI trading system."""

from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime
import os
from typing import Optional


def get_mongo_client(connection_string: Optional[str] = None):
    """Get MongoDB client connection."""
    if connection_string is None:
        connection_string = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    return MongoClient(connection_string)


def setup_mongodb(db_name: str = "zerodha_trading"):
    """
    Set up MongoDB collections with proper indexes for the trading system.
    
    Collections:
    - ohlc_history: Historical OHLCV data
    - trades_executed: Completed trades with full audit trail
    - agent_decisions: Individual agent outputs and decisions
    - backtest_results: Backtesting performance data
    - strategy_parameters: Strategy configuration and parameters
    - market_events: Market events (RBI announcements, etc.)
    """
    client = get_mongo_client()
    db = client[db_name]

    # 1. OHLC History Collection
    ohlc_history = db["ohlc_history"]
    ohlc_history.create_index([("timestamp", DESCENDING), ("instrument", ASCENDING)])
    ohlc_history.create_index([("instrument", ASCENDING), ("timeframe", ASCENDING)])
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


def get_collection(db, collection_name: str):
    """Get a collection by name."""
    return db[collection_name]


if __name__ == "__main__":
    setup_mongodb()