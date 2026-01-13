# Pydantic Models for API Contracts

# Auto-generated schemas for FastAPI endpoints
# Ensures type safety and OpenAPI schema generation

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# ========================================
# Enums
# ========================================

class TradingAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class PositionSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"

class SystemStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"

class DatabaseStatus(str, Enum):
    OK = "ok"
    ERROR = "error"

class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"

# ========================================
# Core Data Models
# ========================================

class SystemHealth(BaseModel):
    """System health status response model."""
    status: SystemStatus
    timestamp: str
    database: DatabaseStatus
    cache: DatabaseStatus
    market_open: bool
    instrument: str

    class Config:
        schema_extra = {
            "example": {
                "status": "ok",
                "timestamp": "2024-01-15T10:30:00Z",
                "database": "ok",
                "cache": "ok",
                "market_open": True,
                "instrument": "BANKNIFTY"
            }
        }

class TradingSignal(BaseModel):
    """Trading signal data model."""
    signal_id: str
    instrument: str
    action: TradingAction
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: str
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reasoning: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "signal_id": "sig_123",
                "instrument": "BANKNIFTY",
                "action": "BUY",
                "confidence": 0.85,
                "timestamp": "2024-01-15T10:30:00Z",
                "entry_price": 45200.0,
                "stop_loss": 44800.0,
                "take_profit": 45800.0,
                "reasoning": "Strong bullish momentum detected"
            }
        }

class MarketData(BaseModel):
    """Market data response model."""
    instrument: str
    current_price: float
    change_24h: float
    change_percent_24h: float
    volume_24h: int
    high_24h: float
    low_24h: float
    vwap: float
    timestamp: str
    status: str

    class Config:
        schema_extra = {
            "example": {
                "instrument": "BANKNIFTY",
                "current_price": 45250.50,
                "change_24h": 125.50,
                "change_percent_24h": 0.28,
                "volume_24h": 12450000,
                "high_24h": 45350.00,
                "low_24h": 44900.00,
                "vwap": 45125.25,
                "timestamp": "2024-01-15T10:30:00Z",
                "status": "active"
            }
        }

class Position(BaseModel):
    """Trading position data model."""
    id: str
    instrument: str
    side: PositionSide
    quantity: int
    entry_price: float
    current_price: float
    pnl: float
    pnl_percent: float
    timestamp: str
    status: PositionStatus

    class Config:
        schema_extra = {
            "example": {
                "id": "pos_123",
                "instrument": "BANKNIFTY",
                "side": "BUY",
                "quantity": 25,
                "entry_price": 45200.0,
                "current_price": 45350.0,
                "pnl": 3750.0,
                "pnl_percent": 1.66,
                "timestamp": "2024-01-15T10:30:00Z",
                "status": "open"
            }
        }

class ControlStatus(BaseModel):
    """Control system status model."""
    mode: str
    database: str
    balance: float

    class Config:
        schema_extra = {
            "example": {
                "mode": "paper",
                "database": "mock",
                "balance": 100000.0
            }
        }

class TradingStats(BaseModel):
    """Trading performance statistics."""
    total_trades: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    current_streak: int
    best_streak: int
    worst_streak: int

    class Config:
        schema_extra = {
            "example": {
                "total_trades": 15,
                "win_rate": 0.667,
                "total_pnl": 2500.50,
                "avg_win": 1250.25,
                "avg_loss": -750.15,
                "largest_win": 1500.00,
                "largest_loss": -800.00,
                "current_streak": 2,
                "best_streak": 5,
                "worst_streak": -3
            }
        }

# ========================================
# Request Models
# ========================================

class ModeSwitchRequest(BaseModel):
    """Request model for switching trading modes."""
    mode: TradingMode
    confirm: Optional[bool] = False

    class Config:
        schema_extra = {
            "example": {
                "mode": "live",
                "confirm": True
            }
        }

class BalanceUpdateRequest(BaseModel):
    """Request model for updating account balance."""
    balance: float = Field(gt=0)

    class Config:
        schema_extra = {
            "example": {
                "balance": 150000.0
            }
        }

# ========================================
# Response Models
# ========================================

class ApiResponse(BaseModel):
    """Generic API response wrapper."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: str

class ModeSwitchResponse(BaseModel):
    """Response model for mode switch operations."""
    success: bool
    mode: str
    confirmation_required: Optional[bool] = None

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "mode": "live",
                "confirmation_required": False
            }
        }

class BalanceResponse(BaseModel):
    """Response model for balance operations."""
    success: bool
    balance: float

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "balance": 150000.0
            }
        }

class SignalConditionCheck(BaseModel):
    """Response model for signal condition checks."""
    conditions_met: bool
    can_execute: bool
    signal: Optional[TradingSignal] = None
    reason: Optional[str] = None
    error: Optional[str] = None

class TradingCycleResult(BaseModel):
    """Response model for trading cycle execution."""
    success: bool
    decision: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    error: Optional[str] = None

# ========================================
# Collection Response Models
# ========================================

class SignalsResponse(BaseModel):
    """Response model for signals list."""
    signals: List[TradingSignal]

class PositionsResponse(BaseModel):
    """Response model for positions list."""
    positions: List[Position]

class RecentTradesResponse(BaseModel):
    """Response model for recent trades list."""
    trades: List[Dict[str, Any]]  # Using dict for flexibility with existing data

# ========================================
# Error Models
# ========================================

class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    detail: Optional[str] = None
    timestamp: str

    class Config:
        schema_extra = {
            "example": {
                "error": "ValidationError",
                "detail": "Invalid request parameters",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }

# ========================================
# Agent Status Models (for dashboard)
# ========================================

class AgentSummary(BaseModel):
    """Agent analysis summary."""
    signal: str
    confidence: float
    reasoning: str
    metrics: Optional[Dict[str, Any]] = None

class AgentStatus(BaseModel):
    """Individual agent status."""
    status: str
    last_update: str
    signal: str
    confidence: float
    indicators: List[str]
    summary: AgentSummary

class AgentStatusResponse(BaseModel):
    """Response model for agent status endpoint."""
    agents: Dict[str, AgentStatus]

# ========================================
# Utility Functions
# ========================================

def create_error_response(error: str, detail: Optional[str] = None) -> ErrorResponse:
    """Create a standardized error response."""
    return ErrorResponse(
        error=error,
        detail=detail,
        timestamp=datetime.utcnow().isoformat()
    )

def create_success_response(data: Any = None) -> ApiResponse:
    """Create a standardized success response."""
    return ApiResponse(
        success=True,
        data=data,
        timestamp=datetime.utcnow().isoformat()
    )

# ========================================
# OpenAPI Configuration
# ========================================

# These models will be used to generate comprehensive OpenAPI schemas
# when integrated into FastAPI routers with proper response models

OPENAPI_MODELS = [
    SystemHealth,
    TradingSignal,
    MarketData,
    Position,
    ControlStatus,
    TradingStats,
    ModeSwitchRequest,
    BalanceUpdateRequest,
    ApiResponse,
    ModeSwitchResponse,
    BalanceResponse,
    SignalConditionCheck,
    TradingCycleResult,
    SignalsResponse,
    PositionsResponse,
    RecentTradesResponse,
    ErrorResponse,
    AgentStatus,
    AgentSummary,
    AgentStatusResponse
]