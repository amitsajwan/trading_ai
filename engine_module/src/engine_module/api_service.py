"""FastAPI REST API service for engine_module.

This provides HTTP endpoints for:
- Orchestrator execution
- Trading signals
- Agent analysis
- Health checks
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
import redis
from pymongo import MongoClient

from .api import build_orchestrator
from .contracts import Orchestrator, AnalysisResult


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
    try:
        # Check Redis connection
        redis_client = get_redis_client()
        redis_client.ping()
        
        # Check MongoDB connection
        mongo_client = get_mongo_client()
        mongo_client.admin.command('ping')
        
        # Note: Orchestrator requires LLM client and market store
        # These should be initialized separately with proper dependencies
        print("Engine API: Services initialized successfully")
        print("Note: Orchestrator requires LLM client and market store to be configured")
    except Exception as e:
        print(f"Engine API: Startup error: {e}")


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
        timestamp=datetime.utcnow().isoformat(),
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
        
        return AnalysisResponse(
            instrument=request.instrument,
            decision=result.decision,
            confidence=result.confidence,
            details=result.details,
            timestamp=datetime.utcnow().isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
                timestamp=signal.get("timestamp", datetime.utcnow().isoformat())
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
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("ENGINE_API_PORT", "8006"))
    host = os.getenv("ENGINE_API_HOST", "0.0.0.0")
    
    print(f"Starting Engine API on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

