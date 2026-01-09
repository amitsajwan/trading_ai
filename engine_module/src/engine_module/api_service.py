"""FastAPI REST API service for engine_module.

This provides HTTP endpoints for:
- Orchestrator execution
- Trading signals
- Agent analysis
- Health checks
"""

from __future__ import annotations

import os
import sys
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import redis
from pymongo import MongoClient

from .api import build_orchestrator
from .contracts import Orchestrator, AnalysisResult

logger = logging.getLogger(__name__)
# Ensure a basic logging configuration so messages appear and unicode is handled safely
logging.basicConfig(level=logging.INFO)

# IST timezone for Indian financial markets
IST = timezone(timedelta(hours=5, minutes=30))

# Import market hours checker
try:
    from core_kernel.src.core_kernel.market_hours import is_market_open as check_market_open
    def is_market_open(now=None):
        """Wrapper to ensure timezone-aware datetime is used."""
        if now is None:
            now = datetime.now(IST)
        elif now.tzinfo is None:
            # If naive datetime, assume it's IST
            now = now.replace(tzinfo=IST)
        return check_market_open(now)
except ImportError:
    # Fallback if core_kernel not available
    def is_market_open(now=None):
        """Check if Indian equity market is open (9:15 AM - 3:30 PM IST, Mon-Fri)."""
        if now is None:
            now = datetime.now(IST)
        elif now.tzinfo is None:
            # If naive datetime, assume it's IST
            now = now.replace(tzinfo=IST)
        
        # Market is only open Monday-Friday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Market hours: 9:15 AM to 3:30 PM IST
        market_open_time = now.replace(hour=9, minute=15, second=0, microsecond=0).time()
        market_close_time = now.replace(hour=15, minute=30, second=0, microsecond=0).time()
        current_time = now.time()
        return market_open_time <= current_time < market_close_time


def convert_numpy_types(obj: Any) -> Any:
    """Recursively convert numpy types to native Python types for JSON serialization."""
    try:
        import numpy as np
        
        # Handle numpy scalar types
        if isinstance(obj, (np.integer, np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64,
                           np.uint8, np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float16, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_numpy_types(item) for item in obj]
        else:
            return obj
    except ImportError:
        # If numpy is not available, just return the object as-is
        return obj


# Pydantic models for API requests/responses
class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    module: str
    timestamp: str
    dependencies: Dict[str, str]


class AnalysisRequest(BaseModel):
    """Analysis request."""
    instrument: str
    context: Optional[Dict[str, Any]] = None


class AnalysisResponse(BaseModel):
    """Analysis result response."""
    instrument: str
    decision: str
    confidence: float
    details: Optional[Dict[str, Any]] = None
    timestamp: str


class SignalResponse(BaseModel):
    """Trading signal response."""
    signal_id: str
    instrument: str
    action: str  # "BUY", "SELL", "HOLD"
    confidence: float
    reasoning: str
    timestamp: str


# Socket.IO removed - real-time updates now handled by Redis WebSocket Gateway
# See redis_ws_gateway module for direct Redis pub/sub to WebSocket forwarding
WEBSOCKET_AVAILABLE = False

# Lifespan handler for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources using FastAPI lifespan events."""
    global _orchestrator
    
    try:
        # Startup
        # Check Redis connection
        redis_client = get_redis_client()
        redis_client.ping()
        
        # Check MongoDB connection
        mongo_client = get_mongo_client()
        mongo_client.admin.command('ping')
        
        logger.info("Engine API: Services initialized successfully")
        
        # Initialize orchestrator with LLM client and Redis
        try:
            # Debug: Check if genai_module is in Python path
            logger.debug("Engine API: Python path includes: %s", [p for p in sys.path if 'genai' in p.lower()])
            logger.debug("Engine API: Current working directory: %s", os.getcwd())
            
            # Import LLM provider manager and client builder
            from genai_module.core.llm_provider_manager import LLMProviderManager
            from genai_module.api import build_llm_client
            
            # Build LLM client (reads API keys from environment)
            logger.info("Engine API: Building LLM client...")
            llm_manager = LLMProviderManager()
            llm_client = build_llm_client(llm_manager)
            logger.info("Engine API: LLM client initialized")
            
            # Build agents
            logger.info("Engine API: Building agents...")
            from engine_module.agent_factory import create_default_agents
            
            # Create default agents with balanced profile
            agents = create_default_agents(
                profile="balanced",
                llm_client=llm_client,
                news_service=None  # Will be added later if needed
            )
            logger.info("Engine API: Created %d agents", len(agents))
            
            # Initialize SignalMonitor for conditional signal monitoring
            signal_monitor = None
            try:
                from .signal_monitor import get_signal_monitor
                signal_monitor = get_signal_monitor()
                logger.info("Engine API: SignalMonitor initialized")
            except Exception as e:
                logger.warning("Engine API: SignalMonitor not available: %s", e)
            
            # Get MongoDB database for signal persistence
            mongo_db = None
            try:
                db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
                mongo_db = mongo_client[db_name]
                logger.info("Engine API: MongoDB database '%s' ready for signal persistence", db_name)
            except Exception as e:
                logger.warning("Engine API: MongoDB database not available: %s", e)
            
            # Build orchestrator with Redis client for market data and agents
            logger.info("Engine API: Building orchestrator...")
            _orchestrator = build_orchestrator(
                llm_client=llm_client,
                redis_client=redis_client,
                agents=agents,
                signal_monitor=signal_monitor,
                mongo_db=mongo_db,
                instrument="BANKNIFTY"  # Default to BANKNIFTY Futures (nearest expiry) - should be determined dynamically
            )
            logger.info("Engine API: Orchestrator initialized successfully with signal monitoring support")
            
            # Sync existing signals from MongoDB to SignalMonitor on startup
            if signal_monitor and mongo_db is not None:
                try:
                    from .signal_creator import sync_signals_to_monitor
                    synced = await sync_signals_to_monitor(mongo_db, signal_monitor)
                    if synced > 0:
                        logger.info(f"Engine API: Synced {synced} existing signals to SignalMonitor on startup")
                except Exception as sync_error:
                    logger.warning(f"Engine API: Failed to sync signals on startup: {sync_error}")
            
            # Start Redis tick subscriber for real-time signal monitoring
            try:
                from .redis_tick_subscriber import start_tick_subscriber
                await start_tick_subscriber()
                logger.info("Engine API: Redis tick subscriber started for real-time signal monitoring")
            except Exception as tick_error:
                logger.warning(f"Engine API: Failed to start tick subscriber: {tick_error}")
            
            # Socket.IO removed - real-time updates now handled by Redis WebSocket Gateway
            # Engine API now focuses on REST endpoints only
            
        except ImportError as e:
            logger.warning("Engine API: Failed to import dependencies: %s", e)
            logger.debug("Engine API: Python path: %s", sys.path)
            logger.warning("Engine API: Make sure genai_module/src is in PYTHONPATH")
            logger.warning("Engine API: Orchestrator will not be available")
            _orchestrator = None
        except Exception as e:
            logger.exception("Engine API: Failed to initialize orchestrator: %s", e)
            _orchestrator = None
            
    except Exception as e:
        logger.exception("Engine API: Startup error: %s", e)
    
    yield
    
    # Shutdown
    global _mongo_client
    
    # Stop tick subscriber
    try:
        from .redis_tick_subscriber import stop_tick_subscriber
        await stop_tick_subscriber()
        logger.info("Engine API: Redis tick subscriber stopped")
    except Exception as e:
        logger.warning(f"Engine API: Error stopping tick subscriber: {e}")
    
    # Socket.IO removed - no cleanup needed
    
    _orchestrator = None
    
    if _mongo_client is not None:
        try:
            _mongo_client.close()
        except Exception:
            pass


# FastAPI app
app = FastAPI(
    title="Engine API",
    description="REST API for trading orchestrator, signals, and agent analysis (with WebSocket support)",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware to allow requests from dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global orchestrator instance
_orchestrator: Optional[Orchestrator] = None
_redis_client: Optional[redis.Redis] = None
_mongo_client: Optional[MongoClient] = None

# Socket.IO removed - real-time updates now handled by Redis WebSocket Gateway
# Export the FastAPI app directly (no Socket.IO wrapping)
main_app = app


def get_redis_client() -> redis.Redis:
    """Get Redis client from environment."""
    global _redis_client
    if _redis_client is None:
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        _redis_client = redis.Redis(host=host, port=port, db=0, decode_responses=True)
    return _redis_client


def get_mongo_client() -> MongoClient:
    """Get MongoDB client from environment."""
    global _mongo_client
    if _mongo_client is None:
        mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/zerodha_trading")
        _mongo_client = MongoClient(mongodb_uri)
    return _mongo_client




@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
    
    try:
        mongo_client = get_mongo_client()
        mongo_client.admin.command('ping')
        mongo_status = "healthy"
    except Exception as e:
        mongo_status = f"unhealthy: {str(e)}"
    
    return HealthResponse(
        status="healthy" if (redis_status == "healthy" and mongo_status == "healthy") else "degraded",
        module="engine",
        timestamp=datetime.now(IST).isoformat(),
        dependencies={
            "redis": redis_status,
            "mongodb": mongo_status,
            "orchestrator": "initialized" if _orchestrator is not None else "not_initialized"
        }
    )


@app.post("/api/v1/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest):
    """Run orchestrator analysis cycle."""
    try:
        if _orchestrator is None:
            raise HTTPException(
                status_code=503,
                detail="Orchestrator not initialized. Requires LLM client and market store."
            )
        
        context = request.context or {}
        context["instrument"] = request.instrument
        
        # Check market hours and add to context (critical for orchestrator decisions)
        current_time_ist = datetime.now(IST)
        market_open = is_market_open(current_time_ist)
        context["market_hours"] = market_open
        context["timestamp"] = current_time_ist
        
        if not market_open:
            logger.info(f"Market is CLOSED (current time: {current_time_ist.strftime('%Y-%m-%d %H:%M:%S %Z')})")
        else:
            logger.info(f"Market is OPEN (current time: {current_time_ist.strftime('%Y-%m-%d %H:%M:%S %Z')})")
        
        result = await _orchestrator.run_cycle(context)
        
        # Convert numpy types in details to native Python types for JSON serialization
        details = result.details
        if details:
            details = convert_numpy_types(details)
        
        # Save agent decisions to MongoDB for agent status display
        try:
            mongo_client = get_mongo_client()
            db = mongo_client["zerodha_trading"]
            agent_discussions = db["agent_discussions"]
            
            # Extract agent signals from aggregated_analysis
            agent_signals = []
            if isinstance(details, dict) and "aggregated_analysis" in details:
                agg = details.get("aggregated_analysis", {})
                # Extract from various signal buckets
                signal_buckets = [
                    "technical_signals", "sentiment_signals", "macro_signals", 
                    "risk_signals", "execution_signals", "bull_bear_signals"
                ]
                for bucket in signal_buckets:
                    signals = agg.get(bucket, [])
                    if isinstance(signals, list):
                        agent_signals.extend(signals)
                    elif isinstance(signals, dict):
                        agent_signals.extend(list(signals.values()))
            
            # Save each agent's decision
            timestamp = datetime.now(IST)
            saved_count = 0
            for entry in agent_signals:
                if isinstance(entry, dict) and entry.get("agent"):
                    agent_name = entry.get("agent", "Unknown Agent")
                    signal = entry.get("signal") or entry.get("decision")
                    if signal:  # Only save if we have a decision
                        confidence = entry.get("confidence", 0.0)
                        
                        discussion_doc = {
                            "timestamp": timestamp.isoformat(),
                            "agent_name": agent_name,
                            "signal": signal,
                            "decision": signal,  # Alias for compatibility
                            "confidence": float(confidence) if confidence is not None else 0.0,
                            "weight": entry.get("weight"),
                            "weighted_vote": entry.get("weighted_vote"),
                            "reasoning": entry.get("reasoning") or entry.get("thesis"),
                            "indicators": entry.get("indicators") or entry.get("details", {}),
                            "instrument": request.instrument,
                        }
                        agent_discussions.insert_one(discussion_doc)
                        saved_count += 1
                        
                        # Publish agent decision to Redis pub/sub for real-time updates
                        try:
                            redis_client = get_redis_client()
                            # Derive canonical direction (BUY/SELL/HOLD) for UI friendliness
                            sig_str = str(signal).upper() if signal is not None else ''
                            direction = 'HOLD'
                            if 'SELL' in sig_str or 'PUT' in sig_str:
                                direction = 'SELL'
                            elif 'BUY' in sig_str or 'CALL' in sig_str:
                                direction = 'BUY'

                            decision_data = {
                                "agent_name": agent_name,
                                "signal": signal,
                                "decision": signal,
                                "direction": direction,
                                "confidence": float(confidence) if confidence is not None else 0.0,
                                "timestamp": timestamp.isoformat(),
                                "instrument": request.instrument
                            }
                            import json
                            redis_client.publish("engine:decision", json.dumps(decision_data))
                            redis_client.publish(f"engine:decision:{request.instrument}", json.dumps(decision_data))
                        except Exception as pub_err:
                            logger.debug(f"Failed to publish decision to Redis pub/sub: {pub_err}")
            
            if saved_count > 0:
                logger.info(f"Saved {saved_count} agent decisions to MongoDB")
                    
        except Exception as save_error:
            logger.warning(f"Failed to save agent decisions to MongoDB: {save_error}", exc_info=True)
            # Continue even if save fails
        
        # Ensure confidence is a native Python float
        confidence = float(result.confidence) if result.confidence is not None else 0.0
        
        return AnalysisResponse(
            instrument=request.instrument,
            decision=str(result.decision) if result.decision else "HOLD",
            confidence=confidence,
            details=details,
            timestamp=datetime.now(IST).isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        # Log full traceback for debugging
        import traceback
        error_detail = str(e)
        traceback_str = traceback.format_exc()
        print(f"ERROR in analyze endpoint: {error_detail}")
        print(f"Traceback:\n{traceback_str}")
        logger.error(f"Error in analyze endpoint: {error_detail}\n{traceback_str}")
        raise HTTPException(status_code=500, detail=f"{error_detail}")


@app.get("/api/v1/signals/{instrument}", response_model=List[SignalResponse])
async def get_signals(instrument: str, limit: int = 10):
    """Get recent trading signals for an instrument."""
    try:
        # Get signals from MongoDB
        mongo_client = get_mongo_client()
        db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
        db = mongo_client[db_name]
        signals_collection = db["signals"]
        
        # Query recent signals (sort by created_at instead of timestamp)
        signals = list(
            signals_collection.find({"instrument": instrument.upper()})
            .sort("created_at", -1)
            .limit(limit)
        )
        
        return [
            SignalResponse(
                signal_id=str(signal.get("_id", "")),
                instrument=signal.get("instrument", instrument),
                action=signal.get("action", "HOLD"),
                confidence=signal.get("confidence", 0.0),
                reasoning=signal.get("reasoning", ""),
                timestamp=signal.get("created_at", signal.get("timestamp", datetime.now(IST).isoformat()))
            )
            for signal in signals
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/signals/delete-pending")
async def delete_pending_signals_endpoint(instrument: Optional[str] = None):
    """Delete all pending (non-executed) signals.
    
    This is typically called at the start of each orchestrator cycle.
    """
    try:
        from .signal_creator import delete_pending_signals
        
        mongo_client = get_mongo_client()
        db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
        db = mongo_client[db_name]
        
        deleted_count = await delete_pending_signals(db, instrument=instrument)
        
        # Also clear SignalMonitor if available
        if _orchestrator and hasattr(_orchestrator, 'signal_monitor') and _orchestrator.signal_monitor:
            active_signals = _orchestrator.signal_monitor.get_active_signals(instrument)
            for signal in active_signals:
                _orchestrator.signal_monitor.remove_signal(signal.condition_id)
            cleared_count = len(active_signals)
        else:
            cleared_count = 0
        
        return {
            "success": True,
            "deleted_from_mongodb": deleted_count,
            "cleared_from_monitor": cleared_count,
            "instrument": instrument or "all"
        }
    except Exception as e:
        logger.error(f"Failed to delete pending signals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/signals/by-id/{signal_id}")
async def get_signal_by_id(signal_id: str):
    """Get full signal document by its Mongo _id or condition_id."""
    try:
        mongo_client = get_mongo_client()
        db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
        db = mongo_client[db_name]
        collection = db["signals"]

        # Try as ObjectId first
        try:
            from bson import ObjectId
            query = {"_id": ObjectId(signal_id)}
        except Exception:
            query = {"condition_id": signal_id}

        doc = collection.find_one(query)
        if not doc:
            raise HTTPException(status_code=404, detail="Signal not found")

        # Convert ObjectId to string for JSON
        if doc.get("_id"):
            doc["signal_id"] = str(doc["_id"])
            doc["_id"] = str(doc["_id"])

        return doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch signal by id: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/signals/mark-executed")
async def mark_signal_executed(signal_id: str, execution_info: Optional[dict] = None):
    """Mark a signal as executed in MongoDB. Accepts either the document _id or the condition_id."""
    try:
        mongo_client = get_mongo_client()
        db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
        db = mongo_client[db_name]
        collection = db["signals"]

        # Try to match by ObjectId, else by condition_id
        try:
            from bson import ObjectId
            query = {"_id": ObjectId(signal_id)}
        except Exception:
            query = {"condition_id": signal_id}

        update = {"$set": {"status": "executed", "executed_at": datetime.now(IST).isoformat()}}
        if execution_info:
            update["$set"]["execution_info"] = execution_info

        collection.update_one(query, update)

        return {"success": True, "signal_id": signal_id}
    except Exception as e:
        logger.error(f"Failed to mark signal executed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/signals/sync")
async def sync_signals_to_monitor_endpoint(instrument: Optional[str] = None):
    """Sync MongoDB signals to SignalMonitor for real-time monitoring.
    
    Reads all active pending signals from MongoDB and adds them to SignalMonitor.
    """
    try:
        from .signal_creator import sync_signals_to_monitor
        
        if not _orchestrator or not hasattr(_orchestrator, 'signal_monitor') or not _orchestrator.signal_monitor:
            raise HTTPException(status_code=503, detail="SignalMonitor not available")
        
        if _orchestrator.mongo_db is None:
            raise HTTPException(status_code=503, detail="MongoDB not available")
        
        synced_count = await sync_signals_to_monitor(
            _orchestrator.mongo_db,
            _orchestrator.signal_monitor,
            instrument=instrument
        )
        
        return {
            "success": True,
            "signals_synced": synced_count,
            "instrument": instrument or "all"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync signals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio")
async def get_portfolio():
    """Get portfolio summary from orchestrator."""
    try:
        if _orchestrator is None:
            return {
                "total_equity": 0,
                "available_cash": 0,
                "total_portfolio_value": 0,
                "total_unrealized_pnl": 0,
                "daily_pnl": 0,
                "total_pnl": 0,
                "total_risk_exposure": 0,
                "active_positions": [],
                "timestamp": datetime.now(IST).isoformat()
            }
        
        # Get portfolio summary from position manager if available
        if hasattr(_orchestrator, 'position_manager') and _orchestrator.position_manager:
            portfolio_summary = _orchestrator.position_manager.get_portfolio_summary()
        else:
            portfolio_summary = {
                "total_equity": 0,
                "available_cash": 0,
                "total_portfolio_value": 0,
                "total_unrealized_pnl": 0,
                "daily_pnl": 0,
                "total_pnl": 0,
                "total_risk_exposure": 0,
                "active_positions": []
            }
        
        # Convert numpy types if present
        if portfolio_summary:
            portfolio_summary = convert_numpy_types(portfolio_summary)
            portfolio_summary["timestamp"] = datetime.now(IST).isoformat()
        
        return portfolio_summary or {
            "total_equity": 0,
            "available_cash": 0,
            "total_portfolio_value": 0,
            "total_unrealized_pnl": 0,
            "daily_pnl": 0,
            "total_pnl": 0,
            "total_risk_exposure": 0,
            "active_positions": [],
            "timestamp": datetime.now(IST).isoformat()
        }
    except Exception as e:
        logger.exception("Error getting portfolio: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/agent-status")
async def get_agent_status():
    """Get agent status and orchestrator state.
    
    Returns an array of agents with their latest decisions from MongoDB.
    """
    try:
        agents_info = []
        
        # Get agent list from orchestrator if available
        agent_names = []
        if _orchestrator is not None and hasattr(_orchestrator, 'agents') and _orchestrator.agents:
            agent_names = [agent.__class__.__name__ if hasattr(agent, '__class__') else str(agent) 
                          for agent in _orchestrator.agents]
        else:
            # Default agent list if orchestrator not available
            agent_names = [
                "TechnicalAgent", "SentimentAgent", "MacroAgent", "FundamentalAgent",
                "MomentumAgent", "TrendAgent", "VolumeAgent", "MeanReversionAgent",
                "BullResearcher", "BearResearcher", "NeutralRiskAgent", "ExecutionAgent"
            ]
        
        # Fetch latest decisions from MongoDB for each agent
        try:
            mongo_client = get_mongo_client()
            db = mongo_client["zerodha_trading"]
            agent_discussions = db["agent_discussions"]
            
            # Get latest decision for each agent
            for agent_name in agent_names:
                latest_discussion = agent_discussions.find_one(
                    {"agent_name": agent_name},
                    sort=[("timestamp", -1)]
                )
                
                last_decision = None
                updated_at = datetime.now(IST).isoformat()
                
                if latest_discussion:
                    last_decision = latest_discussion.get("signal") or latest_discussion.get("decision")
                    updated_at = latest_discussion.get("timestamp", updated_at)
                
                agents_info.append({
                    "name": agent_name,
                    "state": "active",
                    "status": "active",
                    "last_decision": last_decision,
                    "updated_at": updated_at
                })
        except Exception as db_error:
            logger.warning(f"Could not fetch agent decisions from MongoDB: {db_error}")
            # Fallback: return agents without decisions
            for agent_name in agent_names:
                agents_info.append({
                    "name": agent_name,
                    "state": "active",
                    "status": "active",
                    "last_decision": None,
                    "updated_at": datetime.now(IST).isoformat()
                })
        
        return agents_info
    except Exception as e:
        logger.exception("Error getting agent status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/decision/latest")
async def get_latest_decision():
    """Get the latest trading decision from orchestrator."""
    try:
        if _orchestrator is None:
            return {
                "instrument": "BANKNIFTY",
                "signal": "HOLD",
                "confidence": 0.0,
                "reasoning": "Orchestrator not initialized",
                "timestamp": datetime.now(IST).isoformat()
            }
        
        # Get latest decision from MongoDB or orchestrator state
        mongo_client = get_mongo_client()
        db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
        db = mongo_client[db_name]
        signals_collection = db["signals"]
        
        # Get most recent signal
        latest_signal = signals_collection.find_one(
            {},
            sort=[("timestamp", -1)]
        )
        
        if latest_signal:
            return {
                "instrument": latest_signal.get("instrument", "BANKNIFTY"),
                "signal": latest_signal.get("action", "HOLD"),
                "confidence": float(latest_signal.get("confidence", 0.0)),
                "reasoning": latest_signal.get("reasoning", ""),
                "timestamp": latest_signal.get("timestamp", datetime.now(IST).isoformat())
            }
        
        return {
            "instrument": "BANKNIFTY",
            "signal": "HOLD",
            "confidence": 0.0,
            "reasoning": "No recent decisions available",
            "timestamp": datetime.now(IST).isoformat()
        }
    except Exception as e:
        logger.exception("Error getting latest decision: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/options-strategy-agent")
async def get_options_strategy_agent():
    """Get the latest options strategy from the multi-agent system.
    
    Returns complex multi-leg strategies like condors and spreads with full risk/reward analysis.
    """
    try:
        from pymongo import MongoClient
        
        mongo_client = get_mongo_client()
        db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
        db = mongo_client[db_name]
        collection = db["agent_decisions"]
        
        # Find the most recent decision with options strategy
        latest = collection.find_one(
            {"options_strategy": {"$exists": True}},
            sort=[("timestamp", -1)]
        )
        
        if not latest:
            return {
                "available": False,
                "reason": "No options strategy available from agents",
                "timestamp": datetime.now(IST).isoformat()
            }
        
        options_strategy = latest.get("options_strategy")
        if not options_strategy:
            return {
                "available": False,
                "reason": "No options strategy in latest decision",
                "timestamp": datetime.now(IST).isoformat()
            }
        
        # Format the response with full strategy details
        strategy_details = {
            "available": True,
            "timestamp": latest.get("timestamp", datetime.now(IST).isoformat()),
            "strategy_type": options_strategy.get("strategy_type"),
            "underlying": options_strategy.get("underlying"),
            "expiry": options_strategy.get("expiry"),
            "confidence": latest.get("confidence", 0.0),
            "agent": latest.get("agent", "unknown"),
            "legs": options_strategy.get("legs", []),
            "risk_analysis": {
                "max_profit": options_strategy.get("max_profit", 0.0),
                "max_loss": options_strategy.get("max_loss", 0.0),
                "breakeven_points": options_strategy.get("breakeven_points", []),
                "risk_reward_ratio": options_strategy.get("risk_reward_ratio", 0.0),
                "margin_required": options_strategy.get("margin_required", 0.0)
            },
            "reasoning": latest.get("reasoning", "")
        }
        
        return strategy_details
    except Exception as e:
        logger.exception("Error getting options strategy: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/trades")
async def get_recent_trades(limit: int = 20):
    """Get recent trades from the system."""
    try:
        # Get trades from MongoDB
        mongo_client = get_mongo_client()
        db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
        db = mongo_client[db_name]
        trades_collection = db.get_collection("trades")
        
        # Query recent trades
        trades = list(
            trades_collection.find({})
            .sort("timestamp", -1)
            .limit(limit)
        )
        
        # Convert to expected format
        result = []
        for trade in trades:
            result.append({
                "id": str(trade.get("_id", "")),
                "timestamp": trade.get("timestamp", datetime.now(IST).isoformat()),
                "instrument": trade.get("instrument", ""),
                "side": trade.get("side", "BUY"),
                "quantity": trade.get("quantity", 0),
                "price": trade.get("price", 0.0),
                "pnl": trade.get("pnl", 0.0),
                "status": trade.get("status", "open"),
                "exit_price": trade.get("exit_price"),
                "exit_timestamp": trade.get("exit_timestamp")
            })
        
        return result
    except Exception as e:
        logger.exception("Error getting recent trades: %s", e)
        # Return empty array on error
        return []


@app.get('/api/v1/orchestrator/health')
async def orchestrator_health():
    """Return last orchestrator health document from MongoDB (if available)."""
    try:
        mongo_client = get_mongo_client()
        db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
        db = mongo_client[db_name]
        doc = db.orchestrator_health.find_one({'_id': 'current'})
        if not doc:
            raise HTTPException(status_code=404, detail="No orchestrator health available")
        # Convert ObjectId and datetime to strings where necessary
        doc = convert_numpy_types(doc)
        # Remove Mongo internal _id to avoid ObjectId serialization issues
        doc_copy = {k: (str(v) if k == '_id' else v) for k, v in doc.items()}
        return doc_copy
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching orchestrator health: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/orchestrator/initialize")
async def initialize_orchestrator(config: Dict[str, Any] = Body(...)):
    """Initialize orchestrator with dependencies.
    
    This endpoint allows dynamic initialization of the orchestrator
    with LLM client, market store, and other dependencies.
    """
    try:
        # This would require importing and building dependencies
        # For now, return a message indicating manual initialization is needed
        return {
            "status": "info",
            "message": "Orchestrator initialization requires proper dependency injection. "
                      "Use the build_orchestrator function from engine_module.api with "
                      "LLM client, market store, and options data.",
            "timestamp": datetime.now(IST).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("ENGINE_API_PORT", "8006"))
    host = os.getenv("ENGINE_API_HOST", "0.0.0.0")
    
    print(f"Starting Engine API on {host}:{port}")
    # Socket.IO removed - using FastAPI app directly
    uvicorn.run(app, host=host, port=port)

