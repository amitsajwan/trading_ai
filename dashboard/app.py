#!/usr/bin/env python3
"""
Basic Trading Dashboard - FastAPI Application

This provides a web interface for monitoring the trading system.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi import Body
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json
import asyncio
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our modules
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from engine_module.options_strategy_engine import evaluate as eval_options_strategy, RuleConfig

# Start historical data replay for mock tick data
try:
    # Import the data_niftybank modules
    import sys
    project_root = os.path.dirname(os.path.dirname(__file__))
    data_path = os.path.join(project_root, 'data_niftybank', 'src')
    if data_path not in sys.path:
        sys.path.insert(0, data_path)

    from data_niftybank.adapters.redis_store import RedisMarketStore
    from data_niftybank.adapters.historical_replay import HistoricalDataReplay
    import redis

    # Initialize Redis store
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    store = RedisMarketStore(redis_client)

    # Start historical data replay
    replay = HistoricalDataReplay(store, data_source="synthetic")
    replay.start()

except Exception as e:
    print(f"Warning: Could not start historical data replay: {e}")

app = FastAPI(title="Trading Dashboard", version="1.0.0")

# Setup templates and static files
templates_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

templates_dir.mkdir(exist_ok=True)
static_dir.mkdir(exist_ok=True)

templates = Jinja2Templates(directory=str(templates_dir))

# Mount static files
try:
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
except Exception:
    pass  # Static files optional

# In-memory fallback store for paper trades if DB isn't available
PAPER_TRADES_CACHE: list[dict] = []

async def _get_option_ltp(strike: int, option_type: str) -> float | None:
    """Lookup current option premium from options chain for given strike/type."""
    try:
        chain = await options_chain()
        rows = chain.get("chain") or []
        for r in rows:
            if int(r.get("strike", -1)) == int(strike):
                if option_type.upper() == "CE":
                    return float(r.get("ce_ltp")) if r.get("ce_ltp") is not None else None
                if option_type.upper() == "PE":
                    return float(r.get("pe_ltp")) if r.get("pe_ltp") is not None else None
        return None
    except Exception:
        return None

# Automation flags/state
OPTIONS_ALGO_ACTIVE: bool = os.getenv("OPTIONS_ALGO_ENABLED", "0") in ("1", "true", "True")
_options_algo_task: asyncio.Task | None = None
# Algo config (env-overridable)
OPTIONS_MIN_CONF: float = float(os.getenv("OPTIONS_MIN_CONF", "0.6"))
OPTIONS_ENTRY_COOLDOWN_SEC: int = int(os.getenv("OPTIONS_ENTRY_COOLDOWN_SEC", "300"))
OPTIONS_ENTRY_MIN_IMBALANCE: float = float(os.getenv("OPTIONS_ENTRY_MIN_IMBALANCE", "0.05"))
_last_options_entry_ts: float | None = None

def _db_available() -> bool:
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=1000)
        client.admin.command('ping')
        return True
    except Exception:
        return False

def _get_latest_open_trade() -> dict | None:
    if _db_available():
        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017/")
            db = client.zerodha_trading
            col = db.paper_trades
            doc = col.find_one({"status": "open"}, sort=[("timestamp", -1)])
            if doc:
                return doc
        except Exception:
            pass
    open_trades = [t for t in PAPER_TRADES_CACHE if t.get("status") == "open"]
    return open_trades[0] if open_trades else None

def _persist_trade(trade_doc: dict) -> bool:
    try:
        if _db_available():
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017/")
            db = client.zerodha_trading
            col = db.paper_trades
            # Insert a copy to avoid PyMongo mutating the dict with ObjectId
            to_insert = dict(trade_doc)
            col.insert_one(to_insert)
            return True
    except Exception:
        pass
    PAPER_TRADES_CACHE.append(trade_doc)
    return False

def _update_trade(trade_id: str, update_fields: dict) -> bool:
    try:
        if _db_available():
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017/")
            db = client.zerodha_trading
            col = db.paper_trades
            col.update_one({"id": trade_id}, {"$set": update_fields})
            return True
    except Exception:
        pass
    for i, t in enumerate(PAPER_TRADES_CACHE):
        if t.get("id") == trade_id:
            PAPER_TRADES_CACHE[i] = {**t, **update_fields}
            return False
    return False

def add_camel_aliases(data: dict) -> dict:
    """Add camelCase aliases for snake_case keys (for API compatibility)."""
    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        result[key] = add_camel_aliases(value) if isinstance(value, dict) else value
        # Add camelCase version
        camel_key = ''.join(word.capitalize() if i > 0 else word.lower()
                           for i, word in enumerate(key.split('_')))
        if camel_key != key:
            result[camel_key] = result[key]
    return result

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    try:
        # Get system status for template
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            r.ping()
            redis_status = "ok"
        except Exception:
            redis_status = "error"
        
        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
            client.admin.command('ping')
            mongo_status = "ok"
        except Exception:
            mongo_status = "error"
        
        # Check if market is open
        now = datetime.now()
        market_open = (now.weekday() < 5 and  # Monday-Friday
                      now.time() >= datetime.strptime("09:15", "%H:%M").time() and
                      now.time() <= datetime.strptime("15:30", "%H:%M").time())
        
        system_status = {
            "status": "ok" if mongo_status == "ok" and redis_status == "ok" else "degraded",
            "database": mongo_status,
            "cache": redis_status,
            "market_open": market_open
        }
        
        # Paper trading configuration
        paper_trading = {
            "enabled": True,
            "mode": "paper"
        }
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "INSTRUMENT": "BANKNIFTY",
            "timestamp": datetime.now().isoformat(),
            "system_status": system_status,
            "paper_trading": paper_trading
        })
    except Exception as e:
        # Fallback to JSON if template fails
        return JSONResponse(
            status_code=500,
            content={"error": f"Dashboard template error: {str(e)}"}
        )

@app.get("/api/health")
async def health_check():
    """Basic health check endpoint."""
    try:
        # Check database connections
        mongo_status = "unknown"
        redis_status = "unknown"

        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
            client.admin.command('ping')
            mongo_status = "ok"
        except Exception:
            mongo_status = "error"

        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            r.ping()
            redis_status = "ok"
        except Exception:
            redis_status = "error"

        # Check if market is open
        now = datetime.now()
        market_open = (now.weekday() < 5 and  # Monday-Friday
                      now.time() >= datetime.strptime("09:15", "%H:%M").time() and
                      now.time() <= datetime.strptime("15:30", "%H:%M").time())

        return {
            "status": "ok" if mongo_status == "ok" and redis_status == "ok" else "degraded",
            "timestamp": datetime.now().isoformat(),
            "database": mongo_status,
            "cache": redis_status,
            "market_open": market_open,
            "instrument": "BANKNIFTY"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/system-health")
async def system_health():
    """Comprehensive system health check."""
    return await get_system_status()

@app.get("/api/latest-analysis")
async def latest_analysis():
    """Get latest agent analysis."""
    try:
        # Try to get from MongoDB
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017/")
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
        # Try to get real signal from MongoDB
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017/")
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
                "take_profit": latest.get("take_profit")
            }
            return signal_data

        # Mock signal data for demonstration
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "timestamp": datetime.now().isoformat(),
            "reasoning": "Waiting for market analysis",
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None
        }
    except Exception as e:
        return {
            "signal": "ERROR",
            "confidence": 0.0,
            "timestamp": datetime.now().isoformat(),
            "reasoning": f"Error: {str(e)}",
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None
        }

def calculate_vwap(instrument: str = "BANKNIFTY", hours: int = 24) -> float | None:
    """Calculate VWAP from stored tick data in Redis."""
    try:
        import redis
        import json
        from datetime import datetime, timedelta

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
        # Try to get real data from Redis first
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)

        instrument = "BANKNIFTY"
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

        # Fallback to mock data if no real data
        if current_price is None:
            current_price = 45250.50
        if volume_24h is None:
            volume_24h = 12450000
        if vwap is None:
            vwap = 45125.25  # fallback to mock

        # Calculate mock 24h change (in real system this would be from historical data)
        change_24h = 125.50
        change_percent_24h = 0.28

        return {
            "instrument": instrument,
            "current_price": current_price,
            "change_24h": change_24h,
            "change_percent_24h": change_percent_24h,
            "volume_24h": volume_24h,
            "high_24h": 45350.00,  # Would calculate from real data
            "low_24h": 44900.00,   # Would calculate from real data
            "vwap": round(vwap, 2),
            "timestamp": datetime.now().isoformat(),
            "status": "active"
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/metrics/trading")
async def trading_metrics():
    """Get trading performance metrics."""
    try:
        # Mock trading metrics
        return {
            "total_pnl": 2500.50,
            "win_rate": 0.667,
            "total_trades": 3,
            "avg_win": 1250.25,
            "avg_loss": -750.15,
            "largest_win": 1500.00,
            "largest_loss": -800.00,
            "current_streak": 2,
            "best_streak": 3,
            "worst_streak": -1
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/metrics/risk")
async def risk_metrics():
    """Get risk management metrics."""
    try:
        # Mock risk metrics
        return {
            "sharpe_ratio": 1.25,
            "max_drawdown": -1200.50,
            "var_95": -850.25,
            "total_exposure": 45000.00,
            "portfolio_value": 248862.50,
            "daily_var": -425.00,
            "stress_test_loss": -2500.00,
            "correlation_matrix": {
                "BANKNIFTY": 1.0,
                "NIFTY": 0.75
            }
        }
    except Exception as e:
        return {"error": str(e)}

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

@app.get("/api/agent-status")
async def agent_status():
    """Get status of all trading agents."""
    try:
        # Mock agent status
        agents = {
            "technical": {
                "status": "active",
                "last_update": datetime.now().isoformat(),
                "signal": "BUY",
                "confidence": 0.82,
                "indicators": ["RSI", "MACD", "Moving Averages"],
                "summary": {
                    "signal": "BUY",
                    "confidence": 0.82,
                    "reasoning": "RSI at 68.5 (bullish), MACD positive crossover, price above 20-SMA.",
                    "metrics": {
                        "rsi": 68.5,
                        "macd": 125.50,
                        "sma_20": 45125.25
                    }
                }
            },
            "sentiment": {
                "status": "active",
                "last_update": datetime.now().isoformat(),
                "signal": "BUY",
                "confidence": 0.71,
                "indicators": ["News", "Social Media", "Market Mood"],
                "summary": {
                    "signal": "BUY",
                    "confidence": 0.71,
                    "reasoning": "Positive market coverage and improving social momentum support mild bullish bias.",
                    "metrics": {
                        "news_score": 0.74,
                        "social_score": 0.69
                    }
                }
            },
            "macro": {
                "status": "active",
                "last_update": datetime.now().isoformat(),
                "signal": "HOLD",
                "confidence": 0.55,
                "indicators": ["Inflation", "RBI Policy", "GDP"],
                "summary": {
                    "signal": "HOLD",
                    "confidence": 0.55,
                    "reasoning": "Macro environment stable; awaiting next RBI guidance and inflation print.",
                    "metrics": {
                        "inflation_trend": "stable",
                        "policy_bias": "neutral"
                    }
                }
            },
            "risk": {
                "status": "active",
                "last_update": datetime.now().isoformat(),
                "signal": "APPROVED",
                "confidence": 0.88,
                "indicators": ["VaR", "Position Size", "Drawdown"],
                "summary": {
                    "signal": "APPROVED",
                    "confidence": 0.88,
                    "reasoning": "Position sizing within limits; VaR and drawdown acceptable for entry.",
                    "metrics": {
                        "var_95": -850.25,
                        "max_drawdown": -1200.50
                    }
                }
            },
            "execution": {
                "status": "active",
                "last_update": datetime.now().isoformat(),
                "signal": "READY",
                "confidence": 0.95,
                "indicators": ["Slippage", "Market Impact", "Timing"],
                "summary": {
                    "signal": "READY",
                    "confidence": 0.95,
                    "reasoning": "Liquidity sufficient; spreads tight; order flow balanced—good execution window.",
                    "metrics": {
                        "spread": 0.25,
                        "imbalance": 0.15
                    }
                }
            }
        }

        consensus = {
            "signal": "BUY",
            "confidence": 0.78,
            "agents_agreeing": 3,
            "total_agents": 5
        }

        # Build a concise executive summary (Markdown supported in UI)
        def fmt_agent_line(name: str, a: dict) -> str:
            sig = a.get("signal", "HOLD")
            conf = a.get("confidence", 0.0)
            status = a.get("status", "unknown")
            return f"- **{name.title()}**: {sig} ({conf:.0%}) · {status}"

        lines = [
            "### Multi-Agent Executive Summary",
            fmt_agent_line("technical", agents["technical"]),
            fmt_agent_line("sentiment", agents["sentiment"]),
            fmt_agent_line("macro", agents["macro"]),
            fmt_agent_line("risk", agents["risk"]),
            fmt_agent_line("execution", agents["execution"]),
            "",
            f"**Consensus**: {consensus['signal']} ({consensus['confidence']:.0%}) with "
            f"{consensus['agents_agreeing']}/{consensus['total_agents']} agents aligned."
        ]

        executive_summary = "\n".join(lines)

        return {
            "agents": agents,
            "consensus": consensus,
            "executive_summary": executive_summary,
            "last_analysis": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/portfolio")
async def portfolio():
    """Get current portfolio positions."""
    try:
        # Mock portfolio data
        return {
            "positions": [
                {
                    "instrument": "BANKNIFTY",
                    "quantity": 25,
                    "entry_price": 45200.00,
                    "current_price": 45250.50,
                    "unrealized_pnl": 1250.25,
                    "pnl_percentage": 2.77,
                    "market_value": 1131262.50
                }
            ],
            "summary": {
                "total_value": 1131262.50,
                "cash_balance": 488862.50,
                "total_equity": 1620125.00,
                "day_pnl": 1250.25,
                "total_pnl": 1250.25
            }
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/technical-indicators")
async def technical_indicators():
    """Get technical analysis indicators."""
    try:
        # Mock technical indicators
        return {
            "indicators": [
                {
                    "name": "RSI",
                    "value": 68.5,
                    "signal": "bullish",
                    "description": "Relative Strength Index"
                },
                {
                    "name": "MACD",
                    "value": 125.50,
                    "signal": "bullish",
                    "description": "Moving Average Convergence Divergence"
                },
                {
                    "name": "SMA_20",
                    "value": 45125.25,
                    "signal": "above",
                    "description": "20-period Simple Moving Average"
                },
                {
                    "name": "BB_UPPER",
                    "value": 45400.00,
                    "signal": "below",
                    "description": "Bollinger Band Upper"
                },
                {
                    "name": "STOCHASTIC",
                    "value": 75.2,
                    "signal": "bullish",
                    "description": "Stochastic Oscillator"
                }
            ],
            "trend": "bullish",
            "strength": "strong",
            "timestamp": datetime.now().isoformat()
        }
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

# Create basic HTML template
template_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }
        .status {
            padding: 30px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .card {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            border-left: 4px solid #007bff;
        }
        .card.success {
            border-left-color: #28a745;
        }
        .card.warning {
            border-left-color: #ffc107;
        }
        .card.error {
            border-left-color: #dc3545;
        }
        .card h3 {
            margin: 0 0 15px 0;
            color: #333;
            font-size: 1.2em;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }
        .metric:last-child {
            border-bottom: none;
        }
        .value {
            font-weight: bold;
            color: #007bff;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-ok { background: #28a745; }
        .status-error { background: #dc3545; }
        .status-degraded { background: #ffc107; }
        .footer {
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            border-top: 1px solid #dee2e6;
        }
        .refresh-btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin: 10px;
        }
        .refresh-btn:hover {
            background: #0056b3;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Automated Trading Dashboard</h1>
            <p>Real-time monitoring of your AI trading system</p>
            <button class="refresh-btn" onclick="location.reload()">Refresh</button>
        </div>

        <div class="status">
            <div class="card {{ 'success' if system_status.status == 'ok' else 'warning' if system_status.status == 'degraded' else 'error' }}">
                <h3>
                    <span class="status-indicator status-{{ 'ok' if system_status.status == 'ok' else 'error' if system_status.status == 'error' else 'degraded' }}"></span>
                    System Status
                </h3>
                <div class="metric">
                    <span>Overall Health:</span>
                    <span class="value">{{ system_status.status.upper() }}</span>
                </div>
                <div class="metric">
                    <span>Market Status:</span>
                    <span class="value">{{ 'OPEN' if system_status.market_open else 'CLOSED' }}</span>
                </div>
                <div class="metric">
                    <span>Last Update:</span>
                    <span class="value">{{ timestamp }}</span>
                </div>
            </div>

            <div class="card {{ 'success' if system_status.database == 'ok' else 'error' }}">
                <h3>
                    <span class="status-indicator status-{{ 'ok' if system_status.database == 'ok' else 'error' }}"></span>
                    Database
                </h3>
                <div class="metric">
                    <span>MongoDB:</span>
                    <span class="value">{{ system_status.database.upper() }}</span>
                </div>
                <div class="metric">
                    <span>Redis Cache:</span>
                    <span class="value">{{ system_status.cache.upper() }}</span>
                </div>
            </div>

            <div class="card success">
                <h3>
                    <span class="status-indicator status-ok"></span>
                    Trading Modules
                </h3>
                <div class="metric">
                    <span>Data Module:</span>
                    <span class="value">OPERATIONAL</span>
                </div>
                <div class="metric">
                    <span>GenAI Module:</span>
                    <span class="value">OPERATIONAL</span>
                </div>
                <div class="metric">
                    <span>User Module:</span>
                    <span class="value">OPERATIONAL</span>
                </div>
                <div class="metric">
                    <span>Engine Module:</span>
                    <span class="value">OPERATIONAL</span>
                </div>
            </div>

            <div class="card {{ 'success' if system_status.market_open else 'warning' }}">
                <h3>
                    <span class="status-indicator status-{{ 'ok' if system_status.market_open else 'degraded' }}"></span>
                    Market Information
                </h3>
                <div class="metric">
                    <span>Instrument:</span>
                    <span class="value">BANKNIFTY</span>
                </div>
                <div class="metric">
                    <span>Trading Hours:</span>
                    <span class="value">9:15 AM - 3:30 PM IST</span>
                </div>
                <div class="metric">
                    <span>Current Status:</span>
                    <span class="value">{{ 'MARKET OPEN' if system_status.market_open else 'AFTER HOURS' }}</span>
                </div>
            </div>
        </div>

        <div class="footer">
            <p><strong>Automated Trading System v1.0.0</strong></p>
            <p>Multi-agent AI trading with risk management | Real-time monitoring active</p>
            <p>Dashboard running on localhost:8888 | Last updated: {{ timestamp }}</p>
        </div>
    </div>

    <script>
        // Auto-refresh every 30 seconds
        setTimeout(() => {
            location.reload();
        }, 30000);
    </script>
</body>
</html>
"""

# Use the restored template files

@app.get("/api/metrics/llm")
async def llm_metrics():
    """Get LLM provider metrics."""
    try:
        # Check which providers are actually configured
        import os
        configured_providers = {}

        provider_configs = {
            "groq": {
                "rate_limit_per_minute": 30,
                "rate_limit_per_day": 14400,
                "daily_token_quota": 1000000,
                "status": "active" if groq_key else "unavailable"
            },
            "openai": {
                "rate_limit_per_minute": 60,
                "rate_limit_per_day": 10000,
                "daily_token_quota": 100000,
                "status": "available" if openai_key else "unavailable"
            },
            "google": {
                "rate_limit_per_minute": 60,
                "rate_limit_per_day": 1000,
                "daily_token_quota": 1000000,
                "status": "available" if google_key else "unavailable"
            },
            "anthropic": {
                "rate_limit_per_minute": 50,
                "rate_limit_per_day": 5000,
                "daily_token_quota": 100000,
                "status": "available" if anthropic_key else "unavailable"
            }
        }

        # Only include providers that are configured
        for provider_name, config in provider_configs.items():
            if config["status"] != "unavailable":
                configured_providers[provider_name] = {
                    **config,
                    "requests_today": 145 if provider_name == "groq" else 0,  # Mock usage data
                    "requests_per_minute": 2.1 if provider_name == "groq" else 0.0,
                    "tokens_today": 125000 if provider_name == "groq" else 0,
                    "last_error": None,
                    "last_error_time": None
                }

        return {"providers": configured_providers}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/order-flow")
async def order_flow():
    """Get order flow and market depth data."""
    try:
        # Mock order flow data
        return {
            "available": True,
            "last_price": 45245.50,
            "imbalance": 0.15,
            "spread": 0.25,
            "total_depth_bid": 1250,
            "total_depth_ask": 1100,
            "depth_ladder": [
                {"bid_qty": 50, "bid_price": 45245.00, "ask_price": 45245.25, "ask_qty": 45},
                {"bid_qty": 75, "bid_price": 45244.75, "ask_price": 45245.50, "ask_qty": 60},
                {"bid_qty": 100, "bid_price": 45244.50, "ask_price": 45245.75, "ask_qty": 80},
                {"bid_qty": 125, "bid_price": 45244.25, "ask_price": 45246.00, "ask_qty": 90},
                {"bid_qty": 150, "bid_price": 45244.00, "ask_price": 45246.25, "ask_qty": 110}
            ],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"available": False, "error": str(e)}

@app.get("/api/options-chain")
async def options_chain():
    """Get options chain data."""
    try:
        # Mock options chain data
        return {
            "available": True,
            "futures_price": 45250.00,
            "expiry": "2026-01-30",
            "chain": [
                {
                    "strike": 44500,
                    "ce_ltp": 850.50,
                    "ce_oi": 125000,
                    "pe_ltp": 45.25,
                    "pe_oi": 98000,
                    "ce_iv": 22.5,
                    "pe_iv": 18.3,
                    "ce_delta": 0.65,
                    "pe_delta": -0.12
                },
                {
                    "strike": 45000,
                    "ce_ltp": 425.75,
                    "ce_oi": 145000,
                    "pe_ltp": 125.50,
                    "pe_oi": 112000,
                    "ce_iv": 20.8,
                    "pe_iv": 21.2,
                    "ce_delta": 0.45,
                    "pe_delta": -0.28
                },
                {
                    "strike": 45250,
                    "ce_ltp": 225.25,
                    "ce_oi": 180000,
                    "pe_ltp": 285.75,
                    "pe_oi": 165000,
                    "ce_iv": 19.6,
                    "pe_iv": 23.0,
                    "ce_delta": 0.35,
                    "pe_delta": -0.36
                },
                {
                    "strike": 45500,
                    "ce_ltp": 95.50,
                    "ce_oi": 95000,
                    "pe_ltp": 525.25,
                    "pe_oi": 78000,
                    "ce_iv": 18.9,
                    "pe_iv": 24.5,
                    "ce_delta": 0.22,
                    "pe_delta": -0.52
                },
                {
                    "strike": 46000,
                    "ce_ltp": 25.75,
                    "ce_oi": 45000,
                    "pe_ltp": 875.50,
                    "pe_oi": 52000,
                    "ce_iv": 17.2,
                    "pe_iv": 26.8,
                    "ce_delta": 0.10,
                    "pe_delta": -0.65
                }
            ],
            "pcr": 1.15,
            "max_pain": 45250,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"available": False, "error": str(e)}

@app.get("/api/options-strategy")
async def options_strategy():
    """Suggest a simple Options Buy/Sell strategy based on latest signal, options chain and order flow.

    - If signal is BUY: recommend buying ATM/near-ATM CE
    - If signal is SELL: recommend buying ATM/near-ATM PE
    - Incorporates simple order-flow imbalance tilt
    """
    try:
        # Get latest signal
        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017/")
            db = client.zerodha_trading
            collection = db.agent_decisions
            latest = collection.find_one(sort=[("timestamp", -1)])
            if latest:
                signal = str(latest.get("final_signal", "HOLD")).upper()
                confidence = float(latest.get("confidence", 0.5))
            else:
                signal, confidence = "HOLD", 0.0
        except Exception:
            # Fallback
            signal, confidence = "HOLD", 0.0

        # Get options chain and order flow
        chain = await options_chain()
        oflow = await order_flow()

        if not chain or chain.get("available") is False:
            return {"available": False, "reason": "Options chain unavailable"}

        fut_price = chain.get("futures_price")
        strikes = chain.get("chain", [])
        if not fut_price or not strikes:
            return {"available": False, "reason": "Insufficient chain data"}

        # Pick nearest strike to futures price
        def nearest(row):
            try:
                return abs((row.get("strike") or 0) - fut_price)
            except Exception:
                return float("inf")

        strikes_sorted = sorted(strikes, key=nearest)
        best_row = strikes_sorted[0]

        rec = None
        if signal == "BUY":
            rec = {
                "side": "BUY",
                "option_type": "CE",
                "strike": best_row.get("strike"),
                "premium": best_row.get("ce_ltp"),
            }
        elif signal == "SELL":
            rec = {
                "side": "BUY",
                "option_type": "PE",
                "strike": best_row.get("strike"),
                "premium": best_row.get("pe_ltp"),
            }

        if not rec or rec.get("premium") in (None, 0):
            return {
                "available": False,
                "reason": "No actionable premium at nearest strike",
                "signal": signal,
                "confidence": confidence,
            }

        # Simple quantity and risk framing for BANKNIFTY
        lot_size = 25
        premium = float(rec["premium"]) or 0.0

        # Order-flow tilt: if imbalance strongly positive/negative, nudge strike one step
        try:
            imbalance = oflow.get("imbalance")
            imb_val = imbalance.get("imbalance_pct") if isinstance(imbalance, dict) else imbalance
            if imb_val is not None:
                # If bullish (> +0.10), prefer slightly OTM CE; if bearish (< -0.10), slightly OTM PE
                if rec["option_type"] == "CE" and float(imb_val) > 0.10:
                    # pick next higher strike if available
                    for row in strikes_sorted:
                        if row.get("strike", 0) >= rec["strike"] and row.get("ce_ltp"):
                            best_row = row
                            premium = float(row.get("ce_ltp"))
                            rec["strike"] = row.get("strike")
                            rec["premium"] = premium
                            break
                elif rec["option_type"] == "PE" and float(imb_val) < -0.10:
                    # pick next lower strike if available
                    for row in strikes_sorted:
                        if row.get("strike", 0) <= rec["strike"] and row.get("pe_ltp"):
                            best_row = row
                            premium = float(row.get("pe_ltp"))
                            rec["strike"] = row.get("strike")
                            rec["premium"] = premium
                            break
        except Exception:
            pass

        # Risk: 40% stop loss on premium, 40% take profit
        sl_price = round(premium * 0.60, 2)
        tp_price = round(premium * 1.40, 2)

        reasoning = []
        reasoning.append(f"Signal {signal} with confidence {confidence:.0%}")
        reasoning.append("ATM/near-ATM selection based on futures price")
        if oflow and oflow.get("imbalance") is not None:
            reasoning.append("Order-flow imbalance considered for strike tilt")

        return {
            "available": True,
            "timestamp": datetime.now().isoformat(),
            "instrument": "BANKNIFTY",
            "expiry": chain.get("expiry"),
            "recommendation": {
                **rec,
                "quantity": lot_size,
                "stop_loss_price": sl_price,
                "take_profit_price": tp_price,
                "reasoning": "; ".join(reasoning)
            }
        }
    except Exception as e:
        return {"available": False, "error": str(e)}

@app.get("/api/options-strategy-advanced")
async def options_strategy_advanced(min_oi: int = 75000, prefer_expiry: str | None = None, target_delta: float = 0.35, max_iv: float | None = None):
    """Advanced options strategy using rule config.

    Query params:
    - min_oi: minimum open interest per leg
    - prefer_expiry: target expiry date (YYYY-MM-DD)
    """
    try:
        # Determine latest signal
        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017/")
            db = client.zerodha_trading
            collection = db.agent_decisions
            latest = collection.find_one(sort=[("timestamp", -1)])
            signal = str(latest.get("final_signal", "HOLD")).upper() if latest else "HOLD"
        except Exception:
            signal = "HOLD"

        chain = await options_chain()
        oflow = await order_flow()

        cfg = RuleConfig(min_oi=min_oi, prefer_expiry=prefer_expiry, target_delta=target_delta, max_iv=max_iv)
        result = eval_options_strategy(signal, chain, oflow, cfg)
        return result
    except Exception as e:
        return {"available": False, "error": str(e)}

def _generate_trade_id(prefix: str = "PT") -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]}"

@app.post("/api/paper-trade/options")
async def paper_trade_options(payload: dict = Body(None)):
    """Execute a paper trade for the recommended options leg.

    If `payload` is omitted or incomplete, evaluates the advanced options strategy and uses its recommendation.
    Persists to MongoDB when available; otherwise stores in memory.
    """
    try:
        # Obtain recommendation or advanced spread
        rec = None
        expiry = None
        instrument = "BANKNIFTY"
        legs = None
        strategy_type = None
        net_debit = None

        if payload and isinstance(payload, dict):
            if payload.get("recommendation"):
                rec = payload["recommendation"]
            expiry = payload.get("expiry")
            instrument = payload.get("instrument", instrument)
            legs = payload.get("legs")
            strategy_type = payload.get("strategy_type")
            net_debit = payload.get("net_debit")

        if rec is None and legs is None:
            adv = await options_strategy_advanced()
            if adv.get("available"):
                rec = adv.get("recommendation")
                expiry = adv.get("expiry")
                instrument = adv.get("instrument", instrument)
                legs = adv.get("legs")
                strategy_type = adv.get("strategy_type")
                net_debit = adv.get("net_debit")

        if rec is None and not legs:
            return JSONResponse(status_code=400, content={"error": "No recommendation available"})

        # If spread legs provided, create multiple trade docs with a shared group id
        if legs and isinstance(legs, list) and len(legs) > 0:
            group_id = _generate_trade_id("SP")
            trades_created = []
            for leg in legs:
                doc = {
                    "id": _generate_trade_id(),
                    "group_id": group_id,
                    "timestamp": datetime.now().isoformat(),
                    "instrument": instrument,
                    "expiry": expiry,
                    "side": leg.get("side", "BUY"),
                    "option_type": leg.get("option_type"),
                    "strike": leg.get("strike"),
                    "quantity": int(leg.get("quantity", 25)),
                    "entry_price": float(leg.get("premium", 0.0)),
                    "exit_price": None,
                    "pnl": 0.0,
                    "status": "open",
                    "meta": {
                        "reasoning": (rec or {}).get("reasoning"),
                        "strategy_type": strategy_type,
                        "net_debit": net_debit
                    }
                }
                _persist_trade(doc)
                trades_created.append(doc)
            return {"ok": True, "group_id": group_id, "trades": trades_created}

        # Single-leg fallback
        trade_doc = {
            "id": _generate_trade_id(),
            "timestamp": datetime.now().isoformat(),
            "instrument": instrument,
            "expiry": expiry,
            "side": rec.get("side", "BUY"),
            "option_type": rec.get("option_type"),
            "strike": rec.get("strike"),
            "quantity": int(rec.get("quantity", 25)),
            "entry_price": float(rec.get("premium", 0.0)),
            "exit_price": None,
            "pnl": 0.0,
            "status": "open",
            "meta": {"reasoning": rec.get("reasoning")}
        }
        persisted = _persist_trade(trade_doc)
        return {"ok": True, "trade": trade_doc, "persisted": persisted}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/paper-trade/close")
async def paper_trade_close(payload: dict = Body(None)):
    """Close a paper trade.

    Payload (optional): { id: string, exit_price?: float }
    If `id` is omitted, closes the latest open trade. If `exit_price` is omitted,
    attempts to fetch current premium from options chain using stored strike/type.
    Computes P&L: BUY -> (exit-entry)*qty, SELL -> (entry-exit)*qty.
    """
    try:
        target_id = (payload or {}).get("id") if isinstance(payload, dict) else None
        explicit_exit = (payload or {}).get("exit_price") if isinstance(payload, dict) else None

        # Try MongoDB first
        doc = None
        used_db = False
        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017/")
            db = client.zerodha_trading
            col = db.paper_trades
            if target_id:
                doc = col.find_one({"id": target_id})
            else:
                doc = col.find_one({"status": "open"}, sort=[("timestamp", -1)])
            used_db = doc is not None
        except Exception:
            used_db = False

        # Fallback to in-memory cache
        if doc is None:
            open_trades = [t for t in PAPER_TRADES_CACHE if t.get("status") == "open"]
            if target_id:
                match = [t for t in PAPER_TRADES_CACHE if t.get("id") == target_id]
                doc = match[0] if match else (open_trades[0] if open_trades else None)
            else:
                doc = open_trades[0] if open_trades else None

        if doc is None:
            return JSONResponse(status_code=404, content={"error": "No open trade found"})

        # Determine exit price
        exit_price = explicit_exit
        if exit_price is None:
            strike = doc.get("strike")
            opt_type = doc.get("option_type")
            if strike and opt_type:
                exit_price = await _get_option_ltp(strike, opt_type)
        if exit_price is None:
            return JSONResponse(status_code=400, content={"error": "Exit price unavailable"})

        exit_price = float(exit_price)
        entry = float(doc.get("entry_price", 0.0))
        qty = int(doc.get("quantity", 0))
        side = str(doc.get("side", "BUY")).upper()
        pnl = (exit_price - entry) * qty if side == "BUY" else (entry - exit_price) * qty

        # Update document
        update_fields = {
            "exit_price": exit_price,
            "exit_timestamp": datetime.now().isoformat(),
            "pnl": round(pnl, 2),
            "status": "closed"
        }

        persisted = _update_trade(doc.get("id"), update_fields)

        return {"ok": True, "id": doc.get("id"), "pnl": round(pnl, 2), "persisted": persisted}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/options-algo/state")
async def options_algo_state():
    return {"active": OPTIONS_ALGO_ACTIVE}

@app.post("/api/options-algo/state")
async def options_algo_toggle(payload: dict = Body(None)):
    global OPTIONS_ALGO_ACTIVE, _options_algo_task
    desired = bool((payload or {}).get("active", False))
    OPTIONS_ALGO_ACTIVE = desired
    if desired and _options_algo_task is None:
        _options_algo_task = asyncio.create_task(_options_algo_loop())
    elif not desired and _options_algo_task:
        _options_algo_task.cancel()
        _options_algo_task = None
    return {"active": OPTIONS_ALGO_ACTIVE}

async def _options_algo_loop():
    try:
        while OPTIONS_ALGO_ACTIVE:
            now = datetime.now()
            market_open = (now.weekday() < 5 and
                           now.time() >= datetime.strptime("09:15", "%H:%M").time() and
                           now.time() <= datetime.strptime("15:30", "%H:%M").time())
            if market_open:
                open_trade = _get_latest_open_trade()
                if open_trade:
                    strike = open_trade.get("strike")
                    opt_type = open_trade.get("option_type")
                    ltp = await _get_option_ltp(strike, opt_type) if (strike and opt_type) else None
                    if ltp is not None:
                        entry = float(open_trade.get("entry_price", 0.0))
                        meta = open_trade.get("meta", {})
                        sl = float(meta.get("stop_loss_price", entry * 0.6))
                        tp = float(meta.get("take_profit_price", entry * 1.4))
                        side = str(open_trade.get("side", "BUY")).upper()
                        should_close = False
                        if side == "BUY":
                            if ltp <= sl or ltp >= tp:
                                should_close = True
                        else:
                            if ltp >= sl or ltp <= tp:
                                should_close = True
                        if should_close:
                            qty = int(open_trade.get("quantity", 0))
                            pnl = (ltp - entry) * qty if side == "BUY" else (entry - ltp) * qty
                            _update_trade(open_trade.get("id"), {
                                "exit_price": float(ltp),
                                "exit_timestamp": datetime.now().isoformat(),
                                "pnl": round(pnl, 2),
                                "status": "closed"
                            })
                else:
                    # Entry gating: respect cooldown and signal confidence & order-flow sign
                    import time
                    global _last_options_entry_ts
                    if _last_options_entry_ts is not None:
                        if time.time() - _last_options_entry_ts < OPTIONS_ENTRY_COOLDOWN_SEC:
                            await asyncio.sleep(15)
                            continue

                    # Check latest signal and confidence
                    latest = await latest_signal()
                    sig = str(latest.get("signal", "HOLD")).upper()
                    conf = float(latest.get("confidence", 0.0) or 0.0)
                    # Require actionable signal and minimum confidence
                    if sig not in ("BUY", "SELL") or conf < OPTIONS_MIN_CONF:
                        await asyncio.sleep(15)
                        continue

                    # Require supportive order-flow imbalance sign
                    oflow = await order_flow()
                    imb = oflow.get("imbalance")
                    imb_val = imb.get("imbalance_pct") if isinstance(imb, dict) else imb
                    if imb_val is None:
                        await asyncio.sleep(15)
                        continue
                    if sig == "BUY" and float(imb_val) < OPTIONS_ENTRY_MIN_IMBALANCE:
                        await asyncio.sleep(15)
                        continue
                    if sig == "SELL" and float(imb_val) > -OPTIONS_ENTRY_MIN_IMBALANCE:
                        await asyncio.sleep(15)
                        continue

                    # Evaluate advanced strategy and open
                    adv = await options_strategy_advanced()
                    if adv.get("available") and adv.get("recommendation"):
                        rec = adv["recommendation"]
                        trade_doc = {
                            "id": _generate_trade_id(),
                            "timestamp": datetime.now().isoformat(),
                            "instrument": adv.get("instrument", "BANKNIFTY"),
                            "expiry": adv.get("expiry"),
                            "side": rec.get("side", "BUY"),
                            "option_type": rec.get("option_type"),
                            "strike": rec.get("strike"),
                            "quantity": rec.get("quantity", 25),
                            "entry_price": float(rec.get("premium", 0.0)),
                            "exit_price": None,
                            "pnl": 0.0,
                            "status": "open",
                            "meta": {
                                "reasoning": rec.get("reasoning"),
                                "stop_loss_price": rec.get("stop_loss_price"),
                                "take_profit_price": rec.get("take_profit_price")
                            }
                        }
                        _persist_trade(trade_doc)
                        _last_options_entry_ts = time.time()
            await asyncio.sleep(15)
    except asyncio.CancelledError:
        pass

@app.on_event("startup")
async def _start_algo_if_enabled():
    global _options_algo_task
    if OPTIONS_ALGO_ACTIVE and _options_algo_task is None:
        _options_algo_task = asyncio.create_task(_options_algo_loop())

if __name__ == "__main__":
    import uvicorn
    print("Starting dashboard on http://localhost:8888")
    uvicorn.run(app, host="0.0.0.0", port=8888)
