import logging
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import csv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

try:
    from config.settings import settings
except Exception:  # pragma: no cover - fallback when settings not ready
    settings = None

try:
    from mongodb_schema import get_mongo_client, get_collection
except Exception:  # pragma: no cover - fallback for tests without DB
    get_mongo_client = None
    get_collection = None

try:
    from monitoring.system_health import healthchecker
except Exception:  # pragma: no cover
    healthchecker = None

try:
    from data.market_memory import MarketMemory
    marketmemory = MarketMemory()
except Exception:  # pragma: no cover - Redis optional
    marketmemory = None

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "index.html"
STATIC_PATH = BASE_DIR / "static"


app = FastAPI(title="Trading Dashboard Pro", version="1.0")

# Mount static files
if STATIC_PATH.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_PATH)), name="static")

# Setup templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def add_camel_aliases(data: Any) -> Any:
    """Add camelCase and underscore-less aliases for API consumers."""
    def camel(s: str) -> str:
        parts = s.split("_")
        return parts[0] + "".join(p.title() for p in parts[1:])

    if isinstance(data, list):
        return [add_camel_aliases(item) for item in data]
    if isinstance(data, dict):
        out: Dict[str, Any] = {}
        for k, v in data.items():
            out[k] = add_camel_aliases(v)
            key_no_underscore = k.replace("_", "")
            key_camel = camel(k)
            # Preserve original first; add aliases only if missing
            if key_no_underscore not in out:
                out[key_no_underscore] = out[k]
            if key_camel not in out:
                out[key_camel] = out[k]
        return out
    return data


# ---------- helpers ----------

def _load_index_html() -> str:
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text(encoding="utf-8")
    return "<html><body><h1>Dashboard template missing</h1></body></html>"


def _safe_db():
    if not get_mongo_client or not settings:
        raise RuntimeError("Database not configured")
    mongo_client = get_mongo_client()
    db = mongo_client[settings.mongodb_db_name]
    return mongo_client, db


# ---------- routes ----------

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    instrument_symbol = settings.instrument_symbol if settings and hasattr(settings, "instrument_symbol") else "NIFTY"
    return templates.TemplateResponse("index.html", {
        "request": request,
        "INSTRUMENT": instrument_symbol
    })


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/metrics/llm")
async def get_llm_metrics():
    providers: List[Dict[str, Any]] = []
    try:
        from agents.llm_provider_manager import get_llm_manager

        manager = get_llm_manager()
        if manager and getattr(manager, "providers", None):
            for name, cfg in manager.providers.items():
                def _get(field: str, default=None):
                    return cfg.get(field, default) if hasattr(cfg, "get") else getattr(cfg, field, default)

                status_raw = _get("status", "unknown")
                status = status_raw.value if hasattr(status_raw, "value") else str(status_raw)
                tokens_today = _get("tokens_today", 0)
                daily_limit = _get("daily_limit", 0) or _get("daily_token_quota", 0) or 0
                providers.append({
                    "name": name,
                    "status": status,
                    "tokens_today": tokens_today,
                    "daily_limit": daily_limit,
                    "usage_percent": round((tokens_today / daily_limit) * 100, 2) if daily_limit else 0,
                    "last_check": _get("last_check"),
                    "consecutive_failures": _get("consecutive_failures", 0),
                    "total_calls": _get("total_calls", 0),
                    "has_key": bool(_get("api_key")),
                    "model": _get("model", "N/A"),
                    "priority": _get("priority", 99)
                })
    except Exception as exc:
        logger.debug(f"LLM metrics fallback: {exc}")

    providers = sorted(providers, key=lambda p: p.get("priority", 99))
    summary = {
        "total_providers": len(providers),
        "healthy_providers": sum(1 for p in providers if p.get("status") in {"available", "healthy"}),
        "unhealthy_providers": sum(1 for p in providers if p.get("status") not in {"available", "healthy"}),
        "total_tokens_today": sum(p.get("tokens_today", 0) for p in providers),
        "health_percentage": round((sum(1 for p in providers if p.get("status") in {"available", "healthy"}) / len(providers) * 100) if providers else 0, 2)
    }
    return {"providers": providers, "summary": summary, "selection_strategy": "hash", "usage_counts": {}}


@app.get("/api/latest-signal")
async def get_latest_signal() -> Dict[str, Any]:
    try:
        _, db = _safe_db()
        trades_collection = get_collection(db, "trades_executed")
        latest_trade = trades_collection.find_one(sort=[("entry_timestamp", -1)])
        if latest_trade:
            resp = {
                "signal": latest_trade.get("signal", "HOLD"),
                "position_size": latest_trade.get("quantity", 0),
                "entry_price": latest_trade.get("entry_price", 0),
                "stop_loss": latest_trade.get("stop_loss", 0),
                "take_profit": latest_trade.get("take_profit", 0),
                "confidence": latest_trade.get("confidence", 0.0),
                "reasoning": latest_trade.get("portfolio_manager_reasoning", "") or "Based on multi-agent analysis"
            }
            return add_camel_aliases(resp)
    except Exception as exc:
        logger.error(f"latest signal failed: {exc}")
    return add_camel_aliases({
        "signal": "HOLD",
        "position_size": 0,
        "entry_price": 0,
        "stop_loss": 0,
        "take_profit": 0,
        "confidence": 0.0,
        "reasoning": "Waiting for market analysis"
    })


@app.get("/api/market-data")
async def get_market_data() -> Dict[str, Any]:
    current_price = None
    volume_24h = None
    high_24h = None
    low_24h = None
    vwap = None
    change_24h = None
    
    try:
        if marketmemory and marketmemory._redis_available:
            instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper() if settings else "INSTRUMENT"
            current_price = marketmemory.get_current_price(instrument_key)
    except Exception as exc:
        logger.debug(f"redis price fallback: {exc}")

    try:
        _, db = _safe_db()
        ohlc_collection = get_collection(db, "ohlc_history")
        
        # Get current price from latest OHLC if not from Redis
        if not current_price:
            last_ohlc = ohlc_collection.find_one({"instrument": settings.instrument_symbol}, sort=[("timestamp", -1)])
            if last_ohlc and last_ohlc.get("close"):
                current_price = last_ohlc["close"]
        
        # Calculate 24h metrics from OHLC history
        now = datetime.now()
        twenty_four_hours_ago = now - timedelta(hours=24)
        recent_ohlc = list(ohlc_collection.find({
            "instrument": settings.instrument_symbol,
            "timestamp": {"$gte": twenty_four_hours_ago}
        }).sort("timestamp", 1))
        
        if recent_ohlc:
            # Calculate 24h high, low, volume
            high_24h = max(candle.get("high", 0) for candle in recent_ohlc)
            low_24h = min(candle.get("low", float('inf')) for candle in recent_ohlc if candle.get("low", 0) > 0)
            if low_24h == float('inf'):
                low_24h = None
            
            # Calculate 24h volume
            volume_24h = sum(candle.get("volume", 0) for candle in recent_ohlc)
            
            # Calculate VWAP (Volume Weighted Average Price)
            total_volume = 0
            vwap_sum = 0
            for candle in recent_ohlc:
                vol = candle.get("volume", 0)
                if vol > 0:
                    typical_price = (candle.get("high", 0) + candle.get("low", 0) + candle.get("close", 0)) / 3
                    vwap_sum += typical_price * vol
                    total_volume += vol
            if total_volume > 0:
                vwap = vwap_sum / total_volume
            
            # Calculate 24h price change
            if current_price and recent_ohlc:
                first_price = recent_ohlc[0].get("open", 0)
                if first_price > 0:
                    change_24h = ((current_price - first_price) / first_price) * 100
                    
    except Exception as exc:
        logger.debug(f"24h metrics calculation failed: {exc}")

    market_open = True
    if settings and not getattr(settings, "market_24_7", True):
        try:
            open_time = datetime.strptime(settings.market_open_time, "%H:%M:%S").time()
            close_time = datetime.strptime(settings.market_close_time, "%H:%M:%S").time()
            now = datetime.now().time()
            market_open = open_time <= now <= close_time
        except Exception:
            market_open = True

    return {
        "currentprice": current_price,
        "marketopen": market_open,
        "instrumentname": getattr(settings, "instrument_name", "Unknown") if settings else "Unknown",
        "instrumentsymbol": getattr(settings, "instrument_symbol", "INSTRUMENT") if settings else "INSTRUMENT",
        "datasource": "Redis" if current_price else "MongoDB",
        "timestamp": datetime.now().isoformat(),
        "volume24h": volume_24h,
        "high24h": high_24h,
        "low24h": low_24h,
        "vwap": vwap,
        "change24h": change_24h
    }


@app.get("/api/recent-trades")
async def get_recent_trades(limit: int = Query(10, ge=1, le=100)) -> List[Dict[str, Any]]:
    try:
        _, db = _safe_db()
        trades_collection = get_collection(db, "trades_executed")
        trades = list(trades_collection.find({}, sort=[("entry_timestamp", -1)]).limit(limit))
        for trade in trades:
            if "_id" in trade:
                trade["_id"] = str(trade["_id"])
        return [add_camel_aliases(t) for t in trades]
    except Exception as exc:
        logger.error(f"recent trades failed: {exc}")
        return []


@app.get("/metrics/trading")
async def get_trading_metrics() -> Dict[str, Any]:
    try:
        _, db = _safe_db()
        trades_collection = get_collection(db, "trades_executed")
        all_trades = list(trades_collection.find({}))
        closed = [t for t in all_trades if t.get("status") == "CLOSED"]
        open_trades = [t for t in all_trades if t.get("status") == "OPEN"]
        if not closed:
            return add_camel_aliases({
                "total_trades": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "average_pnl": 0,
                "open_positions": len(open_trades)
            })
        profitable = sum(1 for t in closed if t.get("pnl", 0) > 0)
        total_pnl = sum(t.get("pnl", 0) for t in closed)
        return add_camel_aliases({
            "total_trades": len(closed),
            "profitable_trades": profitable,
            "win_rate": (profitable / len(closed) * 100) if closed else 0,
            "total_pnl": total_pnl,
            "average_pnl": total_pnl / len(closed) if closed else 0,
            "open_positions": len(open_trades)
        })
    except Exception as exc:
        logger.error(f"trading metrics failed: {exc}")
        return add_camel_aliases({"total_trades": 0, "win_rate": 0, "total_pnl": 0, "average_pnl": 0, "open_positions": 0})


@app.get("/metrics/risk")
async def get_risk_metrics() -> Dict[str, Any]:
    try:
        _, db = _safe_db()
        trades_collection = get_collection(db, "trades_executed")
        closed = list(trades_collection.find({"status": "CLOSED"}))
        open_trades = list(trades_collection.find({"status": "OPEN"}))
        
        if not closed:
            # Calculate metrics for open positions only
            total_exposure = sum(abs(t.get("entry_price", 0) * t.get("quantity", 0)) for t in open_trades)
            portfolio_value = sum(t.get("pnl", 0) for t in open_trades)
            
            return {
                "sharpe_ratio": 0.0, 
                "max_drawdown": 0.0, 
                "win_loss_ratio": 0.0, 
                "avg_win_size": 0.0,
                "var_95": 0.0,
                "total_exposure": total_exposure,
                "portfolio_value": portfolio_value
            }
            
        profitable = [t for t in closed if t.get("pnl", 0) > 0]
        losing = [t for t in closed if t.get("pnl", 0) < 0]
        win_loss_ratio = len(profitable) / len(losing) if losing else 0
        avg_win = sum(t.get("pnl", 0) for t in profitable) / len(profitable) if profitable else 0
        
        cumulative = 0
        peak = 0
        max_dd = 0
        for t in closed:
            cumulative += t.get("pnl", 0)
            peak = max(peak, cumulative)
            max_dd = max(max_dd, peak - cumulative)
            
        total_pnl = sum(t.get("pnl", 0) for t in closed)
        mean = total_pnl / len(closed)
        variance = sum((t.get("pnl", 0) - mean) ** 2 for t in closed) / len(closed)
        std = variance ** 0.5 if variance > 0 else 0
        sharpe = (mean / std) if std else 0
        
        # Calculate VaR (95% confidence) - 5th percentile of PnL distribution
        pnl_values = sorted([t.get("pnl", 0) for t in closed])
        var_index = int(len(pnl_values) * 0.05)
        var_95 = abs(pnl_values[var_index]) if pnl_values else 0
        
        # Calculate total exposure (sum of all open position values)
        total_exposure = sum(abs(t.get("entry_price", 0) * t.get("quantity", 0)) for t in open_trades)
        
        # Calculate portfolio value (total PnL + open positions value)
        open_pnl = sum(t.get("pnl", 0) for t in open_trades)
        portfolio_value = total_pnl + open_pnl
        
        return {
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(max_dd, 2),
            "win_loss_ratio": round(win_loss_ratio, 2),
            "avg_win_size": round(avg_win, 2),
            "var_95": round(var_95, 2),
            "total_exposure": round(total_exposure, 2),
            "portfolio_value": round(portfolio_value, 2)
        }
    except Exception as exc:
        logger.error(f"risk metrics failed: {exc}")
        return {
            "sharpe_ratio": 0.0, 
            "max_drawdown": 0.0, 
            "win_loss_ratio": 0.0, 
            "avg_win_size": 0.0,
            "var_95": 0.0,
            "total_exposure": 0.0,
            "portfolio_value": 0.0
        }


@app.get("/api/latest-analysis")
async def get_latest_analysis() -> Dict[str, Any]:
    try:
        _, db = _safe_db()
        analysis_collection = get_collection(db, "agent_decisions")
        latest = analysis_collection.find_one({"instrument": getattr(settings, "instrument_symbol", None)}, sort=[("timestamp", -1)])
        if latest and latest.get("agent_decisions"):
            agent_decisions = latest.get("agent_decisions")
            if isinstance(agent_decisions, str):
                try:
                    agent_decisions = json.loads(agent_decisions)
                except Exception:
                    agent_decisions = {}
            portfolio_output = agent_decisions.get("portfolio_manager", {}) if isinstance(agent_decisions, dict) else {}
            resp = {
                "agents": agent_decisions,
                "timestamp": latest.get("timestamp"),
                "final_signal": latest.get("final_signal", "HOLD"),
                "trend_signal": latest.get("trend_signal", "NEUTRAL"),
                "current_price": latest.get("current_price"),
                "bullish_score": portfolio_output.get("bullish_score"),
                "bearish_score": portfolio_output.get("bearish_score"),
                "scenario_paths": portfolio_output.get("scenario_paths", {}),
                "agent_explanations": latest.get("agent_explanations", []),
                "executive_summary": latest.get("executive_summary", "")
            }
            return add_camel_aliases(resp)
    except Exception as exc:
        logger.error(f"latest analysis failed: {exc}")
    return add_camel_aliases({"agents": {}, "message": "No analysis available yet."})


@app.get("/api/technical-indicators")
async def get_technical_indicators() -> Dict[str, Any]:
    try:
        if not marketmemory:
            return add_camel_aliases({"indicators": {}, "error": "Market memory not available"})
        instrument_key = getattr(settings, "instrument_symbol", "INSTRUMENT").replace("-", "").replace(" ", "").upper() if settings else "INSTRUMENT"
        ohlc_data = marketmemory.get_recent_ohlc(instrument_key, "5min", 50)
        if not ohlc_data or len(ohlc_data) < 2:
            return add_camel_aliases({"indicators": {}, "message": "Insufficient OHLC data"})
        import pandas as pd
        df = pd.DataFrame(ohlc_data)
        required_cols = ["open", "high", "low", "close"]
        if not all(col in df.columns for col in required_cols):
            return add_camel_aliases({"indicators": {}, "error": "Missing OHLC columns"})
        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=required_cols)
        if df.empty:
            return add_camel_aliases({"indicators": {}, "error": "No valid OHLC data"})
        indicators: Dict[str, Any] = {}
        current_price = float(df["close"].iloc[-1])
        if len(df) >= 5:
            sma_5 = df["close"].tail(5).mean()
            indicators["sma_5"] = float(sma_5)
            indicators["sma_5_signal"] = "ABOVE" if current_price > sma_5 else "BELOW"
        if len(df) >= 10:
            sma_10 = df["close"].tail(10).mean()
            indicators["sma_10"] = float(sma_10)
            indicators["sma_10_signal"] = "ABOVE" if current_price > sma_10 else "BELOW"
        if len(df) >= 20:
            sma_20 = df["close"].tail(20).mean()
            indicators["sma_20"] = float(sma_20)
            indicators["sma_20_signal"] = "ABOVE" if current_price > sma_20 else "BELOW"
        if len(df) >= 14:
            try:
                import pandas_ta as ta
                rsi = ta.rsi(df["close"], length=14)
                if not rsi.empty:
                    indicators["rsi"] = float(rsi.iloc[-1])
                    indicators["rsi_status"] = "OVERBOUGHT" if indicators["rsi"] > 70 else "OVERSOLD" if indicators["rsi"] < 30 else "NEUTRAL"
            except Exception as exc:
                logger.debug(f"RSI calculation failed: {exc}")
        if len(df) >= 26:
            try:
                import pandas_ta as ta
                macd = ta.macd(df["close"])
                if not macd.empty:
                    macd_line = macd["MACD_12_26_9"].iloc[-1]
                    signal_line = macd["MACDs_12_26_9"].iloc[-1]
                    indicators["macd"] = float(macd_line)
                    indicators["macd_signal"] = float(signal_line)
                    indicators["macd_status"] = "BULLISH" if macd_line > signal_line else "BEARISH" if macd_line < signal_line else "NEUTRAL"
            except Exception as exc:
                logger.debug(f"MACD calculation failed: {exc}")
        lookback = min(20, len(df))
        indicators["support_level"] = float(df["low"].tail(lookback).min())
        indicators["resistance_level"] = float(df["high"].tail(lookback).max())
        if len(df) >= 5:
            trend_slope = (df["close"].tail(5).iloc[-1] - df["close"].tail(5).iloc[0]) / df["close"].tail(5).iloc[0]
            indicators["trend_strength"] = abs(trend_slope) * 100
            indicators["trend_direction"] = "UP" if trend_slope > 0.005 else "DOWN" if trend_slope < -0.005 else "SIDEWAYS"
        if "volume" in df.columns:
            avg_volume = df["volume"].tail(10).mean()
            current_volume = df["volume"].iloc[-1]
            indicators["volume_ratio"] = float(current_volume / avg_volume) if avg_volume else 1.0
            indicators["volume_status"] = "HIGH" if indicators["volume_ratio"] > 1.5 else "LOW" if indicators["volume_ratio"] < 0.7 else "NORMAL"
        return add_camel_aliases({"indicators": indicators, "current_price": current_price, "data_points": len(df), "timestamp": datetime.now().isoformat()})
    except Exception as exc:
        logger.error(f"technical indicators failed: {exc}")
        return add_camel_aliases({"indicators": {}, "error": str(exc)})


@app.get("/api/portfolio")
async def get_portfolio() -> Dict[str, Any]:
    positions: List[Dict[str, Any]] = []
    total_value = 0
    try:
        _, db = _safe_db()
        trades_collection = get_collection(db, "trades_executed")
        open_trades = list(trades_collection.find({"status": "OPEN"}))
        for trade in open_trades:
            symbol = trade.get("instrument", getattr(settings, "instrument_symbol", "INSTRUMENT"))
            size = trade.get("quantity", 0)
            entry_price = trade.get("entry_price", 0)
            current_price = None
            if marketmemory:
                try:
                    current_price = marketmemory.get_current_price(symbol.replace("-", "").replace(" ", "").upper())
                except Exception:
                    current_price = None
            current_price = current_price or entry_price
            pnl = (current_price - entry_price) * size
            total_value += current_price * abs(size)
            positions.append({"symbol": symbol, "size": size, "entry": entry_price, "current": current_price, "pnl": pnl})
    except Exception as exc:
        logger.error(f"portfolio failed: {exc}")
    return {"total_value": total_value, "positions": [add_camel_aliases(p) for p in positions]}


@app.get("/api/alerts")
async def get_alerts(limit: int = 20) -> List[Dict[str, Any]]:
    try:
        _, db = _safe_db()
        alerts_collection = get_collection(db, "alerts")
        alerts = list(alerts_collection.find({}, sort=[("timestamp", -1)]).limit(limit))
        for alert in alerts:
            if "_id" in alert:
                alert["_id"] = str(alert["_id"])
        return alerts
    except Exception as exc:
        logger.error(f"alerts failed: {exc}")
        return []


@app.get("/api/system-health")
async def get_system_health() -> Dict[str, Any]:
    try:
        if not healthchecker:
            raise RuntimeError("healthchecker unavailable")
        import concurrent.futures
        health = {"timestamp": datetime.utcnow().isoformat(), "overall_status": "unknown", "components": {}, "note": "partial"}
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(healthchecker.check_all)
            try:
                full = future.result(timeout=1.5)
                health.update(full)
                health.pop("note", None)
            except concurrent.futures.TimeoutError:
                logger.warning("health check timeout")
        return health
    except Exception as exc:
        logger.error(f"system health failed: {exc}")
        # Fallback minimal health snapshot so UI still has something useful
        components: Dict[str, Any] = {}

        # MongoDB health
        mongo_status = "unknown"
        if get_mongo_client and settings:
            try:
                mongo_client = get_mongo_client()
                db = mongo_client[settings.mongodb_db_name]
                # Cheap ping
                db.command("ping")
                mongo_status = "healthy"
            except Exception:
                mongo_status = "unhealthy"
        components["mongodb"] = {"status": mongo_status}

        # Redis / market memory health
        redis_status = "unknown"
        if marketmemory is not None:
            try:
                redis_status = "healthy" if getattr(marketmemory, "_redis_available", False) else "unhealthy"
            except Exception:
                redis_status = "unhealthy"
        components["redis"] = {"status": redis_status}

        # LLM provider summary (optional)
        llm_overall = "unknown"
        try:
            from agents.llm_provider_manager import get_llm_manager

            manager = get_llm_manager()
            if manager and getattr(manager, "providers", None):
                total = len(manager.providers)
                healthy_count = 0
                for cfg in manager.providers.values():
                    status_raw = getattr(cfg, "status", None)
                    status = status_raw.value if hasattr(status_raw, "value") else str(status_raw or "unknown")
                    if status == "available":
                        healthy_count += 1
                if total:
                    if healthy_count == total:
                        llm_overall = "healthy"
                    elif healthy_count == 0:
                        llm_overall = "unhealthy"
                    else:
                        llm_overall = "degraded"
                components["llm_providers"] = {
                    "status": llm_overall,
                    "total": total,
                    "healthy": healthy_count,
                }
        except Exception:
            pass

        overall_status = llm_overall if llm_overall != "unknown" else "degraded"
        if mongo_status == "unhealthy" or redis_status == "unhealthy":
            overall_status = "degraded" if overall_status == "healthy" else overall_status

        return {
            "overall_status": overall_status,
            "components": components,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "fallback",
        }


@app.get("/api/agent-status")
async def get_agent_status() -> Dict[str, Any]:
    try:
        _, db = _safe_db()
        analysis_collection = get_collection(db, "agent_decisions")
        latest = analysis_collection.find_one(sort=[("timestamp", -1)])
        agents_info: Dict[str, Any] = {}
        status_label = "initializing"
        status_message = "Waiting for first analysis"
        last_ts: Optional[datetime] = None
        if latest:
            ts = latest.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    ts = None
            if isinstance(ts, datetime):
                last_ts = ts
        now = datetime.now()
        if last_ts:
            seconds_since = (now - last_ts.replace(tzinfo=None)).total_seconds()
            if seconds_since <= 900:
                status_label = "active"
                status_message = "Agents are running analysis"
            else:
                status_label = "stale"
                status_message = "Analysis is stale; waiting for next cycle"
        agent_decisions = latest.get("agent_decisions", {}) if latest else {}
        incomplete_agents_list = latest.get("incomplete_agents", []) if latest else []
        if isinstance(agent_decisions, dict) and agent_decisions:
            for agent_name, agent_data in agent_decisions.items():
                summary = {}
                if isinstance(agent_data, dict):
                    if "signal" in agent_data:
                        summary["signal"] = agent_data.get("signal")
                    if "recommendation" in agent_data:
                        summary["recommendation"] = agent_data.get("recommendation")
                    if "reasoning" in agent_data:
                        summary["reasoning"] = str(agent_data.get("reasoning", ""))[:200]
                    metrics = {k: v for k, v in agent_data.items() if k not in {"signal", "recommendation", "reasoning", "thesis"} and v not in (None, "", "N/A")}
                    summary["key_metrics"] = dict(list(metrics.items())[:5])
                agents_info[agent_name] = {
                    "name": agent_name.replace("_", " ").title(),
                    "status": status_label if status_label != "initializing" else "active",
                    "last_update": last_ts.isoformat() if last_ts else None,
                    "summary": summary,
                    "data": agent_data,
                    "incomplete": agent_name in incomplete_agents_list
                }
        if not agents_info:
            for agent_name in ["technical_agent", "fundamental_agent", "sentiment_agent", "macro_agent", "portfolio_manager", "risk_agent", "execution_agent", "learning_agent"]:
                agents_info[agent_name] = {
                    "name": agent_name.replace("_", " ").title(),
                    "status": status_label,
                    "last_update": last_ts.isoformat() if last_ts else None,
                    "data": {"message": status_message}
                }
        return {
            "status": status_label,
            "agents": agents_info,
            "last_analysis": last_ts.isoformat() if last_ts else None,
            "executive_summary": latest.get("executive_summary") if latest else None,
            "message": status_message
        }
    except Exception as exc:
        logger.error(f"agent status failed: {exc}")
        return {"status": "error", "agents": {}, "error": str(exc)}


__all__ = ["app", "add_camel_aliases"]
