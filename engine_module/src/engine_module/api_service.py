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
import redis
from pymongo import MongoClient

from .api import build_orchestrator
from .contracts import Orchestrator, AnalysisResult

logger = logging.getLogger(__name__)
# Ensure a basic logging configuration so messages appear and unicode is handled safely
logging.basicConfig(level=logging.INFO)

# IST timezone for Indian financial markets
IST = timezone(timedelta(hours=5, minutes=30))


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


# FastAPI app
app = FastAPI(
    title="Engine API",
    description="REST API for trading orchestrator, signals, and agent analysis",
    version="1.0.0"
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


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global _orchestrator
    
    try:
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
            
            # Build orchestrator with Redis client for market data and agents
            logger.info("Engine API: Building orchestrator...")
            _orchestrator = build_orchestrator(
                llm_client=llm_client,
                redis_client=redis_client,
                agents=agents,
                instrument="BANKNIFTY"  # Default instrument
            )
            logger.info("Engine API: Orchestrator initialized successfully")
            
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


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global _mongo_client
    
    if _mongo_client:
        _mongo_client.close()


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
        
        result = await _orchestrator.run_cycle(context)
        
        # Convert numpy types in details to native Python types for JSON serialization
        details = result.details
        if details:
            details = convert_numpy_types(details)
        
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
        
        # Query recent signals
        signals = list(
            signals_collection.find({"instrument": instrument.upper()})
            .sort("timestamp", -1)
            .limit(limit)
        )
        
        return [
            SignalResponse(
                signal_id=str(signal.get("_id", "")),
                instrument=signal.get("instrument", instrument),
                action=signal.get("action", "HOLD"),
                confidence=signal.get("confidence", 0.0),
                reasoning=signal.get("reasoning", ""),
                timestamp=signal.get("timestamp", datetime.now(IST).isoformat())
            )
            for signal in signals
        ]
    except Exception as e:
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
    uvicorn.run(app, host=host, port=port)

