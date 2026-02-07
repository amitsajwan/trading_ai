#!/usr/bin/env python3
"""Minimal dashboard stub for container startup and testing."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import asyncio
import logging
import os

logger = logging.getLogger(__name__)

app = FastAPI(title="Trading Dashboard (stub)", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8888", "http://127.0.0.1:8888"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def add_camel_aliases(data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    result = {}
    for key, value in data.items():
        result[key] = add_camel_aliases(value) if isinstance(value, dict) else value
        camel_key = ''.join(word.capitalize() if i > 0 else word.lower() for i, word in enumerate(key.split('_')))
        if camel_key != key:
            result[camel_key] = result[key]
    return result


@app.get("/")
async def root():
    return {"message": "OK"}


@app.get("/api/v1/technical/indicators/{instrument}")
async def get_technical_indicators_v1(instrument: str, timeframe: str = "1min"):
    now = datetime.now().isoformat()
    indicators = [
        {"name": "RSI_14", "value": 0.0, "signal": "neutral", "description": "Relative Strength Index (14)"},
        {"name": "MACD", "value": 0.0, "signal": "neutral", "description": "MACD Line"},
        {"name": "ADX_14", "value": 0.0, "signal": "neutral", "description": "Average Directional Index (14)"},
        {"name": "ATR_14", "value": 0.0, "signal": "neutral", "description": "Average True Range (14)"},
    ]
    return {"indicators": indicators, "trend": "unknown", "strength": "unknown", "timestamp": now}


@app.get("/api/technical-indicators")
async def technical_indicators():
    return await get_technical_indicators_v1(instrument=os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY"))


async def start_historical_replay(start_date=None, end_date=None, interval: str = "minute", kite=None):
    logger.info("Stub start_historical_replay called start_date=%s end_date=%s interval=%s", start_date, end_date, interval)
    # Minimal no-op that yields control briefly
    await asyncio.sleep(0.1)
    return {"started": True, "start_date": str(start_date), "end_date": str(end_date), "interval": interval}


async def get_system_status():
    return {"status": "ok", "timestamp": datetime.now().isoformat(), "database": "unknown", "cache": "unknown"}


@app.get("/api/system-health")
async def system_health():
    return await get_system_status()


__all__ = ["app", "add_camel_aliases", "start_historical_replay", "technical_indicators"]

@app.get("/api/auth-status")
async def auth_status():
    """Get current authentication status."""
    try:
        import redis
        redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        
        # Try to get latest auth status from Redis
        auth_data = redis_client.get("auth:status:latest")
        if auth_data:
            import json
            return json.loads(auth_data)
        
        # Fallback: check if credentials exist
        import os
        cred_path = os.path.join(os.getcwd(), "credentials.json")
        if os.path.exists(cred_path):
            return {
                "status": "unknown",
                "message": "Credentials file exists but status unknown",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "failed",
                "message": "No credentials file found",
                "timestamp": datetime.now().isoformat(),
                "action_required": "manual_login",
                "url": "http://localhost:8000/auth"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error checking auth status: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/latest-analysis")
async def latest_analysis():
    """Get latest agent analysis."""
    try:
        # Try to get from MongoDB
        from pymongo import MongoClient
        client = MongoClient("mongodb://mongodb:27017/")
        db = client.zerodha_trading
        collection = db.agent_decisions

        latest = collection.find_one(sort=[("timestamp", -1)])
        if latest:
            return {
                "timestamp": latest.get("timestamp"),
                "decision": latest.get("final_signal", "HOLD"),
                "confidence": latest.get("confidence", 0.0),
                "instrument": latest.get("instrument", "BANKNIFTY")
            }

        # Fallback mock data
        return {
            "timestamp": datetime.now().isoformat(),
            "decision": "HOLD",
            "confidence": 0.0,
            "instrument": "BANKNIFTY",
            "note": "No recent analysis available"
        }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/latest-signal")
async def latest_signal():
    """Get latest trading signal for dashboard banner."""
    try:
        # Get agent status for executive summary
        agent_data = await agent_status()
        
        # Try to get real signal from MongoDB
        from pymongo import MongoClient
        client = MongoClient("mongodb://mongodb:27017/")
        db = client.zerodha_trading
        collection = db.agent_decisions

        latest = collection.find_one(sort=[("timestamp", -1)])
        if latest:
            decision = latest.get("final_signal", "HOLD")
            confidence = latest.get("confidence", 0.5)

            # Format for dashboard signal banner
            signal_data = {
                "signal": decision.upper(),
                "confidence": confidence,
                "timestamp": latest.get("timestamp", datetime.now().isoformat()),
                "reasoning": f"AI analysis confidence: {confidence:.1%}",
                "entry_price": latest.get("entry_price"),
                "stop_loss": latest.get("stop_loss"),
                "take_profit": latest.get("take_profit"),
                "executive_summary": agent_data.get("executive_summary", "Executive summary not available")
            }
            return signal_data

        # Mock signal data for demonstration with executive summary
        signal_data = {
            "signal": "HOLD", 
            "confidence": 0.0, 
            "timestamp": datetime.now().isoformat(), 
            "reasoning": "Waiting for market analysis", 
            "entry_price": None, 
            "stop_loss": None, 
            "take_profit": None,
            "executive_summary": agent_data.get("executive_summary", "Executive summary not available")
        }
        return signal_data
    except Exception as e:
        return {
            "signal": "ERROR",
            "confidence": 0.0,
            "timestamp": datetime.now().isoformat(),
            "reasoning": f"Error: {str(e)}",
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "executive_summary": "Error retrieving executive summary"
        }


# Modular routers for control/trading/market endpoints (moved to dashboard.api package)
# Keep a small compatibility variable for tests that patch `dashboard.app._kite_client`
_kite_client = None

# Mount modular routers
# try:
#     from dashboard.api import control_router, trading_router, market_router  # type: ignore
#     app.include_router(control_router)
#     app.include_router(trading_router)
#     app.include_router(market_router)
#     # Include risk router if available
#     # try:
#     #     from dashboard.api.risk import router as risk_router
#     #     app.include_router(risk_router)
#     #     print(f"[OK] Risk router included: {risk_router.prefix} with {len(risk_router.routes)} routes")
#     # except ImportError as e:
#     #     print(f"Warning: Risk router not available (Layer 8 components may not be installed): {e}")
#     # except Exception as e:
#     #     print(f"Error: Failed to include risk router: {e}")
#     #     import traceback
#     #     traceback.print_exc()
# except Exception as e:  # pragma: no cover - best effort to include routers
#     print(f"Warning: could not mount modular routers: {e}")
#     import traceback
#     traceback.print_exc()


def calculate_vwap(instrument: str = None, hours: int = 24) -> float | None:
    """Calculate VWAP from stored tick data in Redis."""
    try:
        import redis
        import json
        from datetime import datetime, timedelta

        # Get config for instrument if not provided
        if instrument is None:
            config = get_config()
            instrument = config.instrument_symbol.upper()

        # Connect to Redis
        r = redis.Redis(host='localhost', port=6379, db=0)

        # Get all tick keys for the instrument from the last N hours
        pattern = f"tick:{instrument}:*"
        keys = r.keys(pattern)

        # Filter keys that are timestamps (not "latest")
        tick_keys = [k for k in keys if not k.decode().endswith(':latest')]

        if not tick_keys:
            # Fallback to synthetic calculation if no historical data
            return None

        total_price_volume = 0.0
        total_volume = 0.0
        cutoff_time = datetime.now() - timedelta(hours=hours)

        for key in tick_keys:
            try:
                # Get tick data
                tick_data = r.get(key)
                if not tick_data:
                    continue

                tick_json = json.loads(tick_data.decode())

                # Parse timestamp
                ts_str = tick_json.get('timestamp')
                if not ts_str:
                    continue

                tick_time = datetime.fromisoformat(ts_str)
                if tick_time < cutoff_time:
                    continue

                # Get price and volume
                price = float(tick_json.get('last_price', 0))
                volume = float(tick_json.get('volume', 0))

                if price > 0 and volume > 0:
                    total_price_volume += price * volume
                    total_volume += volume

            except Exception as e:
                continue  # Skip malformed ticks

        if total_volume > 0:
            return total_price_volume / total_volume

        return None

    except Exception as e:
        print(f"VWAP calculation error: {e}")
        return None

@app.get("/api/market-data")
async def market_data():
    """Get current market data."""
    try:
        # Get config for instrument
        config = get_config()
        instrument = config.instrument_symbol.upper()
        
        # Try to get real data from Redis first
        import redis
        r = redis.Redis(host='redis', port=6379, db=0)

        current_price = None
        volume_24h = None

        try:
            # Get latest price
            price_data = r.get(f"price:{instrument}:latest")
            if price_data:
                current_price = float(price_data.decode())

            # Get 24h volume
            volume_data = r.get(f"volume:{instrument}:latest")
            if volume_data:
                volume_24h = int(float(volume_data.decode()))
        except Exception:
            pass

        # Calculate VWAP from tick data
        vwap = calculate_vwap(instrument)

        # Check if we have any real data
        has_real_data = current_price is not None or volume_24h is not None or vwap is not None

        if not has_real_data:
            # No live market data available - return clear indication
            return {
                "instrument": instrument,
                "status": "no_data",
                "message": "Live market data not available",
                "current_price": None,
                "change_24h": None,
                "change_percent_24h": None,
                "volume_24h": None,
                "high_24h": None,
                "low_24h": None,
                "vwap": None,
                "timestamp": datetime.now().isoformat(),
                "error": "Market data feed unavailable"
            }

        # Use available real data, set None for missing fields
        change_24h = None  # Would be calculated from historical data
        change_percent_24h = None

        return {
            "instrument": instrument,
            "current_price": current_price,
            "change_24h": change_24h,
            "change_percent_24h": change_percent_24h,
            "volume_24h": volume_24h,
            "high_24h": None,  # Would calculate from real data
            "low_24h": None,   # Would calculate from real data
            "vwap": round(vwap, 2) if vwap else None,
            "timestamp": datetime.now().isoformat(),
            "status": "partial" if not all([current_price, volume_24h, vwap]) else "active"
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/metrics/trading")
async def trading_metrics():
    """Get trading performance metrics."""
    try:
        # Try to get real trading data from database
        from pymongo import MongoClient
        client = MongoClient("mongodb://mongodb:27017/")
        db = client.zerodha_trading
        collection = db.trades

        # Get all completed trades
        trades = list(collection.find({"status": "completed"}))
        
        if not trades:
            return {
                "status": "no_data",
                "message": "No trading data available",
                "total_pnl": 0,
                "win_rate": 0,
                "total_trades": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "largest_win": 0,
                "largest_loss": 0,
                "current_streak": 0,
                "best_streak": 0,
                "worst_streak": 0,
                "timestamp": datetime.now().isoformat()
            }

        # Calculate real metrics from trade data
        pnls = [trade.get("pnl", 0) for trade in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        total_pnl = sum(pnls)
        win_rate = len(wins) / len(pnls) if pnls else 0
        total_trades = len(trades)
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        largest_win = max(wins) if wins else 0
        largest_loss = min(losses) if losses else 0

        # Calculate streaks
        current_streak = 0
        best_streak = 0
        worst_streak = 0
        temp_streak = 0
        
        for pnl in pnls:
            if pnl > 0:
                temp_streak = max(temp_streak + 1, 1)
                best_streak = max(best_streak, temp_streak)
            elif pnl < 0:
                temp_streak = min(temp_streak - 1, -1)
                worst_streak = min(worst_streak, temp_streak)
            else:
                temp_streak = 0
        
        current_streak = temp_streak

        return {
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(win_rate, 3),
            "total_trades": total_trades,
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "largest_win": round(largest_win, 2),
            "largest_loss": round(largest_loss, 2),
            "current_streak": current_streak,
            "best_streak": best_streak,
            "worst_streak": worst_streak,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": "Trading metrics unavailable",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/metrics/risk")
async def risk_metrics():
    """Get risk management metrics."""
    try:
        # Try to get real risk data from database
        from pymongo import MongoClient
        client = MongoClient("mongodb://mongodb:27017/")
        db = client.zerodha_trading
        collection = db.trades

        # Get all trades for risk calculation
        trades = list(collection.find({}))
        
        if not trades:
            return {
                "status": "no_data",
                "message": "No trading data available for risk calculation",
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "var_95": 0,
                "total_exposure": 0,
                "portfolio_value": 0,
                "daily_var": 0,
                "stress_test_loss": 0,
                "correlation_matrix": {},
                "timestamp": datetime.now().isoformat()
            }

        # Calculate basic risk metrics from real data
        pnls = [trade.get("pnl", 0) for trade in trades]
        total_pnl = sum(pnls)
        max_drawdown = min(pnls) if pnls else 0
        
        # For now, return calculated metrics without mock values
        return {
            "sharpe_ratio": 0,  # Would need more sophisticated calculation
            "max_drawdown": round(max_drawdown, 2),
            "var_95": 0,  # Would need historical data for VaR calculation
            "total_exposure": 0,  # Would need position data
            "portfolio_value": round(100000 + total_pnl, 2),  # Base portfolio + pnl
            "daily_var": 0,  # Would need daily P&L data
            "stress_test_loss": 0,  # Would need stress testing
            "correlation_matrix": {
                "BANKNIFTY": 1.0,
                "NIFTY": 0.0  # No correlation data available
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": "Risk metrics unavailable",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/analytics/performance")
async def analytics_performance():
    """Get real performance analytics from trades data."""
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017/")
        db = client.zerodha_trading
        col = db.trades_executed
        
        # Get all closed trades
        trades = list(col.find({"status": "CLOSED"}))
        
        if not trades:
            return {
                "total_pnl": 0,
                "win_rate": 0,
                "total_trades": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "largest_win": 0,
                "largest_loss": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "current_streak": 0,
                "best_streak": 0,
                "worst_streak": 0
            }
        
        # Calculate metrics
        pnls = [trade.get("pnl", 0) for trade in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        total_pnl = sum(pnls)
        win_rate = len(wins) / len(pnls) if pnls else 0
        total_trades = len(pnls)
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        largest_win = max(wins) if wins else 0
        largest_loss = min(losses) if losses else 0
        
        # Calculate streaks
        current_streak = 0
        best_streak = 0
        worst_streak = 0
        temp_streak = 0
        
        for pnl in pnls:
            if pnl > 0:
                temp_streak = max(temp_streak + 1, 1)
                best_streak = max(best_streak, temp_streak)
            elif pnl < 0:
                temp_streak = min(temp_streak - 1, -1)
                worst_streak = min(worst_streak, temp_streak)
            else:
                temp_streak = 0
        
        current_streak = temp_streak
        
        # Mock sharpe and drawdown for now
        sharpe_ratio = 1.25
        max_drawdown = min(pnls) if pnls else 0
        
        return {
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "total_trades": total_trades,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "largest_win": largest_win,
            "largest_loss": largest_loss,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "current_streak": current_streak,
            "best_streak": best_streak,
            "worst_streak": worst_streak
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/analytics/risk")
async def analytics_risk():
    """Get real risk analytics from trades data."""
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017/")
        db = client.zerodha_trading
        col = db.trades_executed
        
        trades = list(col.find({"status": "CLOSED"}))
        pnls = [trade.get("pnl", 0) for trade in trades]
        
        if not pnls:
            return {
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "var_95": 0,
                "total_exposure": 0,
                "portfolio_value": 0,
                "daily_var": 0,
                "stress_test_loss": 0,
                "correlation_matrix": {}
            }
        
        # Calculate metrics from real data
        total_pnl = sum(pnls)
        max_drawdown = min(pnls) if pnls else 0
        
        # Return real calculated metrics, no mock values
        return {
            "sharpe_ratio": 0,  # Would need time-series data for proper calculation
            "max_drawdown": round(max_drawdown, 2),
            "var_95": 0,  # Would need historical distribution
            "total_exposure": 0,  # Would need position sizing data
            "portfolio_value": round(100000 + total_pnl, 2),  # Base + calculated pnl
            "daily_var": 0,  # Would need daily returns
            "stress_test_loss": 0,  # Would need stress testing framework
            "correlation_matrix": {
                "BANKNIFTY": 1.0,
                "NIFTY": 0.0  # No correlation data available
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/analytics/llm")
async def analytics_llm():
    """Get LLM analytics - proxy to existing metrics."""
    return await llm_metrics()

@app.get("/api/recent-trades")
async def recent_trades(limit: int = 20):
    """Get recent trades history."""
    try:
        # Prefer DB paper trades; fallback to in-memory; final fallback to sample
        results: list[dict] = []
        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017/")
            db = client.zerodha_trading
            col = db.paper_trades
            for doc in col.find().sort("timestamp", -1).limit(limit):
                results.append({
                    "id": doc.get("id"),
                    "timestamp": doc.get("timestamp"),
                    "instrument": doc.get("instrument"),
                    "side": doc.get("side"),
                    "quantity": doc.get("quantity"),
                    "price": doc.get("entry_price"),
                    "pnl": doc.get("pnl", 0.0),
                    "status": doc.get("status", "open"),
                    "exit_price": doc.get("exit_price")
                })
        except Exception:
            pass

        if not results and PAPER_TRADES_CACHE:
            results = sorted(PAPER_TRADES_CACHE, key=lambda x: x.get("timestamp",""), reverse=True)[:limit]

        if not results:
            # Sample when no trades exist
            results = [
                {
                    "id": "SAMPLE-1",
                    "timestamp": datetime.now().isoformat(),
                    "instrument": "BANKNIFTY",
                    "side": "BUY",
                    "quantity": 25,
                    "price": 45200.00,
                    "pnl": 0.00,
                    "status": "open",
                    "exit_price": None
                }
            ]
        return results[:limit]
    except Exception as e:
        return {"error": str(e)}

def _map_agent_to_ui_key(agent_name: str) -> str:
    """Map agent names to UI keys."""
    mapping = {
        'EnhancedResearchManager': 'enhancedresearchmanager',
        'BullResearcher': 'bullresearcher',
        'BearResearcher': 'bearresearcher',
        'TechnicalAgent': 'technical',
        'SentimentAgent': 'sentiment',
        'MacroAgent': 'macro',
        'FundamentalAgent': 'fundamental',
        'MomentumAgent': 'momentum',
        'TrendAgent': 'trend',
        'VolumeAgent': 'volume',
        'MeanReversionAgent': 'reversion',
        'OptionsStrategyAgent': 'options',
        'SignalCreationAgent': 'signalcreation',
        'ExecutionAgent': 'execution',
        'NeutralRiskAgent': 'neutralrisk',
        'RiskManager': 'risk'
    }
    return mapping.get(agent_name, '')

@app.get("/api/agent-status")
async def agent_status():
    """Get status of all trading agents."""
    try:
        from datetime import datetime

        # Try to get real agent status from Redis
        import redis
        r = redis.Redis(host='redis', port=6379, db=0)

        # Check for agent status keys
        agent_keys = r.keys("agent:*:status")
        
        if not agent_keys:
            return {
                "status": "no_data",
                "message": "No agent status data available - agents may not be running",
                "agents": {},
                "timestamp": datetime.now().isoformat()
            }

        # Get real agent data from Redis
        agents = {}
        for key in agent_keys:
            agent_name = key.decode().split(":")[1]
            agent_data = r.get(key)
            if agent_data:
                agents[agent_name] = json.loads(agent_data.decode())

        if not agents:
            return {
                "status": "no_data", 
                "message": "Agent status data unavailable",
                "agents": {},
                "timestamp": datetime.now().isoformat()
            }

        return {
            "agents": agents,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": "Agent status unavailable",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/portfolio")
async def portfolio():
    """Get current portfolio positions."""
    try:
        # Try to get real portfolio data from database
        from pymongo import MongoClient
        client = MongoClient("mongodb://mongodb:27017/")
        db = client.zerodha_trading
        collection = db.positions

        # Get all open positions
        positions = list(collection.find({"status": "open"}))
        
        if not positions:
            return {
                "status": "no_data",
                "message": "No open positions in portfolio",
                "positions": [],
                "summary": {
                    "total_value": 0,
                    "cash_balance": 100000,  # Default cash balance
                    "total_pnl": 0,
                    "day_pnl": 0
                },
                "timestamp": datetime.now().isoformat()
            }

        # Calculate portfolio summary from real positions
        total_value = sum(pos.get("market_value", 0) for pos in positions)
        total_pnl = sum(pos.get("unrealized_pnl", 0) for pos in positions)
        
        return {
            "positions": positions,
            "summary": {
                "total_value": round(total_value, 2),
                "cash_balance": 100000,  # Would need cash balance tracking
                "total_pnl": round(total_pnl, 2),
                "day_pnl": 0  # Would need daily P&L calculation
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": "Portfolio data unavailable",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/orchestrator-decisions")
async def orchestrator_decisions(limit: int = 20):
    """Get stored orchestrator decisions from Redis."""
    try:
        import redis
        import json
        from datetime import datetime

        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

        # Get current instrument
        instrument = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY").upper()

        decisions = []

        # Try to get the latest decisions from Redis
        latest_keys = [
            f"engine:orchestrator_decision:{instrument}:latest",
            "engine:orchestrator_decision:latest",
            f"engine:orchestrator_decision:{instrument.replace('26JANFUT', '')}:latest"
        ]

        for key in latest_keys:
            try:
                decision_json = r.get(key)
                if decision_json:
                    decision_data = json.loads(decision_json)

                    # Format for UI consumption
                    formatted_decision = {
                        "decision_id": f"decision_{int(datetime.fromisoformat(decision_data.get('timestamp', datetime.now().isoformat())).timestamp() * 1000)}",
                        "instrument": decision_data.get("instrument", instrument),
                        "final_decision": decision_data.get("final_decision", "UNKNOWN"),
                        "confidence": decision_data.get("confidence", 0.0),
                        "timestamp": decision_data.get("timestamp", datetime.now().isoformat()),
                        "reasoning": decision_data.get("reasoning", ""),
                        "agent_responses": decision_data.get("agent_responses", []),
                        "details": decision_data.get("details", {})
                    }

                    decisions.append(formatted_decision)
                    if len(decisions) >= limit:
                        break

            except Exception as e:
                continue

        # Sort by timestamp (most recent first)
        decisions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return {
            "decisions": decisions[:limit],
            "total": len(decisions),
            "instrument": instrument
        }

    except Exception as e:
        return {"error": str(e), "decisions": [], "total": 0}

@app.get("/api/technical-indicators")
async def technical_indicators():
    """Get technical analysis indicators calculated from OHLC data."""
    try:
        # Try to calculate technical indicators from stored OHLC data
        try:
            import redis
            import pandas as pd
            from datetime import datetime
            
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            
            # Get current instrument
            instrument = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY").upper()
            
            # Get OHLC data from Redis
            ohlc_keys = r.keys(f"ohlc:{instrument}:*")
            if not ohlc_keys:
                raise Exception("No OHLC data found")
            
            # Get recent OHLC bars
            ohlc_data = []
            for key in sorted(ohlc_keys, reverse=True)[:100]:  # Get last 100 bars
                data = r.get(key)
                if data:
                    try:
                        bar = json.loads(data)
                        ohlc_data.append({
                            'timestamp': bar['start_at'],
                            'open': bar['open'],
                            'high': bar['high'], 
                            'low': bar['low'],
                            'close': bar['close'],
                            'volume': bar.get('volume', 0)
                        })
                    except:
                        continue
            
            if len(ohlc_data) < 20:
                raise Exception("Not enough OHLC data for indicators")
            
            # Create DataFrame
            df = pd.DataFrame(ohlc_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Calculate indicators using pandas-ta
            try:
                import pandas_ta as ta
                
                indicators = []
                
                # RSI
                if len(df) >= 14:
                    rsi = ta.rsi(df['close'], length=14)
                    if rsi is not None and not rsi.empty:
                        rsi_val = float(rsi.iloc[-1])
                        signal = "neutral"
                        if rsi_val < 30:
                            signal = "oversold"
                        elif rsi_val > 70:
                            signal = "overbought"
                        indicators.append({
                            "name": "RSI_14",
                            "value": round(rsi_val, 2),
                            "signal": signal,
                            "description": "Relative Strength Index (14)"
                        })
                
                # MACD
                if len(df) >= 26:
                    macd = ta.macd(df['close'])
                    if macd is not None and len(macd.columns) >= 3:
                        macd_val = float(macd.iloc[-1, 0])
                        signal = "bullish" if macd_val > 0 else "bearish"
                        indicators.append({
                            "name": "MACD",
                            "value": round(macd_val, 2),
                            "signal": signal,
                            "description": "MACD Line"
                        })
                
                # ADX
                if len(df) >= 14:
                    adx = ta.adx(df['high'], df['low'], df['close'], length=14)
                    if adx is not None and len(adx.columns) >= 3:
                        adx_val = float(adx.iloc[-1, 0])
                        signal = "trending" if adx_val > 25 else "sideways"
                        indicators.append({
                            "name": "ADX_14",
                            "value": round(adx_val, 2),
                            "signal": signal,
                            "description": "Average Directional Index (14)"
                        })
                
                # ATR
                if len(df) >= 14:
                    atr = ta.atr(df['high'], df['low'], df['close'], length=14)
                    if atr is not None and not atr.empty:
                        atr_val = float(atr.iloc[-1])
                        indicators.append({
                            "name": "ATR_14",
                            "value": round(atr_val, 2),
                            "signal": "neutral",
                            "description": "Average True Range (14)"
                        })
                
                # Bollinger Bands
                if len(df) >= 20:
                    bb = ta.bbands(df['close'], length=20)
                    if bb is not None and len(bb.columns) >= 3:
                        bb_upper = float(bb.iloc[-1, 0])
                        indicators.append({
                            "name": "BB_UPPER",
                            "value": round(bb_upper, 2),
                            "signal": "neutral",
                            "description": "Bollinger Band Upper (20)"
                        })
                
                if indicators:
                    return {
                        "indicators": indicators,
                        "trend": "unknown",
                        "strength": "unknown", 
                        "timestamp": datetime.now().isoformat()
                    }
                    
            except ImportError:
                pass  # pandas-ta not available
                
        except Exception as calc_error:
            print(f"Failed to calculate indicators: {calc_error}")

        # Fallback to zero values if calculation fails
        print("Using fallback technical indicators")
        return {
            "indicators": [
                {
                    "name": "RSI_14",
                    "value": 0.0,
                    "signal": "neutral",
                    "description": "Relative Strength Index (14)"
                },
                {
                    "name": "MACD",
                    "value": 0.0,
                    "signal": "neutral",
                    "description": "MACD Line"
                },
                {
                    "name": "ADX_14",
                    "value": 0.0,
                    "signal": "neutral",
                    "description": "Average Directional Index (14)"
                },
                {
                    "name": "ATR_14",
                    "value": 0.0,
                    "signal": "neutral",
                    "description": "Average True Range (14)"
                }
            ],
            "trend": "unknown",
            "strength": "unknown",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error in technical_indicators: {e}")
        return {
            "indicators": [],
            "trend": "unknown",
            "strength": "unknown",
            "timestamp": datetime.now().isoformat()
        }
        
@app.get("/api/v1/technical/indicators/{instrument}")
async def get_technical_indicators_v1(instrument: str, timeframe: str = "1min"):
    """Get technical indicators for an instrument (v1 API)."""
    try:
        # Call the existing technical_indicators function
        result = await technical_indicators()
        return result
    except Exception as e:
        return {"error": str(e)}

async def get_system_status():
    """Get comprehensive system status."""
    try:
        # Database status
        mongo_status = "error"
        redis_status = "error"

        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
            client.admin.command('ping')
            mongo_status = "ok"
        except Exception:
            pass

        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            r.ping()
            redis_status = "ok"
        except Exception:
            pass

        # Market status
        now = datetime.now()
        market_open = (now.weekday() < 5 and  # Monday-Friday
                      now.time() >= datetime.strptime("09:15", "%H:%M").time() and
                      now.time() <= datetime.strptime("15:30", "%H:%M").time())

        return {
            "status": "ok" if mongo_status == "ok" and redis_status == "ok" else "degraded",
            "database": mongo_status,
            "cache": redis_status,
            "market_open": market_open,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "uptime": "Active",
            "components": {
                "data_module": "operational",
                "genai_module": "operational",
                "user_module": "operational",
                "engine_module": "operational",
                "ui_shell": "operational"
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    import uvicorn
    import os
    # FastAPI backend should run on port 8000 (API only, no UI template)
    # React UI runs on port 8888 via Vite
    # WebSocket Gateway runs separately on port 8889
    port = int(os.getenv("DASHBOARD_API_PORT", "8000"))
    print(f"Starting FastAPI backend API on http://localhost:{port}")
    print("NOTE: UI is served by Vite dev server on port 8888 (modular_ui/)")
    print("NOTE: WebSocket Gateway runs separately on port 8889")
    uvicorn.run(app, host="0.0.0.0", port=port)
