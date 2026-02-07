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
import asyncio
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

# Fix Windows console encoding for emojis (same as start_local.py)
if sys.platform == 'win32':
    try:
        # Try to set UTF-8 encoding for Windows console
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        # Fallback for older Python versions
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Setup logging before any other operations
try:
    from config import get_config
    config = get_config()
    config.setup_logging()
except ImportError:
    # Fallback if config not available
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger('engine_module')

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


def _serialize_bson(obj: Any) -> Any:
    """Recursively convert BSON types to JSON-serializable types."""
    from bson import ObjectId
    from datetime import datetime

    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize_bson(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_bson(item) for item in obj]
    else:
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
    reasoning: Optional[str] = None
    timestamp: str

    # New fields for UI display and debugging
    entry_price: Optional[float] = None
    execution_mode: Optional[str] = None
    parsed_conditions: Optional[List[Dict[str, Any]]] = None
    reason_hash: Optional[str] = None
    indicator: Optional[str] = None
    threshold: Optional[float] = None
    additional_conditions: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# Socket.IO removed - real-time updates now handled by Redis WebSocket Gateway
# See redis_ws_gateway module for direct Redis pub/sub to WebSocket forwarding
WEBSOCKET_AVAILABLE = False

async def start_cycles_later():
    """Start orchestrator cycles after a delay to ensure everything is initialized."""
    await asyncio.sleep(30)  # Wait 30 seconds
    try:
        global _orchestrator_task
        if _orchestrator and not hasattr(_orchestrator_task, 'done'):
            _orchestrator_task = asyncio.create_task(run_orchestrator_cycles())
            logger.info("Engine API: Automatic orchestrator cycles started (delayed)")
    except Exception as e:
        logger.error(f"Engine API: Failed to start delayed cycles: {e}")

# Lifespan handler for FastAPI
async def start_cycles_later():
    """Start orchestrator cycles after a delay to ensure everything is initialized."""
    await asyncio.sleep(30)  # Wait 30 seconds
    try:
        global _orchestrator_task
        if _orchestrator and not hasattr(_orchestrator_task, 'done'):
            _orchestrator_task = asyncio.create_task(run_orchestrator_cycles())
            logger.info("Engine API: Automatic orchestrator cycles started (delayed)")
    except Exception as e:
        logger.error(f"Engine API: Failed to start delayed cycles: {e}")


async def run_orchestrator_cycles():
    """Run orchestrator analysis cycles based on execution mode."""
    logger.info("Starting orchestrator cycle manager")

    # Get Redis client for mode and virtual time checks
    redis_client = get_redis_client()

    while True:
        try:
            # Check if orchestrator is initialized
            if _orchestrator is None:
                logger.debug("Orchestrator not initialized, skipping cycle")
                await asyncio.sleep(60)  # Wait 1 minute and try again
                continue

            # Get execution mode
            execution_mode = redis_client.get("system:execution_mode")
            if execution_mode:
                execution_mode = execution_mode.decode() if isinstance(execution_mode, bytes) else execution_mode
            else:
                execution_mode = "LIVE"

            if execution_mode == "BACKTEST":
                # In BACKTEST mode, wait for candle triggers instead of running on timer
                logger.info("BACKTEST mode: Waiting for candle triggers (no automatic cycles)")
                await asyncio.sleep(300)  # Wait 5 minutes and check again (BACKTEST cycles are triggered externally)
                continue

            # LIVE/PAPER mode: Run on timer as before
            logger.info("Starting automatic orchestrator cycles (15-minute intervals)")

            # Check if virtual time is enabled (historical mode)
            from datetime import datetime
            virtual_time_enabled = redis_client.get("system:virtual_time:enabled")
            if virtual_time_enabled:
                virtual_time_str = virtual_time_enabled.decode() if isinstance(virtual_time_enabled, bytes) else virtual_time_enabled
                if virtual_time_str == "1":
                    # Use virtual time from Redis
                    virtual_time_current = redis_client.get("system:virtual_time:current")
                    if virtual_time_current:
                        virtual_time_str = virtual_time_current.decode() if isinstance(virtual_time_current, bytes) else virtual_time_current
                        try:
                            current_time_ist = datetime.fromisoformat(virtual_time_str)
                            if current_time_ist.tzinfo is None:
                                current_time_ist = current_time_ist.replace(tzinfo=IST)
                            logger.debug(f"Using virtual time: {current_time_ist.strftime('%H:%M:%S %Z')}")
                        except Exception as e:
                            logger.warning(f"Failed to parse virtual time, using real time: {e}")
                            current_time_ist = datetime.now(IST)
                    else:
                        current_time_ist = datetime.now(IST)
                else:
                    current_time_ist = datetime.now(IST)
            else:
                # Use real-time
                current_time_ist = datetime.now(IST)

            market_open = is_market_open(current_time_ist)

            if not market_open:
                logger.debug(f"Market closed (current time: {current_time_ist.strftime('%H:%M:%S %Z')}), skipping cycle")
                await asyncio.sleep(300)  # Wait 5 minutes when market is closed
                continue

            # Run analysis cycle
            context = {
                "instrument": "BANKNIFTY",
                "market_hours": True,
                "timestamp": current_time_ist
            }

            logger.info(f"Running {execution_mode} orchestrator cycle")
            result = await _orchestrator.run_cycle(context)

            logger.info(f"Orchestrator cycle complete: {result.decision} (confidence: {result.confidence:.2f})")

            # Wait 15 minutes before next cycle
            await asyncio.sleep(15 * 60)

        except Exception as e:
            logger.error(f"Error in orchestrator cycle: {e}")
            await asyncio.sleep(60)  # Wait 1 minute on error


async def run_candle_triggered_cycles():
    """Run orchestrator cycles triggered by candle close events in BACKTEST mode."""
    logger.info("Starting candle-triggered orchestrator cycles for BACKTEST mode")

    redis_client = get_redis_client()
    pubsub = redis_client.pubsub()

    # Subscribe to OHLC candle channels for configured instrument
    from config import get_config
    config = get_config()
    channels = [
        f"market:ohlc:{config.instrument_key}:INDEX",  # 1-minute candles
    ]

    pubsub.subscribe(*channels)
    logger.info(f"Candle-triggered cycles: Subscribed to channels: {channels}")

    try:
        while True:
            try:
                # Wait for candle message
                message = pubsub.get_message(timeout=1.0)
                if message and message['type'] == 'message':
                    data = json.loads(message['data']) if isinstance(message['data'], str) else message['data']

                    # Check if this is a candle close event (mode=BACKTEST and has close price)
                    if (data.get('mode') == 'BACKTEST' and
                        'close' in data and
                        'timestamp' in data):

                        # Check if orchestrator is ready
                        if _orchestrator is None:
                            logger.debug("Orchestrator not initialized, skipping candle-triggered cycle")
                            continue

                        # Parse timestamp
                        from datetime import datetime
                        try:
                            candle_timestamp = datetime.fromisoformat(data['timestamp'])
                            if candle_timestamp.tzinfo is None:
                                candle_timestamp = candle_timestamp.replace(tzinfo=IST)
                        except Exception as e:
                            logger.warning(f"Failed to parse candle timestamp: {e}")
                            continue

                        # Run orchestrator cycle for this candle
                        context = {
                            "instrument": "BANKNIFTY",
                            "market_hours": True,  # Always true in backtest
                            "timestamp": candle_timestamp,
                            "candle_data": data,  # Include candle data for backtest context
                            "mode": "BACKTEST"
                        }

                        logger.info(f"Running BACKTEST orchestrator cycle for candle at {candle_timestamp.strftime('%H:%M:%S')}")
                        result = await _orchestrator.run_cycle(context)
                        logger.info(f"BACKTEST cycle complete: {result.decision} (confidence: {result.confidence:.2f})")

            except Exception as e:
                logger.error(f"Error in candle-triggered cycle: {e}")
                await asyncio.sleep(1)  # Brief pause on error

    except Exception as e:
        logger.error(f"Candle-triggered cycles stopped: {e}")
    finally:
        pubsub.unsubscribe(*channels)
        pubsub.close()


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

            # Initialize RealtimeSignalProcessor for real-time signal monitoring
            realtime_processor = None
            try:
                from .realtime_signal_integration import create_realtime_processor
                realtime_processor = create_realtime_processor()
                logger.info("Engine API: RealtimeSignalProcessor initialized")
            except Exception as e:
                logger.warning("Engine API: RealtimeSignalProcessor not available: %s", e)
            
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
            # Get execution mode and run_id from Redis (set by historical replayer)
            execution_mode = redis_client.get("system:execution_mode")
            run_id = redis_client.get("system:run_id")

            # Decode bytes if needed
            if execution_mode:
                execution_mode = execution_mode.decode() if isinstance(execution_mode, bytes) else execution_mode
            else:
                execution_mode = "LIVE"  # Default to LIVE mode

            if run_id:
                run_id = run_id.decode() if isinstance(run_id, bytes) else run_id

            logger.info(f"Engine API: Initializing in {execution_mode} mode" + (f" (run_id: {run_id})" if run_id else ""))

            # Create trading context
            from .enhanced_orchestrator import TradingContext
            from config import get_config
            config = get_config()
            context = TradingContext(
                instrument=config.instrument_symbol,  # Use configured instrument from environment
                mode=execution_mode,
                run_id=run_id
            )

            _orchestrator = build_orchestrator(
                llm_client=llm_client,
                redis_client=redis_client,
                agents=agents,
                signal_monitor=signal_monitor,
                mongo_db=mongo_db,
                context=context
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
            
            # DISABLED: Candle-triggered cycles for BACKTEST mode (blocking Redis subscription)
            # TODO: Implement async Redis subscription for candle-triggered cycles
            # Get execution mode for BACKTEST check
            execution_mode = redis_client.get("system:execution_mode")
            if execution_mode:
                execution_mode = execution_mode.decode() if isinstance(execution_mode, bytes) else execution_mode
            else:
                execution_mode = "LIVE"

            if execution_mode == "BACKTEST":
                logger.info("Engine API: Candle-triggered cycles DISABLED for BACKTEST mode (use manual cycles instead)")

            # Start automatic orchestrator cycles (every 15 minutes)
            try:
                # Ensure asyncio is available in this context
                import asyncio as asyncio_module
                if asyncio_module and _orchestrator:
                    _orchestrator_task = asyncio_module.create_task(run_orchestrator_cycles())
                    logger.info("Engine API: Automatic orchestrator cycles started (15-minute intervals)")
                else:
                    logger.warning("Engine API: Orchestrator not ready or asyncio unavailable, skipping automatic cycles")
            except Exception as cycle_error:
                logger.warning(f"Engine API: Failed to start automatic orchestrator cycles: {cycle_error}")
                # Try to start cycles later
                try:
                    import asyncio as asyncio_module
                    asyncio_module.get_event_loop().create_task(start_cycles_later())
                except:
                    pass
            
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
    
    # Stop orchestrator task
    try:
        if _orchestrator_task and not _orchestrator_task.done():
            _orchestrator_task.cancel()
            try:
                await _orchestrator_task
            except asyncio.CancelledError:
                pass
        logger.info("Engine API: Orchestrator cycles stopped")
    except Exception as e:
        logger.warning(f"Engine API: Error stopping orchestrator cycles: {e}")
    
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
_orchestrator_task: Optional[asyncio.Task] = None

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


@app.get("/test")
async def test_endpoint():
    """Simple test endpoint."""
    return {"status": "ok", "orchestrator": "initialized" if _orchestrator is not None else "None"}


@app.get("/api/control/mode/info")
async def get_mode_info():
    """Get current system mode and execution context.

    Returns mode information that UI uses to configure subscriptions and behavior.
    """
    try:
        redis_client = get_redis_client()

        # Get execution mode from Redis
        execution_mode = redis_client.get("system:execution_mode")
        if execution_mode:
            execution_mode = execution_mode.decode() if isinstance(execution_mode, bytes) else execution_mode
        else:
            execution_mode = "LIVE"

        # Get run_id from Redis
        run_id = redis_client.get("system:run_id")
        if run_id:
            run_id = run_id.decode() if isinstance(run_id, bytes) else run_id

        # Get instrument from orchestrator context if available
        instrument = "BANKNIFTY"  # Default
        if hasattr(_orchestrator, 'context') and _orchestrator.context:
            instrument = getattr(_orchestrator.context, 'instrument', instrument)

        return {
            "mode": execution_mode,
            "run_id": run_id,
            "instrument": instrument,
            "source": "redis" if execution_mode != "LIVE" else "default"
        }
    except Exception as e:
        # Fallback to default mode if Redis is unavailable
        logger.warning(f"Failed to get mode info from Redis: {e}")
        return {
            "mode": "LIVE",
            "run_id": None,
            "instrument": "BANKNIFTY",
            "source": "fallback"
        }

@app.post("/api/v1/analyze")
async def analyze_endpoint_v1():
    """Run orchestrator analysis cycle using configured instrument."""
    from config import get_config
    config = get_config()
    return await _run_analysis(config.instrument_symbol)

async def _run_analysis(instrument: str, context_override: Optional[Dict[str, Any]] = None):
    """Internal function to run orchestrator analysis."""
    global _orchestrator

    try:
        logger.info(f"Running manual orchestrator analysis for {instrument}")

        if not _orchestrator:
            logger.error("Orchestrator not initialized")
            return {"status": "error", "message": "Orchestrator not initialized"}

        # Run orchestrator cycle (don't set instrument - let orchestrator use its configured one)
        context = {
            "timestamp": datetime.now(),
            "market_hours": True,
            "cycle_interval": "manual",
            "manual_run": True
        }

        # Merge any context override
        if context_override:
            context.update(context_override)

        # Add execution mode to context for orchestrator decision logic
        redis_client = get_redis_client()
        execution_mode = redis_client.get("system:execution_mode")
        if execution_mode:
            execution_mode = execution_mode.decode() if isinstance(execution_mode, bytes) else execution_mode
        else:
            execution_mode = "LIVE"
        context["execution_mode"] = execution_mode
        logger.info(f"API: Set execution_mode in context: {execution_mode}")
        virtual_time_enabled = redis_client.get("system:virtual_time:enabled")
        if virtual_time_enabled:
            virtual_time_str = virtual_time_enabled.decode() if isinstance(virtual_time_enabled, bytes) else virtual_time_enabled
            if virtual_time_str == "1":
                virtual_time_current = redis_client.get("system:virtual_time:current")
                if virtual_time_current:
                    virtual_time_str = virtual_time_current.decode() if isinstance(virtual_time_current, bytes) else virtual_time_current
                    try:
                        current_time_ist = datetime.fromisoformat(virtual_time_str)
                        if current_time_ist.tzinfo is None:
                            current_time_ist = current_time_ist.replace(tzinfo=IST)
                        logger.debug(f"Using virtual time for analysis: {current_time_ist.strftime('%H:%M:%S %Z')}")
                    except Exception as e:
                        logger.warning(f"Failed to parse virtual time, using real time: {e}")
                        current_time_ist = datetime.now(IST)
                else:
                    current_time_ist = datetime.now(IST)
            else:
                current_time_ist = datetime.now(IST)
        else:
            current_time_ist = datetime.now(IST)

        market_open = is_market_open(current_time_ist)

        # In BACKTEST mode, always consider market open
        if execution_mode == "BACKTEST":
            market_open = True
            logger.info("BACKTEST mode: Forcing market_hours to True")

        context["market_hours"] = market_open
        context["timestamp"] = current_time_ist

        if not market_open:
            logger.info(f"Market is CLOSED (current time: {current_time_ist.strftime('%Y-%m-%d %H:%M:%S %Z')})")
        else:
            logger.info(f"Market is OPEN (current time: {current_time_ist.strftime('%Y-%m-%d %H:%M:%S %Z')})")

        result = await _orchestrator.run_cycle(context)

        # Publish the result to Redis so UI can receive it via WebSocket
        try:
            # Extract agent responses from the TradingDecision
            agent_responses = []
            if hasattr(result, 'agent_results') and result.agent_results:
                agent_responses = [
                    {
                        "agent": getattr(ar, 'agent', 'unknown'),
                        "decision": str(getattr(ar, 'decision', 'HOLD')),
                        "confidence": float(getattr(ar, 'confidence', 0.0))
                    } for ar in result.agent_results
                ]
            else:
                logger.warning("No agent_results found in TradingDecision")
                # Provide fallback agent responses
                agent_responses = []

            # Publish to Redis channels for UI
            import redis
            import json
            redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

            # Use the configured instrument (what the orchestrator actually used)
            from config import get_config
            config = get_config()
            decision_data = {
                "instrument": config.instrument_symbol,
                "decision": str(result.decision) if result.decision else "HOLD",
                "confidence": float(result.confidence) if result.confidence is not None else 0.0,
                "reasoning": getattr(result, 'reasoning', ''),
                "timestamp": datetime.now(IST).isoformat(),
                "agent_responses": agent_responses,
                "manual_run": True
            }

            # Publish to orchestrator decision channels
            redis_client.publish("engine:orchestrator_decision", json.dumps(decision_data))
            redis_client.publish(f"engine:orchestrator_decision:{instrument}", json.dumps(decision_data))


        except Exception as e:
            logger.exception(f"Failed to publish manual analysis to Redis: {e}")

        # Save agent decisions to MongoDB for agent status display
        try:
            mongo_client = get_mongo_client()
            db = mongo_client["zerodha_trading"]
            agent_discussions = db["agent_discussions"]

            # Extract agent signals from agent_results or aggregated_analysis
            agent_signals = agent_responses  # We already have them in the right format

            # Save each agent's decision
            timestamp = datetime.now(IST)
            saved_count = 0
            for entry in agent_signals:
                if isinstance(entry, dict) and entry.get("agent"):
                    agent_name = entry.get("agent", "Unknown Agent")
                    signal = entry.get("decision")
                    if signal:  # Only save if we have a decision
                        confidence = entry.get("confidence", 0.0)

                        discussion_doc = {
                            "timestamp": timestamp.isoformat(),
                            "agent_name": agent_name,
                            "signal": signal,
                            "decision": signal,  # Alias for compatibility
                            "confidence": float(confidence) if confidence is not None else 0.0,
                            "reasoning": entry.get("reasoning", ""),
                            "indicators": entry.get("indicators", {}),
                            "instrument": config.instrument_symbol,
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
                                "instrument": instrument
                            }
                            redis_client.publish("engine:decision", json.dumps(decision_data))
                            redis_client.publish(f"engine:decision:{instrument}", json.dumps(decision_data))

                            # Persist last decision in Redis for "replay on subscribe"
                            # Publish to Redis with run isolation
                            from .system_context import get_cache_manager
                            cache_manager = get_cache_manager()
                            cache_manager.set(f"engine:decision:{instrument}:latest", json.dumps(decision_data), expire_seconds=3600)  # 1 hour
                            cache_manager.set("engine:decision:latest", json.dumps(decision_data), expire_seconds=3600)
                        except Exception as pub_err:
                            logger.debug(f"Failed to publish decision to Redis pub/sub: {pub_err}")

            if saved_count > 0:
                logger.info(f"Saved {saved_count} agent decisions to MongoDB")

        except Exception as save_error:
            logger.warning(f"Failed to save agent decisions to MongoDB: {save_error}", exc_info=True)
            # Continue even if save fails

        # Format response for UI
        from config import get_config
        config = get_config()
        response = {
            "status": "success",
            "message": "Analysis completed successfully",
            "instrument": config.instrument_symbol,
            "decision": str(result.decision) if result.decision else "HOLD",
            "confidence": float(result.confidence) if result.confidence is not None else 0.0,
            "details": {"agent_results": agent_responses, "reasoning": getattr(result, 'reasoning', '')},
            "agent_responses": agent_responses,  # Include agent responses in HTTP response
            "timestamp": datetime.now(IST).isoformat()
        }

        logger.info(f"Manual analysis completed: {result.decision} ({result.confidence:.2f})")
        return response

    except Exception as e:
        logger.exception(f"Error in manual analysis: {e}")
        return {"status": "error", "message": f"Analysis failed: {str(e)}"}


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
        
        # Get current indicator values for enriching conditions
        current_indicators = {}
        try:
            from .redis_providers import RedisTechnicalDataProvider
            from .api_service import get_redis_client
            redis_client = get_redis_client()
            provider = RedisTechnicalDataProvider(redis_client)
            current_indicators = await provider.get_indicators(instrument)
        except Exception as e:
            logger.warning(f"Could not fetch current indicators: {e}")

        def enrich_conditions(conditions):
            """Add current_value to conditions if available."""
            if not conditions:
                return conditions
            enriched = []
            for condition in conditions:
                enriched_condition = dict(condition)
                indicator_name = condition.get('indicator')
                if indicator_name and indicator_name in current_indicators:
                    enriched_condition['current_value'] = current_indicators[indicator_name]
                enriched.append(enriched_condition)
            return enriched

        return [
            SignalResponse(
                signal_id=signal.get("signal_id") or signal.get("condition_id") or str(signal.get("_id", "")),
                instrument=signal.get("instrument", instrument),
                action=signal.get("action", "HOLD"),
                confidence=signal.get("confidence", 0.0),
                reasoning=signal.get("reasoning") or (signal.get('metadata') or {}).get('reasoning'),
                timestamp=signal.get("created_at", signal.get("timestamp", datetime.now(IST).isoformat())),
                entry_price=signal.get('entry_price'),
                execution_mode=signal.get('execution_mode') or (signal.get('metadata') or {}).get('execution_mode'),
                parsed_conditions=enrich_conditions(signal.get('parsed_conditions') or (signal.get('metadata') or {}).get('parsed_conditions')),
                reason_hash=signal.get('reason_hash') or (signal.get('metadata') or {}).get('reason_hash'),
                indicator=signal.get('indicator'),
                threshold=signal.get('threshold'),
                additional_conditions=signal.get('additional_conditions'),
                status=signal.get('status'),
                metadata=signal.get('metadata')
            )
            for signal in signals
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/signals/test-realtime")
async def test_realtime_signal_monitoring(instrument: str = "BANKNIFTY26JANFUT"):
    """Test if real-time signal monitoring is working."""
    try:
        from .signal_monitor import get_signal_monitor
        signal_monitor = get_signal_monitor()

        # Get active signals
        active_signals = signal_monitor.get_active_signals(instrument)
        active_count = len(active_signals)

        # Try to check signals manually
        try:
            triggered_events = await signal_monitor.check_signals(instrument)
            triggered_count = len(triggered_events)
        except Exception as e:
            return {
                "status": "error",
                "message": f"Signal check failed: {str(e)}",
                "active_signals": active_count
            }

        # Get current indicators
        try:
            from market_data.technical_indicators_service import get_technical_service
            tech_service = get_technical_service()
            indicators = tech_service.get_indicators_dict(instrument)
            rsi_value = indicators.get('rsi_14') if indicators else None
        except Exception as e:
            rsi_value = f"Error getting indicators: {str(e)}"

        return {
            "status": "success",
            "active_signals": active_count,
            "triggered_events": triggered_count,
            "current_rsi": rsi_value,
            "instrument": instrument,
            "signal_monitor_active": signal_monitor is not None
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


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


@app.post("/api/v1/generate-strikes")
async def generate_strikes(request: dict):
    """Generate optimal strike prices for options strategies using REAL market data."""
    try:
        strategy = request.get("strategy", "IRON_CONDOR")
        instrument = request.get("instrument", "BANKNIFTY")
        provided_market_data = request.get("market_data", {})

        # CRITICAL: Always fetch REAL market data first
        real_market_data = await get_real_market_data(instrument)

        # Merge with any provided data (provided data takes precedence for testing)
        if provided_market_data:
            real_market_data.update(provided_market_data)
            real_market_data["data_quality"] = "TEST_OVERRIDE"
            logger.info(f"⚠️ Using test market data override for {instrument}")

        # Log data quality for monitoring
        data_quality = real_market_data.get("data_quality", "UNKNOWN")
        if data_quality == "FALLBACK":
            logger.warning(f"🚨 STRATEGY ALERT: Using fallback data for {instrument} - strikes may be inaccurate!")
        elif data_quality == "PARTIAL":
            logger.info(f"ℹ️ Partial real data for {instrument} - some defaults used")
        else:
            logger.info(f"[OK] Full real market data for {instrument}")

        # Generate strikes based on strategy and REAL market conditions
        strike_response = await generate_strategy_strikes(strategy, instrument, real_market_data)

        # Add data quality metadata to response
        strike_response["market_data_quality"] = data_quality
        strike_response["data_source"] = real_market_data.get("data_source", "unknown")
        strike_response["generated_at"] = datetime.now(IST).isoformat()

        return strike_response

    except Exception as e:
        logger.exception("Error generating strikes: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

async def get_real_market_data(instrument: str) -> dict:
    """Get real market data from Redis with comprehensive validation."""
    try:
        redis_client = get_redis_client()

        # Extract base instrument name (remove expiry, FUT, etc.)
        base_instrument = instrument.upper().split('26')[0].split('27')[0]  # Remove year codes
        if 'FUT' in instrument.upper():
            # For futures, try both specific and general keys
            specific_key = f"price:{instrument}:latest"
            general_key = f"price:{base_instrument}:latest"
        else:
            specific_key = f"price:{instrument}:latest"
            general_key = f"price:{base_instrument}:latest"

        # STEP 1: Get real spot price from Redis
        spot_price = None
        price_timestamp = None

        # Try specific instrument first (e.g., BANKNIFTY26JANFUT)
        spot_price_raw = redis_client.get(specific_key)
        if spot_price_raw:
            try:
                spot_price = float(spot_price_raw)
                # Get timestamp
                ts_key = f"price:{instrument}:latest_ts"
                ts_raw = redis_client.get(ts_key)
                if ts_raw:
                    price_timestamp = ts_raw.decode() if isinstance(ts_raw, bytes) else ts_raw
                logger.info(f"[OK] Real spot price found for {instrument}: ₹{spot_price}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid spot price data for {instrument}: {spot_price_raw}")

        # Fallback to general instrument (e.g., BANKNIFTY)
        if spot_price is None:
            spot_price_raw = redis_client.get(general_key)
            if spot_price_raw:
                try:
                    spot_price = float(spot_price_raw)
                    logger.info(f"[OK] Fallback spot price found for {base_instrument}: ₹{spot_price}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid fallback spot price data for {base_instrument}: {spot_price_raw}")

        # STEP 2: Get real RSI from Redis
        rsi = None
        rsi_key = f"indicators:{instrument}:rsi_14"
        rsi_raw = redis_client.get(rsi_key)
        if rsi_raw:
            try:
                rsi = float(rsi_raw)
                logger.info(f"[OK] Real RSI found for {instrument}: {rsi:.2f}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid RSI data for {instrument}: {rsi_raw}")

        # STEP 3: Get real volatility level from Redis
        volatility_level = None
        vol_key = f"indicators:{instrument}:volatility_level"
        vol_raw = redis_client.get(vol_key)
        if vol_raw:
            volatility_level = vol_raw.decode() if isinstance(vol_raw, bytes) else vol_raw
            logger.info(f"[OK] Real volatility level found for {instrument}: {volatility_level}")

        # Convert volatility level to numeric value
        vol_numeric = {
            "LOW": 12,
            "MEDIUM": 18,
            "HIGH": 25,
            "VERY_HIGH": 35
        }.get(volatility_level, 18)  # Default to 18% if unknown

        # STEP 4: Determine trend from RSI
        trend = "SIDEWAYS"  # Default
        if rsi is not None:
            if rsi > 65:
                trend = "TRENDING_UP"
            elif rsi < 35:
                trend = "TRENDING_DOWN"
            else:
                trend = "SIDEWAYS"
            logger.info(f"[OK] Trend determined from RSI: {trend}")

        # STEP 5: Validate data completeness and freshness
        data_quality = "FULL"  # FULL, PARTIAL, FALLBACK

        if spot_price is None:
            data_quality = "FALLBACK"
            logger.warning(f"❌ No real spot price available for {instrument}")
        elif rsi is None:
            data_quality = "PARTIAL"
            logger.warning(f"⚠️ No real RSI available for {instrument}, using defaults")
        elif volatility_level is None:
            data_quality = "PARTIAL"
            logger.warning(f"⚠️ No real volatility available for {instrument}, using defaults")

        # If we have no real data at all, mark as fallback
        if spot_price is None and rsi is None and volatility_level is None:
            data_quality = "FALLBACK"
            logger.error(f"❌ No real market data available for {instrument} - using fallbacks")

        return {
            "spot_price": spot_price,
            "volatility": vol_numeric,
            "rsi": rsi,
            "trend": trend,
            "volatility_level": volatility_level,
            "data_quality": data_quality,
            "price_timestamp": price_timestamp,
            "timestamp": datetime.now(IST).isoformat(),
            "instrument": instrument,
            "data_source": "redis_real" if data_quality != "FALLBACK" else "fallback_defaults"
        }

    except Exception as e:
        logger.exception(f"Error fetching real market data for {instrument}: {e}")
        return await get_fallback_market_data(instrument)

async def get_fallback_market_data(instrument: str) -> dict:
    """Get fallback market data when real data is completely unavailable."""
    logger.warning(f"⚠️ Using fallback market data for {instrument} - STRATEGY GENERATION MAY BE INACCURATE")

    # Only use realistic defaults, never wrong hardcoded values
    if "BANKNIFTY" in instrument:
        # Use reasonable current ranges, not wrong hardcoded values
        spot_price = 60000  # Approximate current level (not 44000!)
        volatility = 18
        rsi = 50
        trend = "SIDEWAYS"
    elif "NIFTY" in instrument:
        spot_price = 22000
        volatility = 15
        rsi = 50
        trend = "SIDEWAYS"
    else:
        spot_price = 1000
        volatility = 20
        rsi = 50
        trend = "SIDEWAYS"

    return {
        "spot_price": spot_price,
        "volatility": volatility,
        "rsi": rsi,
        "trend": trend,
        "data_quality": "FALLBACK",
        "timestamp": datetime.now(IST).isoformat(),
        "warning": "Using fallback market data - strike prices may not reflect current market conditions"
    }

async def generate_strategy_strikes(strategy: str, instrument: str, market_data: dict) -> dict:
    """Generate strike prices for specific strategies using REAL market data."""

    # CRITICAL: Try to use real options chain data first
    real_options_data = await get_real_options_chain_data(instrument)

    if real_options_data and real_options_data.get("success"):
        # Use real market data for strike generation
        logger.info(f"[OK] Using REAL options chain data for {instrument}")
        return await generate_strategy_from_real_data(strategy, instrument, real_options_data, market_data)
    else:
        # Fallback to algorithmic generation with available market data
        logger.warning(f"⚠️ No real options data available for {instrument}, using algorithmic generation")
        spot_price = market_data.get("spot_price", 60000)  # Use real spot if available
        volatility = market_data.get("volatility", 18)
        rsi = market_data.get("rsi", 50)
        trend = market_data.get("trend", "SIDEWAYS")

        if strategy.upper() == "IRON_CONDOR":
            return await generate_iron_condor_strikes(spot_price, volatility, rsi, trend)
        elif strategy.upper() == "BULL_CALL_SPREAD":
            return await generate_bull_call_spread_strikes(spot_price, volatility, rsi, trend)
        else:
            return await generate_iron_condor_strikes(spot_price, volatility, rsi, trend)

async def get_real_options_chain_data(instrument: str) -> dict:
    """Fetch real options chain data from market data service."""
    try:
        from market_data.api_service import get_options_chain

        # Get options chain for the instrument
        options_response = await get_options_chain(instrument=instrument)

        if options_response and hasattr(options_response, 'strikes') and options_response.strikes:
            # Convert API response format to our expected format
            # API returns flat strikes format, we need to convert to calls/puts arrays

            calls = []
            puts = []

            for strike_data in options_response.strikes:
                strike_price = strike_data.get("strike")

                # Add call data
                if strike_data.get("ce_ltp") is not None:
                    calls.append({
                        "strike": strike_price,
                        "last_price": strike_data.get("ce_ltp"),
                        "bid": strike_data.get("ce_bid"),
                        "ask": strike_data.get("ce_ask"),
                        "oi": strike_data.get("ce_oi", 0),
                        "volume": strike_data.get("ce_volume", 0),
                        "iv": strike_data.get("ce_iv")
                    })

                # Add put data
                if strike_data.get("pe_ltp") is not None:
                    puts.append({
                        "strike": strike_price,
                        "last_price": strike_data.get("pe_ltp"),
                        "bid": strike_data.get("pe_bid"),
                        "ask": strike_data.get("pe_ask"),
                        "oi": strike_data.get("pe_oi", 0),
                        "volume": strike_data.get("pe_volume", 0),
                        "iv": strike_data.get("pe_iv")
                    })

            return {
                "success": True,
                "calls": calls,
                "puts": puts,
                "underlying_price": getattr(options_response, 'futures_price', None),
                "expiry": getattr(options_response, 'expiry', None),
                "timestamp": getattr(options_response, 'timestamp', None),
                "pcr": getattr(options_response, 'pcr', None),
                "max_pain": getattr(options_response, 'max_pain', None)
            }
        else:
            logger.warning(f"No options chain data available for {instrument}")
            return {"success": False}

    except Exception as e:
        logger.exception(f"Error fetching real options data for {instrument}: {e}")
        return {"success": False}

async def generate_strategy_from_real_data(strategy: str, instrument: str, options_data: dict, market_data: dict) -> dict:
    """Generate strategy using real options chain data."""

    if strategy.upper() == "IRON_CONDOR":
        return await generate_iron_condor_from_real_data(options_data, market_data)
    else:
        # Default to iron condor
        return await generate_iron_condor_from_real_data(options_data, market_data)

async def generate_iron_condor_from_real_data(options_data: dict, market_data: dict) -> dict:
    """Generate IRON_CONDOR using real market options data."""

    calls = options_data.get("calls", [])
    puts = options_data.get("puts", [])
    underlying_price = options_data.get("underlying_price", market_data.get("spot_price", 60000))

    if not calls or not puts:
        # Fallback if no real data
        return await generate_iron_condor_strikes(underlying_price, 18, 50, "SIDEWAYS")

    try:
        # Find optimal strikes for iron condor based on real market data
        # Strategy: Sell OTM calls and puts with good liquidity, buy further OTM for protection

        # Sort by strike price
        calls_sorted = sorted(calls, key=lambda x: x.get("strike", 0))
        puts_sorted = sorted(puts, key=lambda x: x.get("strike", 0))

        # Find strikes around underlying price
        atm_strike = min(calls_sorted, key=lambda x: abs(x.get("strike", 0) - underlying_price))

        # Select OTM strikes with good liquidity (prefer higher volume/OI)
        otm_puts = [p for p in puts_sorted if p.get("strike", 0) < underlying_price and (p.get("oi", 0) > 1000 or p.get("volume", 0) > 100)]
        otm_calls = [c for c in calls_sorted if c.get("strike", 0) > underlying_price and (c.get("oi", 0) > 1000 or c.get("volume", 0) > 100)]

        if len(otm_puts) < 2 or len(otm_calls) < 2:
            logger.warning("Insufficient liquid options for iron condor, using fallback")
            return await generate_iron_condor_strikes(underlying_price, 18, 50, "SIDEWAYS")

        # Select best strikes (highest volume/OI within reasonable range)
        sell_put = max(otm_puts[:5], key=lambda x: (x.get("oi", 0) + x.get("volume", 0)))  # Top 5, pick most liquid
        sell_call = max(otm_calls[:5], key=lambda x: (x.get("oi", 0) + x.get("volume", 0)))

        # Protective strikes (further OTM)
        protective_puts = [p for p in otm_puts if p.get("strike", 0) < sell_put.get("strike", 0)]
        protective_calls = [c for c in otm_calls if c.get("strike", 0) > sell_call.get("strike", 0)]

        buy_put = protective_puts[0] if protective_puts else sell_put  # Fallback to same strike if no further OTM
        buy_call = protective_calls[0] if protective_calls else sell_call

        # Use real market prices (bid/ask or last_price)
        def get_option_price(option):
            """Get realistic option price from market data."""
            if option.get("bid") and option.get("ask"):
                # Use mid price for fair value
                return round((option["bid"] + option["ask"]) / 2, 2)
            elif option.get("last_price"):
                return option["last_price"]
            else:
                # Estimate based on strike and underlying
                return max(10, round(abs(option.get("strike", underlying_price) - underlying_price) * 0.1, 2))

        # Build the strategy
        legs = [
            {
                "action": "SELL",
                "type": "PUT",
                "strike": sell_put.get("strike"),
                "quantity": 1,
                "premium": get_option_price(sell_put),
                "order": 1,
                "purpose": "Premium collection - bear protection"
            },
            {
                "action": "SELL",
                "type": "CALL",
                "strike": sell_call.get("strike"),
                "quantity": 1,
                "premium": get_option_price(sell_call),
                "order": 2,
                "purpose": "Premium collection - bull protection"
            },
            {
                "action": "BUY",
                "type": "PUT",
                "strike": buy_put.get("strike"),
                "quantity": 1,
                "premium": get_option_price(buy_put),
                "order": 3,
                "purpose": "Protection - limits downside risk"
            },
            {
                "action": "BUY",
                "type": "CALL",
                "strike": buy_call.get("strike"),
                "quantity": 1,
                "premium": get_option_price(buy_call),
                "order": 4,
                "purpose": "Protection - limits upside risk"
            }
        ]

        # Calculate net premium and risk metrics
        total_premium_collected = sum(leg["premium"] for leg in legs if leg["action"] == "SELL")
        total_premium_paid = sum(leg["premium"] for leg in legs if leg["action"] == "BUY")
        net_premium = total_premium_collected - total_premium_paid

        # Max loss calculation (wing width minus net premium)
        wing_width = max(leg["strike"] for leg in legs) - min(leg["strike"] for leg in legs)
        max_loss = wing_width - net_premium

        # Breakeven calculation
        lower_breakeven = min(leg["strike"] for leg in legs if leg["action"] == "BUY" and leg["type"] == "PUT") - net_premium
        upper_breakeven = max(leg["strike"] for leg in legs if leg["action"] == "BUY" and leg["type"] == "CALL") + net_premium

        rationale = f"""IRON_CONDOR Strategy using REAL market data:
• Underlying: ₹{underlying_price:,.0f}
• Sell Put: ₹{sell_put.get('strike'):,.0f} (OI: {sell_put.get('oi', 0):,})
• Sell Call: ₹{sell_call.get('strike'):,.0f} (OI: {sell_call.get('oi', 0):,})
• Buy Put: ₹{buy_put.get('strike'):,.0f} (protection)
• Buy Call: ₹{buy_call.get('strike'):,.0f} (protection)
• Net Premium: ₹{net_premium:.2f} collected
• Max Loss: ₹{max_loss:.2f} (wing width minus premium)
• Selected based on highest liquidity options available in market"""

        return {
            "strategy": "IRON_CONDOR",
            "legs": legs,
            "maxProfit": f"₹{net_premium:.2f}",
            "maxLoss": f"₹{max_loss:.2f}",
            "breakeven": f"₹{lower_breakeven:,.0f} - ₹{upper_breakeven:,.0f}",
            "rationale": rationale,
            "marketAnalysis": {
                "underlying_price": underlying_price,
                "data_source": "real_options_chain",
                "confidence": 0.85
            }
        }

    except Exception as e:
        logger.exception("Error generating iron condor from real data")
        # Fallback to algorithmic generation
        return await generate_iron_condor_strikes(underlying_price, 18, 50, "SIDEWAYS")

async def generate_iron_condor_strikes(spot_price: float, volatility: float, rsi: float, trend: str) -> dict:
    """Generate IRON_CONDOR strikes using trader logic.

    Trader approach:
    1. Assess market conditions (volatility, trend, RSI)
    2. Determine range width based on volatility
    3. Select strikes with good liquidity (round numbers)
    4. Position for premium collection with defined risk
    5. Order: Sell premium first, then buy protection
    """

    # Step 1: Calculate range based on volatility and market conditions
    base_range_pct = 0.04  # 4% base range
    vol_adjustment = volatility / 100 * 0.02  # Additional range for high vol
    total_range_pct = base_range_pct + vol_adjustment

    # Adjust for trend and RSI
    if trend == "TRENDING_UP" and rsi > 60:
        # Market bullish, position condor higher
        range_center = spot_price * 1.005
    elif trend == "TRENDING_DOWN" and rsi < 40:
        # Market bearish, position condor lower
        range_center = spot_price * 0.995
    else:
        # Neutral/Sideways
        range_center = spot_price

    range_width = range_center * total_range_pct

    # Step 2: Select strikes (trader prefers round numbers for liquidity)
    lower_put_strike = round((range_center - range_width) / 100) * 100
    upper_put_strike = round((range_center - range_width * 0.3) / 100) * 100
    lower_call_strike = round((range_center + range_width * 0.3) / 100) * 100
    upper_call_strike = round((range_center + range_width) / 100) * 100

    # Step 3: Calculate realistic premiums based on volatility and time to expiry
    # Higher vol = higher premiums
    premium_base = volatility * 0.8  # Base premium per strike

    # Step 4: Define trade order (market maker approach)
    legs = [
        # First: Sell the premium (most important - get paid)
        {
            "action": "SELL",
            "type": "PUT",
            "strike": lower_put_strike,
            "quantity": 1,
            "premium": round(premium_base * 1.2),  # Higher premium for OTM puts
            "order": 1,
            "purpose": "Premium collection - bear protection"
        },
        {
            "action": "SELL",
            "type": "CALL",
            "strike": lower_call_strike,
            "quantity": 1,
            "premium": round(premium_base * 1.1),  # Slightly lower for calls
            "order": 2,
            "purpose": "Premium collection - bull protection"
        },
        # Then: Buy protection (hedge the risk)
        {
            "action": "BUY",
            "type": "PUT",
            "strike": upper_put_strike,
            "quantity": 1,
            "premium": round(premium_base * 0.8),
            "order": 3,
            "purpose": "Protection - limits downside risk"
        },
        {
            "action": "BUY",
            "type": "CALL",
            "strike": upper_call_strike,
            "quantity": 1,
            "premium": round(premium_base * 0.7),
            "order": 4,
            "purpose": "Protection - limits upside risk"
        }
    ]

    # Step 5: Calculate risk metrics
    total_premium_collected = sum(leg["premium"] for leg in legs if leg["action"] == "SELL")
    total_premium_paid = sum(leg["premium"] for leg in legs if leg["action"] == "BUY")
    net_premium = total_premium_collected - total_premium_paid
    max_loss = (upper_call_strike - upper_put_strike) - net_premium

    # Step 6: Generate rationale
    rationale = f"""IRON_CONDOR Strategy Analysis:
• Market conditions: {volatility}% volatility, RSI {rsi}, {trend} trend
• Range expectation: ₹{range_center:.0f} ±{total_range_pct*100:.1f}% (₹{range_width:.0f})
• Strike selection: {lower_put_strike}-{upper_put_strike} puts, {lower_call_strike}-{upper_call_strike} calls
• Net premium: ₹{net_premium} collected
• Risk/Reward: ₹{net_premium} max profit vs ₹{max_loss} max loss
• Execution order: Sell premium first (puts/calls), then buy protection
• Market maker approach prioritizes premium collection with defined risk limits"""

    return {
        "strategy": "IRON_CONDOR",
        "legs": legs,
        "maxProfit": f"₹{net_premium}",
        "maxLoss": f"₹{max_loss}",
        "breakeven": f"{upper_put_strike - net_premium} - {upper_call_strike + net_premium}",
        "rationale": rationale,
        "marketAnalysis": {
            "volatility": volatility,
            "rsi": rsi,
            "trend": trend,
            "rangeWidth": range_width,
            "confidence": 0.72
        }
    }

async def generate_bull_call_spread_strikes(spot_price: float, volatility: float, rsi: float, trend: str) -> dict:
    """Generate BULL_CALL_SPREAD strikes using trader logic."""

    # Bull call spread: Buy ITM/ATM call, Sell OTM call
    lower_strike = round(spot_price * 0.98 / 100) * 100  # Slightly ITM
    upper_strike = round(spot_price * 1.05 / 100) * 100  # OTM

    premium_base = volatility * 0.6

    legs = [
        {
            "action": "BUY",
            "type": "CALL",
            "strike": lower_strike,
            "quantity": 1,
            "premium": round(premium_base * 1.5),
            "order": 1,
            "purpose": "Bullish position - profit from upside"
        },
        {
            "action": "SELL",
            "type": "CALL",
            "strike": upper_strike,
            "quantity": 1,
            "premium": round(premium_base * 0.8),
            "order": 2,
            "purpose": "Premium collection - limits upside risk"
        }
    ]

    net_debit = legs[0]["premium"] - legs[1]["premium"]
    max_profit = (upper_strike - lower_strike) - net_debit
    max_loss = net_debit

    return {
        "strategy": "BULL_CALL_SPREAD",
        "legs": legs,
        "maxProfit": f"₹{max_profit}",
        "maxLoss": f"₹{max_loss}",
        "breakeven": f"{lower_strike + net_debit}",
        "rationale": f"Bull call spread for bullish outlook. Net debit: ₹{net_debit}. Profit above {lower_strike + net_debit}.",
        "marketAnalysis": {
            "volatility": volatility,
            "rsi": rsi,
            "trend": trend,
            "confidence": 0.68
        }
    }

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
        from .system_context import get_cache_manager, get_system_context

        cache_manager = get_cache_manager()
        system_context = get_system_context()

        # Check for latest decision in cache (run-specific)
        cached_decision = cache_manager.get("engine:decision:latest")
        if cached_decision:
            import json
            return json.loads(cached_decision)

        if _orchestrator is None:
            # No orchestrator available - return proper error
            raise HTTPException(
                status_code=503,
                detail="Trading system not initialized. No real trading decisions available."
            )
        
        # Get latest decision from MongoDB with run isolation
        mongo_client = get_mongo_client()
        db_name = os.getenv("MONGODB_DATABASE", "zerodha_trading")
        db = mongo_client[db_name]
        signals_collection = db["signals"]

        # Filter by current run and mode
        run_filter = system_context.get_db_filter()

        # Get most recent signal for this run
        latest_signal = signals_collection.find_one(
            run_filter,
            sort=[("timestamp", -1)]
        )

        if latest_signal:
            return {
                "instrument": latest_signal.get("instrument", "BANKNIFTY"),
                "signal": latest_signal.get("action", "HOLD"),
                "confidence": float(latest_signal.get("confidence", 0.0)),
                "reasoning": latest_signal.get("reasoning", ""),
                "timestamp": latest_signal.get("timestamp", datetime.now(IST).isoformat()),
                "run_id": latest_signal.get("run_id", system_context.run_id),
                "mode": latest_signal.get("mode", system_context.mode)
            }

        return {
            "instrument": "BANKNIFTY",
            "signal": "HOLD",
            "confidence": 0.0,
            "reasoning": f"No decisions available for run {system_context.run_id} in {system_context.mode} mode",
            "timestamp": datetime.now(IST).isoformat(),
            "run_id": system_context.run_id,
            "mode": system_context.mode
        }
    except Exception as e:
        logger.exception("Error getting latest decision: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/orchestrator-decisions")
async def get_orchestrator_decisions(limit: int = 20):
    """Get recent orchestrator decisions from MongoDB."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client["zerodha_trading"]
        decisions_collection = db["orchestrator_decisions"]

        # Get recent decisions
        cursor = decisions_collection.find(
            {},
            sort=[("timestamp", -1)]
        ).limit(limit)

        decisions = []
        for doc in cursor:
            # Convert ObjectId to string for JSON serialization
            doc["_id"] = str(doc["_id"])
            decisions.append(doc)

        return {"decisions": decisions}

    except Exception as e:
        logger.exception(f"Error fetching orchestrator decisions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trading/execute-when-ready/{signal_id}")
async def execute_signal_when_ready(signal_id: str):
    """Enable monitoring for a signal to execute when conditions are met.

    This endpoint marks a signal for monitoring - the system will automatically
    execute it when all parsed conditions are satisfied.
    """
    try:
        # Get the signal from MongoDB
        mongo_client = get_mongo_client()
        db = mongo_client["zerodha_trading"]
        signals_collection = db["signals"]

        # Find the signal by signal_id, condition_id, or _id (MongoDB ObjectId)
        try:
            from bson import ObjectId
            # Try to convert to ObjectId for _id lookup
            object_id = ObjectId(signal_id)
            id_query = {"_id": object_id}
        except:
            id_query = None

        # Build query to check multiple fields
        query_conditions = [
            {"signal_id": signal_id},
            {"condition_id": signal_id}
        ]
        if id_query:
            query_conditions.append(id_query)

        signal = signals_collection.find_one({"$or": query_conditions})

        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")

        # Update the signal to enable monitoring
        signals_collection.update_one(
            {"_id": signal["_id"]},
            {"$set": {
                "monitoring_enabled": True,
                "monitoring_started_at": datetime.now(IST).isoformat(),
                "status": "monitoring"
            }}
        )

        return {
            "success": True,
            "signal_id": signal_id,
            "monitoring": True,
            "message": "Signal monitoring enabled. Will execute when conditions are met."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error enabling signal monitoring for {signal_id}: {e}")
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

@app.post("/api/v1/orchestrator/reinitialize")
async def reinitialize_orchestrator():
    """Reinitialize the orchestrator after fixing import issues."""
    global _orchestrator

    try:
        logger.info("Engine API: Reinitializing orchestrator...")

        # Check Redis connection
        redis_client = get_redis_client()
        redis_client.ping()

        # Check MongoDB connection
        mongo_client = get_mongo_client()
        mongo_client.admin.command('ping')

        # Import LLM provider manager and client builder
        from genai_module.core.llm_provider_manager import LLMProviderManager
        from genai_module.api import build_llm_client

        # Build LLM client
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

        # Get execution mode and run_id from Redis
        execution_mode = redis_client.get("system:execution_mode")
        run_id = redis_client.get("system:run_id")

        # Decode bytes if needed
        if execution_mode:
            execution_mode = execution_mode.decode() if isinstance(execution_mode, bytes) else execution_mode
        else:
            execution_mode = "LIVE"  # Default to LIVE mode

        if run_id:
            run_id = run_id.decode() if isinstance(run_id, bytes) else run_id

        logger.info(f"Engine API: Initializing in {execution_mode} mode" + (f" (run_id: {run_id})" if run_id else ""))

        # Create trading context
        from .enhanced_orchestrator import TradingContext
        from config import get_config
        config = get_config()
        context = TradingContext(
            instrument=config.instrument_symbol,  # Use configured instrument from environment
            mode=execution_mode,
            run_id=run_id
        )

        _orchestrator = build_orchestrator(
            llm_client=llm_client,
            redis_client=redis_client,
            agents=agents,
            signal_monitor=signal_monitor,
            mongo_db=mongo_db,
            context=context
        )
        logger.info("Engine API: Orchestrator reinitialized successfully")

        # Sync existing signals from MongoDB to SignalMonitor on startup
        if signal_monitor and mongo_db is not None:
            try:
                from .signal_creator import sync_signals_to_monitor
                synced = await sync_signals_to_monitor(mongo_db, signal_monitor)
                if synced > 0:
                    logger.info(f"Engine API: Synced {synced} existing signals to SignalMonitor on reinitialize")
            except Exception as sync_error:
                logger.warning(f"Engine API: Failed to sync signals on reinitialize: {sync_error}")

        return {
            "status": "success",
            "message": "Orchestrator reinitialized successfully",
            "execution_mode": execution_mode,
            "run_id": run_id,
            "instrument": config.instrument_symbol
        }

    except Exception as e:
        logger.exception(f"Engine API: Failed to reinitialize orchestrator: {e}")
        return {
            "status": "error",
            "message": f"Failed to reinitialize orchestrator: {str(e)}"
        }


@app.post("/api/v1/orchestrator/run_cycle")
async def run_orchestrator_cycle_endpoint():
    """Manually run an orchestrator cycle for testing WebSocket publishing."""
    global _orchestrator
    try:
        if _orchestrator is None:
            return {"status": "error", "message": "Orchestrator not initialized"}

        from datetime import datetime
        from config import get_config
        config = get_config()
        instrument = config.instrument_symbol

        redis_client = get_redis_client()
        execution_mode = redis_client.get("system:execution_mode")
        if execution_mode:
            execution_mode = execution_mode.decode() if isinstance(execution_mode, bytes) else execution_mode
        else:
            execution_mode = "LIVE"
        print(f"RUN_CYCLE_MODE: execution_mode={execution_mode}")

        # Check market hours for orchestrator decisions
        from core_kernel.src.core_kernel.market_hours import is_market_open
        from datetime import datetime, timezone
        from core_kernel.src.core_kernel.market_hours import IST

        # Use virtual time if available (historical mode)
        virtual_time_enabled = redis_client.get("system:virtual_time:enabled")
        if virtual_time_enabled:
            virtual_time_str = virtual_time_enabled.decode() if isinstance(virtual_time_enabled, bytes) else virtual_time_enabled
            if virtual_time_str == "1":
                virtual_time_current = redis_client.get("system:virtual_time:current")
                if virtual_time_current:
                    virtual_time_str = virtual_time_current.decode() if isinstance(virtual_time_current, bytes) else virtual_time_current
                    try:
                        current_time_ist = datetime.fromisoformat(virtual_time_str)
                        if current_time_ist.tzinfo is None:
                            current_time_ist = current_time_ist.replace(tzinfo=IST)
                    except Exception as e:
                        current_time_ist = datetime.now(IST)
                else:
                    current_time_ist = datetime.now(IST)
            else:
                current_time_ist = datetime.now(IST)
        else:
            current_time_ist = datetime.now(IST)

        market_open = is_market_open(current_time_ist)

        # In BACKTEST mode, always consider market open
        if execution_mode == "BACKTEST":
            market_open = True
            print("RUN_CYCLE: BACKTEST mode - Forcing market_hours to True")

        context = {
            'symbol': instrument,
            'timestamp': datetime.now(),
            'cycle_info': {'cycle_number': 1, 'duration_seconds': 0},
            'execution_mode': execution_mode,
            'market_hours': market_open
        }
        print(f"RUN_CYCLE_CONTEXT: market_hours={market_open}, execution_mode={execution_mode}")

        logger.info(f"Manually running orchestrator cycle for {instrument}")
        result = await _orchestrator.run_cycle(context)

        # Debug info - always include for troubleshooting
        execution_mode = context.get("execution_mode", "LIVE")
        debug_info = {
            "market_hours": context.get("market_hours", False),
            "execution_mode": execution_mode,
            "agent_count": len(getattr(result, 'agent_results', [])),
            "context_keys": list(context.keys()),
            "result_has_agent_results": hasattr(result, 'agent_results')
        }

        response_data = {
            "status": "success",
            "decision": str(result.decision) if result.decision else "HOLD",
            "confidence": float(result.confidence) if result.confidence is not None else 0.0,
            "reasoning": getattr(result, 'reasoning', ''),
            "agent_signals": len(getattr(result, 'agent_results', [])),
            "debug": debug_info
        }
        # Add execution flow info
        redis_client = get_redis_client()
        exec_mode = redis_client.get("system:execution_mode")
        if exec_mode:
            exec_mode = exec_mode.decode() if isinstance(exec_mode, bytes) else exec_mode
        else:
            exec_mode = "LIVE"

        response_data["execution_info"] = {
            "execution_mode": exec_mode,
            "market_hours": context.get("market_hours", False),
            "has_llm_client": hasattr(_orchestrator, 'llm_client') and _orchestrator.llm_client is not None,
            "redis_exec_mode": exec_mode
        }
        return response_data
    except Exception as e:
        logger.error(f"Failed to run orchestrator cycle: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# New agent inspection endpoints for UI
@app.get("/api/engine/agents/status")
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
                "BullResearcher", "BearResearcher", "ResearchManager", "OptionsStrategyAgent",
                "NeutralRiskAgent", "RiskManager", "ExecutionAgent"
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
                    # Return full decision object with reasoning
                    last_decision = {
                        "decision": latest_discussion.get("signal") or latest_discussion.get("decision"),
                        "confidence": latest_discussion.get("confidence", 0),
                        "reasoning": latest_discussion.get("reasoning", "Decision made"),
                        "additionalDetails": {
                            "reasoning": latest_discussion.get("reasoning", "Decision made")
                        }
                    }
                    updated_at = latest_discussion.get("timestamp", updated_at)
                else:
                    last_decision = {
                        "decision": "HOLD",
                        "confidence": 0,
                        "reasoning": "No recent decision available",
                        "additionalDetails": {
                            "reasoning": "No recent decision available"
                        }
                    }

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


@app.get("/api/engine/agents")
async def list_agents():
    """List available agents with basic metadata."""
    try:
        agent_list = []
        if _orchestrator is not None and hasattr(_orchestrator, 'agents') and _orchestrator.agents:
            for agent in _orchestrator.agents:
                name = getattr(agent, '_agent_name', agent.__class__.__name__)
                desc = (agent.__doc__ or '').strip().split('\n')[0] if getattr(agent, '__doc__', None) else ''
                has_memory = hasattr(agent, 'memory')
                agent_list.append({
                    'name': name,
                    'description': desc,
                    'has_memory': has_memory
                })
        else:
            # Fallback list
            defaults = [
                "TechnicalAgent", "SentimentAgent", "MacroAgent", "FundamentalAgent",
                "MomentumAgent", "TrendAgent", "VolumeAgent", "MeanReversionAgent",
                "BullResearcher", "BearResearcher", "ResearchManager", "OptionsStrategyAgent",
                "NeutralRiskAgent", "RiskManager", "ExecutionAgent"
            ]
            agent_list = [{'name': a, 'description': '', 'has_memory': a in ('BullResearcher', 'BearResearcher')} for a in defaults]
        return agent_list
    except Exception as e:
        logger.exception("Error listing agents: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/engine/agents/{agent_name}/details")
async def get_agent_details(agent_name: str):
    """Get detailed metadata and latest decision for an agent."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[os.getenv("MONGODB_DATABASE", "zerodha_trading")]
        agent_discussions = db["agent_discussions"]

        latest = agent_discussions.find_one({"agent_name": agent_name}, sort=[("timestamp", -1)])

        # Attempt to get agent object for config/introspection
        config = {}
        if _orchestrator is not None and hasattr(_orchestrator, 'agents') and _orchestrator.agents:
            for a in _orchestrator.agents:
                name = getattr(a, '_agent_name', a.__class__.__name__)
                if name == agent_name:
                    # Expose a safe subset of properties
                    config = {}
                    if hasattr(a, 'config') and isinstance(a.config, dict):
                        config = a.config
                    else:
                        # Attempt to pick common attrs
                        for key in ('min_confidence', 'use_structured_reports', 'use_multi_timeframe'):
                            if hasattr(a, key):
                                config[key] = getattr(a, key)
                    break

        latest_serialized = _serialize_bson(latest) if latest else None
        return {
            'agent_name': agent_name,
            'latest_decision': latest_serialized,
            'config': config
        }
    except Exception as e:
        logger.exception("Error getting agent details: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/engine/agents/{agent_name}/history")
async def get_agent_history(agent_name: str, limit: int = 50):
    """Get historical decisions / responses saved for an agent (most recent first)."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[os.getenv("MONGODB_DATABASE", "zerodha_trading")]
        agent_discussions = db["agent_discussions"]

        cursor = agent_discussions.find({"agent_name": agent_name}).sort("timestamp", -1).limit(limit)
        results = []
        for doc in cursor:
            if doc.get('_id'):
                doc['_id'] = str(doc['_id'])
            results.append(doc)
        return results
    except Exception as e:
        logger.exception("Error fetching agent history: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/engine/agents/{agent_name}/responses/{response_id}")
async def get_agent_response(agent_name: str, response_id: str):
    """Get a single saved response for inspection."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[os.getenv("MONGODB_DATABASE", "zerodha_trading")]
        agent_discussions = db["agent_discussions"]

        # Try ObjectId first
        try:
            from bson import ObjectId
            query = {"_id": ObjectId(response_id)}
        except Exception:
            query = {"_id": response_id} if isinstance(response_id, str) else {"response_id": response_id}

        doc = agent_discussions.find_one(query)
        if not doc:
            # Try to find by response_id field
            doc = agent_discussions.find_one({"response_id": response_id, "agent_name": agent_name})
        if not doc:
            raise HTTPException(status_code=404, detail="Response not found")
        if doc.get('_id'):
            doc['_id'] = str(doc['_id'])
        return doc
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching agent response: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/engine/agents/{agent_name}/memory")
async def get_agent_memory(agent_name: str, q: str = None, limit: int = 10):
    """Get recent memories for an agent, or run a similarity search if query provided."""
    try:
        # Lazy import to avoid chromadb requirement if not present
        try:
            from engine_module.utils.memory import AgentMemory
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Memory subsystem unavailable: {e}")

        mem = AgentMemory(agent_name)
        if q:
            results = mem.retrieve_similar(q, n_results=limit)
        else:
            results = mem.get_recent_experiences(n_results=limit)
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching agent memory: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/engine/agents/dependencies")
async def get_agent_dependencies():
    """Return a simple dependency graph for agents (nodes + edges)."""
    try:
        # Build a conservative dependency graph based on known roles
        nodes = []
        edges = []

        # Try to enumerate agents from orchestrator
        agent_names = []
        if _orchestrator is not None and hasattr(_orchestrator, 'agents') and _orchestrator.agents:
            agent_names = [getattr(a, '_agent_name', a.__class__.__name__) for a in _orchestrator.agents]
        else:
            agent_names = [
                "TechnicalAgent", "SentimentAgent", "MacroAgent", "FundamentalAgent",
                "MomentumAgent", "TrendAgent", "VolumeAgent", "MeanReversionAgent",
                "BullResearcher", "BearResearcher", "ResearchManager", "OptionsStrategyAgent",
                "NeutralRiskAgent", "ConservativeRiskAgent", "AggressiveRiskAgent", "RiskManager", "ExecutionAgent"
            ]

        for name in agent_names:
            nodes.append({"id": name, "label": name})

        # Add common edges
        # Technical -> Momentum/Trend/MeanReversion/Volume
        for t in ["MomentumAgent", "TrendAgent", "MeanReversionAgent", "VolumeAgent"]:
            edges.append({"from": "TechnicalAgent", "to": t, "type": "data_flow"})

        # Bull/Bear -> ResearchManager
        edges.append({"from": "BullResearcher", "to": "ResearchManager", "type": "coordination"})
        edges.append({"from": "BearResearcher", "to": "ResearchManager", "type": "coordination"})

        # ResearchManager -> OptionsStrategyAgent
        edges.append({"from": "ResearchManager", "to": "OptionsStrategyAgent", "type": "coordination"})

        # Risk veto edges
        edges.append({"from": "NeutralRiskAgent", "to": "ExecutionAgent", "type": "veto"})
        edges.append({"from": "ConservativeRiskAgent", "to": "ExecutionAgent", "type": "veto"})
        edges.append({"from": "AggressiveRiskAgent", "to": "ExecutionAgent", "type": "veto"})

        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        logger.exception("Error building dependency graph: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/engine/agents/{agent_name}/config")
async def update_agent_config(agent_name: str, config: Dict[str, Any] = Body(...)):
    """Update agent configuration in-memory and persist a copy to MongoDB."""
    try:
        # Update in-orchestrator agent instance if present
        updated = False
        if _orchestrator is not None and hasattr(_orchestrator, 'agents') and _orchestrator.agents:
            for a in _orchestrator.agents:
                name = getattr(a, '_agent_name', a.__class__.__name__)
                if name == agent_name:
                    # Set attributes or config dict
                    if hasattr(a, 'config') and isinstance(a.config, dict):
                        a.config.update(config)
                    else:
                        for k, v in config.items():
                            try:
                                setattr(a, k, v)
                            except Exception:
                                pass
                    updated = True
                    break

        # Persist to MongoDB for long-term config
        mongo_client = get_mongo_client()
        db = mongo_client[os.getenv("MONGODB_DATABASE", "zerodha_trading")]
        configs = db["agent_configs"]
        configs.update_one({"agent_name": agent_name}, {"$set": {"config": config, "updated_at": datetime.now(IST).isoformat()}}, upsert=True)

        return {"success": True, "updated_in_memory": updated}
    except Exception as e:
        logger.exception("Failed to update agent config: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/engine/agents/{agent_name}/responses/{response_id}/structured_report")
async def get_agent_structured_report(agent_name: str, response_id: str):
    """Fetch the `structured_report` field for a saved response (if present)."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[os.getenv("MONGODB_DATABASE", "zerodha_trading")]
        agent_discussions = db["agent_discussions"]

        # Try ObjectId first
        try:
            from bson import ObjectId
            query = {"_id": ObjectId(response_id)}
        except Exception:
            query = {"response_id": response_id, "agent_name": agent_name}

        doc = agent_discussions.find_one(query)
        if not doc:
            raise HTTPException(status_code=404, detail="Response not found")

        structured = doc.get("details", {}).get("structured_report") or doc.get("structured_report")
        if structured is None:
            raise HTTPException(status_code=404, detail="Structured report not found in response")

        return {"response_id": response_id, "agent_name": agent_name, "structured_report": structured}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching structured report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DATA VALIDATION FRAMEWORK
# ============================================================================

class DataValidator:
    """Centralized data validation for all agents with fail-fast behavior."""

    # Maximum acceptable data age in minutes
    MAX_OHLC_AGE_MINUTES = 5
    MAX_INDICATOR_AGE_MINUTES = 5
    MAX_OPTIONS_AGE_MINUTES = 10  # Options data can be slightly older

    @staticmethod
    def validate_ohlc_data(ohlc_data: List[Dict], current_time: datetime) -> Dict[str, Any]:
        """Validate OHLC data freshness and completeness."""
        if not ohlc_data:
            return {
                "valid": False,
                "reason": "NO_OHLC_DATA",
                "exclusion_reason": "No OHLC price data available for analysis"
            }

        # Check data freshness
        latest_timestamp = None
        for bar in ohlc_data:
            if isinstance(bar, dict) and 'timestamp' in bar:
                try:
                    if isinstance(bar['timestamp'], str):
                        from dateutil import parser
                        ts = parser.parse(bar['timestamp'])
                    elif hasattr(bar['timestamp'], 'timestamp'):
                        ts = bar['timestamp']
                    else:
                        continue

                    if latest_timestamp is None or ts > latest_timestamp:
                        latest_timestamp = ts
                except:
                    continue

        age_minutes = None
        if latest_timestamp:
            age_minutes = (current_time - latest_timestamp).total_seconds() / 60
            if age_minutes > DataValidator.MAX_OHLC_AGE_MINUTES:
                return {
                    "valid": False,
                    "reason": "OHLC_DATA_STALE",
                    "age_minutes": age_minutes,
                    "exclusion_reason": f"OHLC data is {age_minutes:.1f} minutes old (stale)"
                }

        # Check data completeness
        required_fields = ['open', 'high', 'low', 'close']
        for bar in ohlc_data[:5]:  # Check first 5 bars
            missing_fields = [field for field in required_fields if field not in bar or bar[field] is None]
            if missing_fields:
                return {
                    "valid": False,
                    "reason": "OHLC_DATA_INCOMPLETE",
                    "missing_fields": missing_fields,
                    "exclusion_reason": f"OHLC data missing required fields: {missing_fields}"
                }

        return {"valid": True, "data_points": len(ohlc_data), "latest_age_minutes": age_minutes}

    @staticmethod
    def validate_technical_indicators(redis_indicators: Dict[str, Any], current_time: datetime) -> Dict[str, Any]:
        """Validate technical indicators from Redis."""
        if not redis_indicators:
            return {
                "valid": False,
                "reason": "NO_INDICATORS",
                "exclusion_reason": "No technical indicators available from Redis"
            }

        # Check for data freshness markers
        data_freshness = redis_indicators.get('_data_freshness', 'UNKNOWN')

        # Count available indicators (exclude metadata)
        indicator_count = len([k for k in redis_indicators.keys() if not k.startswith('_')])

        if indicator_count == 0:
            return {
                "valid": False,
                "reason": "NO_VALID_INDICATORS",
                "exclusion_reason": "No valid technical indicators found"
            }

        # Check for critical indicators
        critical_indicators = ['rsi', 'trend_direction', 'adx']
        missing_critical = [ind for ind in critical_indicators if not any(k.startswith(ind) or k == ind for k in redis_indicators.keys())]

        if missing_critical:
            return {
                "valid": False,
                "reason": "MISSING_CRITICAL_INDICATORS",
                "missing_indicators": missing_critical,
                "exclusion_reason": f"Missing critical indicators: {missing_critical}"
            }

        return {
            "valid": True,
            "indicator_count": indicator_count,
            "data_freshness": data_freshness,
            "missing_critical": missing_critical
        }

    @staticmethod
    def validate_options_data(options_data: Dict[str, Any], current_time: datetime) -> Dict[str, Any]:
        """Validate options chain data."""
        if not options_data or not options_data.get("success"):
            return {
                "valid": False,
                "reason": "NO_OPTIONS_DATA",
                "exclusion_reason": "No options chain data available"
            }

        calls = options_data.get("calls", [])
        puts = options_data.get("puts", [])
        underlying_price = options_data.get("underlying_price")

        if not calls or not puts:
            return {
                "valid": False,
                "reason": "INCOMPLETE_OPTIONS_DATA",
                "calls_count": len(calls),
                "puts_count": len(puts),
                "exclusion_reason": "Options chain missing calls or puts data"
            }

        if not underlying_price:
            return {
                "valid": False,
                "reason": "NO_UNDERLYING_PRICE",
                "exclusion_reason": "Options data missing underlying price"
            }

        # Check data freshness
        timestamp = options_data.get("timestamp")
        if timestamp:
            try:
                if isinstance(timestamp, str):
                    from dateutil import parser
                    data_time = parser.parse(timestamp)
                else:
                    data_time = timestamp

                age_minutes = (current_time - data_time).total_seconds() / 60
                if age_minutes > DataValidator.MAX_OPTIONS_AGE_MINUTES:
                    return {
                        "valid": False,
                        "reason": "OPTIONS_DATA_STALE",
                        "age_minutes": age_minutes,
                        "exclusion_reason": f"Options data is {age_minutes:.1f} minutes old"
                    }
            except Exception as e:
                logger.warning(f"Could not validate options data timestamp: {e}")

        # Check for liquid strikes
        liquid_calls = [c for c in calls if (c.get("oi", 0) > 500 or c.get("volume", 0) > 50)]
        liquid_puts = [p for p in puts if (p.get("oi", 0) > 500 or p.get("volume", 0) > 50)]

        if len(liquid_calls) < 3 or len(liquid_puts) < 3:
            return {
                "valid": False,
                "reason": "INSUFFICIENT_LIQUIDITY",
                "liquid_calls": len(liquid_calls),
                "liquid_puts": len(liquid_puts),
                "exclusion_reason": "Insufficient liquid options for strategy creation"
            }

        return {
            "valid": True,
            "calls_count": len(calls),
            "puts_count": len(puts),
            "liquid_calls": len(liquid_calls),
            "liquid_puts": len(liquid_puts),
            "underlying_price": underlying_price
        }

    @staticmethod
    def create_exclusion_result(validation_result: Dict[str, Any]) -> AnalysisResult:
        """Create a standardized exclusion result from validation."""
        return AnalysisResult(
            decision="EXCLUDED",
            confidence=0.0,
            details={
                "validation_result": validation_result,
                "data_available": False,
                "exclusion_reason": validation_result["exclusion_reason"]
            },
            excluded=True,
            exclusion_reason=validation_result["exclusion_reason"]
        )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("ENGINE_API_PORT", "8006"))
    host = os.getenv("ENGINE_API_HOST", "0.0.0.0")
    
    print(f"Starting Engine API on {host}:{port}")
    # Socket.IO removed - using FastAPI app directly
    uvicorn.run(app, host=host, port=port)

