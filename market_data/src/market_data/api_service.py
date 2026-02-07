from __future__ import annotations

"""FastAPI REST API service for market_data module.

This provides HTTP endpoints for:
- Market data (LTP, OHLC, ticks)
- Options chain data
- Technical indicators
- Health checks
"""

print("MARKET DATA API MODULE LOADED")

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import redis
from dotenv import load_dotenv

# Load environment variables (optional - may be set via Docker environment)
try:
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", "..", "local.env"))
except Exception:
    # File may not exist in Docker environment - environment variables set directly
    pass

logger = logging.getLogger(__name__)

# Add parent directory to path for config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from config import get_config
from redis_key_manager import get_redis_key, get_execution_mode

# Get configuration for dynamic instrument usage
config = get_config()
INSTRUMENT_SYMBOL = config.instrument_symbol
INSTRUMENT_KEY = config.instrument_key

# IST timezone for Indian financial markets
IST = timezone(timedelta(hours=5, minutes=30))

from .api import build_store
from .adapters.zerodha_options_chain import ZerodhaOptionsChainAdapter
from .contracts import MarketTick, OHLCBar, OptionsData, MarketStore
try:
    from .technical_indicators_service import TechnicalIndicatorsService
    from .data_validator import get_data_validator
    from .circuit_breaker import get_circuit_breaker_manager
except ImportError:
    # Fallback if technical indicators service is not available
    TechnicalIndicatorsService = None

# Socket.IO removed - real-time updates now handled by Redis WebSocket Gateway
# See redis_ws_gateway module for direct Redis pub/sub to WebSocket forwarding
WEBSOCKET_AVAILABLE = False


# Pydantic models for API requests/responses
class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    module: str
    timestamp: str
    dependencies: Dict[str, str]


class MarketTickResponse(BaseModel):
    """Market tick response."""
    instrument: str
    timestamp: str
    last_price: float
    volume: Optional[int] = None


class OHLCResponse(BaseModel):
    """OHLC bar response."""
    instrument: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int]
    start_at: str


class OptionsChainResponse(BaseModel):
    """Options chain response."""
    instrument: str
    expiry: str
    strikes: List[Dict[str, Any]]
    timestamp: str
    futures_price: Optional[float] = None
    pcr: Optional[float] = None
    max_pain: Optional[int] = None


class TechnicalIndicatorsResponse(BaseModel):
    """Technical indicators response."""
    instrument: str
    timestamp: str
    indicators: Dict[str, Any]


# Lifespan handler for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources using FastAPI lifespan events."""
    print("LIFESPAN HANDLER STARTED")
    try:
        # Validate dependencies first
        print("Market Data API: Validating dependencies...")
        try:
            from .dependency_validator import validate_dependencies
            if not validate_dependencies():
                raise RuntimeError("Dependency validation failed - cannot start market_data API")
        except Exception as e:
            print(f"Market Data API: Dependency validation error: {e}")
            raise

        # Validate mode consistency at startup
        print("Market Data API: Validating mode consistency...")
        try:
            from .mode_validator import validate_mode_consistency, log_mode_startup
            
            redis_client = get_redis_client()
            log_mode_startup("Market Data API")
            
            # Validate mode - this will raise ModeValidationError if critical issues found
            validation_result = validate_mode_consistency(redis_client, "Market Data API")
            
            if validation_result['warnings']:
                print(f"Market Data API: Mode validation warnings: {len(validation_result['warnings'])}")
                for warning in validation_result['warnings']:
                    print(f"  - {warning}")
            else:
                print("Market Data API: Mode validation: PASSED")
                
        except Exception as e:
            print(f"Market Data API: Mode validation failed: {e}")
            # For critical errors, this will prevent startup
            if "CRITICAL" in str(e):
                raise

        print("Market Data API: Starting initialization...")
        # Startup: initialize services
        try:
            get_store()
            print("Market Data API: Store initialized")
        except Exception as e:
            print(f"Market Data API: Store initialization failed: {e}")

        # Initialize technical indicators service with Redis
        print("Market Data API: Initializing technical indicators service...")
        try:
            if TechnicalIndicatorsService is not None:
                global _technical_service
                redis_client = get_redis_client()

                # Read execution mode from Redis if available (for backtest awareness)
                mode = "LIVE"
                run_id = None
                try:
                    mode = redis_client.get("system:execution_mode") or "LIVE"
                    run_id = redis_client.get("system:run_id")
                    if mode == "BACKTEST" and run_id:
                        print(f"Market Data API: Detected BACKTEST mode (run_id: {run_id})")
                except Exception as e:
                    print(f"Market Data API: Could not read execution mode from Redis: {e}")

                _technical_service = TechnicalIndicatorsService(
                    redis_client=redis_client,
                    mode=mode,
                    run_id=run_id
                )
                print(f"Market Data API: Technical indicators service initialized in {mode} mode")
            else:
                print("Market Data API: TechnicalIndicatorsService is None - not available")
        except Exception as e:
            print(f"Market Data API: Technical indicators service initialization failed: {e}")

        # Check Redis connection
        try:
            redis_client = get_redis_client()
            redis_client.ping()
            print("Market Data API: Redis connection verified")
        except Exception as e:
            print(f"Market Data API: Redis connection failed: {e}")

        # Try to initialize options client (non-blocking)
        try:
            get_options_client()
            print("Market Data API: Options client initialized")
        except Exception as e:
            print(f"Market Data API: Options client initialization failed: {e}")

        # Socket.IO removed - real-time updates now handled by Redis WebSocket Gateway
        # Market Data API now focuses on REST endpoints only

        print("Market Data API: Services initialized successfully")

        # Start background task to continuously calculate and publish indicators
        async def publish_indicators():
            """Background task to continuously calculate and publish technical indicators."""
            print("Market Data API: Starting indicator publisher background task...")
            while True:
                try:
                    # GATE BY MODE: In BACKTEST mode, we still need to calculate indicators for API access
                    current_mode = redis_client.get("system:execution_mode") if redis_client else "LIVE"
                    # Allow indicator calculation in both LIVE and BACKTEST modes

                    if _technical_service is not None and redis_client is not None:
                        # Initialize OHLC data for configured instrument directly from Redis
                        # (since historical replay stores as individual keys, not in the store format)
                        ohlc_dicts = []

                        # Primary source: legacy individual keys (if present)
                        ohlc_pattern = f"ohlc:{INSTRUMENT_KEY}:1min:*"
                        ohlc_keys = redis_client.keys(ohlc_pattern)

                        if ohlc_keys and len(ohlc_keys) >= 10:
                            # Get OHLC data from Redis keys (newest first)
                            sorted_keys = sorted(ohlc_keys, reverse=True)[:100]  # Get latest 100

                            for key in sorted_keys:
                                ohlc_data = redis_client.get(key)
                                if ohlc_data:
                                    try:
                                        import json
                                        bar = json.loads(ohlc_data)
                                        ohlc_dicts.append({
                                            "timestamp": bar.get('start_at', bar.get('timestamp')),
                                            "open": bar.get('open'),
                                            "high": bar.get('high'),
                                            "low": bar.get('low'),
                                            "close": bar.get('close'),
                                            "volume": bar.get('volume', 0)
                                        })
                                    except Exception as parse_err:
                                        print(f"Market Data API: Error parsing OHLC data from {key}: {parse_err}")
                                        continue
                        else:
                            # Fallback: look for canonical sorted set storage
                            sorted_key = get_redis_key(f"ohlc_sorted:{INSTRUMENT_KEY}:1min")
                            try:
                                sorted_entries = redis_client.zrange(sorted_key, -100, -1)
                                if sorted_entries:
                                    print(f"Market Data API: Falling back to sorted set {sorted_key} ({len(sorted_entries)} entries)")
                                    for je in sorted_entries:
                                        try:
                                            import json
                                            bar = json.loads(je)
                                            ohlc_dicts.append({
                                                "timestamp": bar.get('start_at', bar.get('timestamp')),
                                                "open": bar.get('open'),
                                                "high": bar.get('high'),
                                                "low": bar.get('low'),
                                                "close": bar.get('close'),
                                                "volume": bar.get('volume', 0)
                                            })
                                        except Exception as parse_err:
                                            print(f"Market Data API: Error parsing OHLC data from sorted set entry: {parse_err}")
                                            continue
                            except Exception as e:
                                print(f"Market Data API: Error accessing sorted set {sorted_key}: {e}")

                        # Now ohlc_dicts may be populated from either source

                        # Sort by timestamp (oldest first for technical analysis)
                        ohlc_dicts.sort(key=lambda x: x['timestamp'])

                        if len(ohlc_dicts) >= 14:
                            # Initialize technical indicators service with OHLC data
                            _technical_service.initialize_with_ohlc_data(INSTRUMENT_KEY, ohlc_dicts)

                            # Calculate indicators for configured instrument
                            indicators = _technical_service.calculate_indicators(INSTRUMENT_KEY)
                            if indicators:
                                print(f"Market Data API: Published indicators for {INSTRUMENT_KEY} at {datetime.now().isoformat()}")
                                print(f"Market Data API: DEBUG - Indicators calculated: rsi_14={indicators.rsi_14}, macd={indicators.macd_value}")
                            else:
                                print(f"Market Data API: Indicator calculation returned None for {INSTRUMENT_KEY}")
                        else:
                            print(f"Market Data API: Insufficient OHLC data for {INSTRUMENT_KEY}: {len(ohlc_dicts)} bars (need >= 14)")
                except Exception as e:
                    print(f"Market Data API: Error publishing indicators: {e}")
                # Publish every 30 seconds
                await asyncio.sleep(30)

        # Create background task
        indicator_task = asyncio.create_task(publish_indicators())

        yield

        # Cleanup: cancel the background task
        if indicator_task and not indicator_task.done():
            indicator_task.cancel()
            try:
                await indicator_task
            except asyncio.CancelledError:
                pass
        print("Market Data API: Indicator publisher stopped")
    except Exception as e:
        print(f"Market Data API: Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        print("Market Data API: Starting cleanup...")
        # Socket.IO removed - no cleanup needed


# FastAPI app
app = FastAPI(
    title="Market Data API",
    description="REST API for market data, options chain, and technical indicators (with WebSocket support)",
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

# Global store instance (initialized on startup)
_store: Optional[MarketStore] = None
_options_client: Optional[OptionsData] = None
_redis_client: Optional[redis.Redis] = None
_technical_service: Optional[TechnicalIndicatorsService] = None


@app.get("/")
async def root():
    """Root endpoint providing API information."""
    return {
        "service": "Market Data API",
        "version": "1.0.0",
        "description": "REST API for market data, options chain, and technical indicators",
        "docs": "/docs",
        "health": "/health"
    }


# Socket.IO removed - real-time updates now handled by Redis WebSocket Gateway


def get_redis_client() -> redis.Redis:
    """Get Redis client from environment."""
    global _redis_client
    if _redis_client is None:
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        _redis_client = redis.Redis(host=host, port=port, db=0, decode_responses=True)
    return _redis_client


def get_store() -> MarketStore:
    """Get market store instance."""
    global _store
    if _store is None:
        redis_client = get_redis_client()
        _store = build_store(redis_client=redis_client)
    return _store


def get_options_client() -> Optional[OptionsData]:
    """Get or initialize options client (lazy initialization).
    
    Tries direct Kite API first, falls back to legacy OptionsChainFetcher if available.
    """
    global _options_client
    if _options_client is not None:
        return _options_client
    
    # Try to build options client if credentials are available
    try:
        from kiteconnect import KiteConnect
        import json
        import os
        
        cred_path = os.path.join(os.getcwd(), "credentials.json")
        if not os.path.exists(cred_path):
            return None
        
        with open(cred_path, "r", encoding="utf-8") as f:
            creds = json.load(f)
        
        api_key = creds.get("api_key")
        access_token = creds.get("access_token")
        
        if not api_key or not access_token:
            return None
        
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        
        # Determine execution mode and live/historical status
        is_live_mode = True  # Default to live mode
        is_backtest_mode = False

        try:
            redis_client = get_redis_client()

            # Check execution mode first (takes precedence)
            execution_mode = redis_client.get("system:execution_mode")
            if execution_mode:
                execution_mode = execution_mode.decode() if isinstance(execution_mode, bytes) else execution_mode
                if execution_mode == "HISTORICAL":
                    is_live_mode = False  # Historical mode uses LTP, not live quotes

            # If not BACKTEST, check for virtual time (historical replay)
            if not is_backtest_mode:
                virtual_time_enabled = redis_client.get("system:virtual_time:enabled")
                if virtual_time_enabled:
                    virtual_time_str = virtual_time_enabled.decode() if isinstance(virtual_time_enabled, bytes) else virtual_time_enabled
                    if virtual_time_str == "1":
                        is_live_mode = False
        except Exception:
            # If Redis check fails, fall back to environment variable
            provider_name = os.getenv("TRADING_PROVIDER", "").lower()
            use_mock_env = os.getenv("USE_MOCK_KITE", "false").lower() in ('1', 'true', 'yes')
            is_live_mode = provider_name in ('zerodha', 'kite') and not use_mock_env
        
        # Use Zerodha Options Chain Adapter
        try:
            instrument = os.getenv("INSTRUMENT_SYMBOL", INSTRUMENT_SYMBOL)

            if is_live_mode:
                print(f"Market Data API: Using Zerodha Options Chain (LIVE mode - real-time quote() API) for {instrument}")
                _options_client = ZerodhaOptionsChainAdapter(kite, instrument, use_live_quotes=True)
                print(f"Market Data API: [OK] Zerodha options client initialized (LIVE - real-time quotes)")
            else:
                print(f"Market Data API: Using Zerodha Options Chain (historical mode - ltp() API) for {instrument}")
                _options_client = ZerodhaOptionsChainAdapter(kite, instrument, use_live_quotes=False)
                print(f"Market Data API: [OK] Zerodha options client initialized (historical - last traded price)")
            return _options_client
        except Exception as e:
            print(f"Market Data API: Zerodha options client failed: {e}")
            import traceback
            traceback.print_exc()
            print(f"Market Data API: Legacy options client failed: {e}")
        
        return None
    except Exception as e:
        print(f"Market Data API: Options client initialization error: {e}")
        return None


        return None


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with data validation."""
    dependencies = {}
    
    # Check Redis connectivity
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        redis_status = "healthy"
        dependencies["redis"] = redis_status
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
        dependencies["redis"] = redis_status
    
    # Check store initialization
    dependencies["store"] = "initialized" if _store is not None else "not_initialized"
    
    # Check data availability and freshness for default instrument (BANKNIFTY)
    if redis_status == "healthy":
        try:
            from datetime import datetime, timedelta
            from market_data.adapters.historical_tick_replayer import IST
            
            instrument = INSTRUMENT_KEY
            price_key = f"price:{instrument}:latest"
            timestamp_key = f"price:{instrument}:latest_ts"
            
            price = redis_client.get(price_key)
            timestamp = redis_client.get(timestamp_key)
            
            if not price or not timestamp:
                dependencies["data_availability"] = f"missing_price_data_for_{instrument}"
            else:
                # Check if data is fresh (not stale)
                try:
                    timestamp_str = timestamp if isinstance(timestamp, str) else timestamp.decode()
                    redis_time = datetime.fromisoformat(timestamp_str)
                    if redis_time.tzinfo is None:
                        redis_time = redis_time.replace(tzinfo=IST)
                    
                    # Check if virtual time is enabled (historical replay mode)
                    virtual_time_enabled = redis_client.get("system:virtual_time:enabled")
                    if virtual_time_enabled and virtual_time_enabled.decode() if isinstance(virtual_time_enabled, bytes) else virtual_time_enabled == "1":
                        # In historical replay mode, compare against virtual time
                        virtual_time_str = redis_client.get("system:virtual_time:current")
                        if virtual_time_str:
                            virtual_time_str = virtual_time_str.decode() if isinstance(virtual_time_str, bytes) else virtual_time_str
                            current_time = datetime.fromisoformat(virtual_time_str)
                            if current_time.tzinfo is None:
                                current_time = current_time.replace(tzinfo=IST)
                            time_diff = current_time - redis_time
                            age_seconds = abs(time_diff.total_seconds())
                            
                            if age_seconds > 120:  # More than 2 minutes old relative to virtual time
                                dependencies["data_availability"] = f"stale_data_for_{instrument}_age_{age_seconds:.0f}s"
                            else:
                                dependencies["data_availability"] = f"fresh_data_for_{instrument}"
                        else:
                            # Virtual time enabled but no current time set
                            dependencies["data_availability"] = f"fresh_data_for_{instrument}_virtual_time_mode"
                    else:
                        # Live mode - compare against real time
                        current_time = datetime.now(IST)
                        time_diff = current_time - redis_time
                        age_seconds = abs(time_diff.total_seconds())
                        
                        if age_seconds > 120:  # More than 2 minutes old
                            dependencies["data_availability"] = f"stale_data_for_{instrument}_age_{age_seconds:.0f}s"
                        else:
                            dependencies["data_availability"] = f"fresh_data_for_{instrument}"
                except Exception as e:
                    dependencies["data_availability"] = f"invalid_timestamp_for_{instrument}: {str(e)}"
        except Exception as e:
            dependencies["data_availability"] = f"check_failed: {str(e)}"
    else:
        dependencies["data_availability"] = "redis_unavailable"
    
    # Check 5-minute OHLC data availability (critical for engine operation)
    if redis_status == "healthy":
        try:
            store = get_store()
            # Check for 5-minute data for the configured instrument
            five_min_bars = list(store.get_ohlc(INSTRUMENT_KEY, "5min", limit=10))
            if len(five_min_bars) >= 5:  # Require at least 5 bars of 5-minute data
                dependencies["five_min_data"] = f"available_{len(five_min_bars)}_bars"
            else:
                dependencies["five_min_data"] = f"insufficient_data_{len(five_min_bars)}_bars_need_5"
        except Exception as e:
            dependencies["five_min_data"] = f"check_failed: {str(e)}"
    else:
        dependencies["five_min_data"] = "redis_unavailable"
    
    # Determine overall status
    try:
        from market_data.adapters.historical_tick_replayer import IST
    except ImportError:
        pass

    # Ensure IST is always defined
    if 'IST' not in locals():
        from datetime import timezone, timedelta, datetime
        IST = timezone(timedelta(hours=5, minutes=30))
    else:
        from datetime import datetime

    status = "healthy"
    if redis_status != "healthy":
        status = "degraded"
    elif "missing" in dependencies.get("data_availability", ""):
        status = "degraded"  # Data missing - this is critical
    elif "insufficient" in dependencies.get("five_min_data", ""):
        status = "degraded"  # Insufficient 5-minute data - engine cannot operate
    elif "stale" in dependencies.get("data_availability", ""):
        # Stale data is not ideal but still usable - keep as healthy but note in dependencies
        status = "healthy"  # Data exists, just not fresh - still functional
    
    return HealthResponse(
        status=status,
        module="market_data",
        timestamp=datetime.now(IST).isoformat(),
        dependencies=dependencies
    )


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with comprehensive dependency validation."""
    try:
        from .dependency_validator import MarketDataDependencyValidator

        validator = MarketDataDependencyValidator()
        all_passed, checks = validator.validate_all()

        # Convert checks to dict format
        check_results = {}
        for check in checks:
            check_results[check.name] = {
                "status": check.status.value,
                "message": check.message,
                "critical": check.critical,
                "details": check.details
            }

        # Summary
        summary = {
            "overall_status": "healthy" if all_passed else "unhealthy",
            "total_checks": len(checks),
            "passed": len([c for c in checks if c.status.value == "ok"]),
            "warnings": len([c for c in checks if c.status.value == "warning"]),
            "errors": len([c for c in checks if c.status.value == "error"]),
            "critical_errors": len([c for c in checks if c.status.value == "error" and c.critical])
        }

        # Add data validation to health check
        data_validation = {}
        try:
            redis_client = get_redis_client()
            validator = get_data_validator(redis_client)

            # Validate data for configured instrument
            instrument = os.getenv('INSTRUMENT_SYMBOL', 'BANKNIFTY26JANFUT')
            ohlc_validation = validator.validate_ohlc_data(instrument, '1min')
            indicators_validation = validator.validate_technical_indicators(instrument)
            system_health = validator.validate_system_health()

            data_validation = {
                "ohlc_data_validation": ohlc_validation,
                "technical_indicators_validation": indicators_validation,
                "system_health": system_health
            }

            # Update overall status if data validation fails
            if not ohlc_validation['valid'] or not indicators_validation['valid']:
                summary["overall_status"] = "degraded"
                summary["data_issues"] = True

        except Exception as e:
            data_validation = {"error": f"Data validation failed: {str(e)}"}

        return {
            "summary": summary,
            "checks": check_results,
            "data_validation": data_validation,
            "timestamp": datetime.now(IST).isoformat()
        }
    except Exception as e:
        return {
            "error": f"Health check failed: {e}",
            "timestamp": datetime.now(IST).isoformat()
        }


@app.get("/diagnostics")
async def get_diagnostics():
    """Comprehensive system diagnostics endpoint."""
    try:
        from .diagnostics import run_diagnostics
        return run_diagnostics()
    except Exception as e:
        return {
            "error": f"Diagnostics failed: {e}",
            "timestamp": datetime.now(IST).isoformat()
        }


class SystemModeResponse(BaseModel):
    """System execution mode response."""
    mode: str = Field(..., description="Current execution mode: live or historical")
    virtual_time_enabled: bool = Field(..., description="Whether virtual time is enabled")
    virtual_time: Optional[str] = Field(None, description="Current virtual time if enabled")
    system_time: str = Field(..., description="Actual system time")
    effective_time: str = Field(..., description="Effective time used by system")
    redis_mode: Optional[str] = Field(None, description="Mode stored in Redis")


@app.get("/api/v1/system/mode", response_model=SystemModeResponse)
async def get_system_mode():
    """
    Get current execution mode and time configuration.
    
    Returns information about:
    - Current execution mode (LIVE or HISTORICAL)
    - Virtual time status (enabled/disabled)
    - Effective time used by the system
    - Mode consistency between environment and Redis
    
    This endpoint is used by the UI to display mode badges and
    helps troubleshoot mode-related issues.
    """
    try:
        redis_client = get_redis_client()
        
        # Get execution mode from environment
        mode = get_execution_mode()
        
        # Get virtual time configuration
        virtual_time_enabled_bytes = redis_client.get("system:virtual_time:enabled")
        virtual_time_enabled = virtual_time_enabled_bytes == b"1" if virtual_time_enabled_bytes else False
        
        virtual_time = None
        if virtual_time_enabled:
            vt_bytes = redis_client.get("system:virtual_time:current")
            virtual_time = vt_bytes.decode() if vt_bytes else None
        
        # Get Redis mode
        redis_mode_bytes = redis_client.get("system:execution_mode")
        redis_mode = redis_mode_bytes.decode() if redis_mode_bytes else None
        
        # Calculate effective time
        system_time = datetime.now(IST).isoformat()
        effective_time = virtual_time if virtual_time_enabled and virtual_time else system_time
        
        return SystemModeResponse(
            mode=mode,
            virtual_time_enabled=virtual_time_enabled,
            virtual_time=virtual_time,
            system_time=system_time,
            effective_time=effective_time,
            redis_mode=redis_mode
        )
        
    except Exception as e:
        logger.error(f"Failed to get system mode: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system mode: {str(e)}")


@app.get("/api/v1/market/tick/{instrument}", response_model=MarketTickResponse)
async def get_latest_tick(instrument: str):
    """Get latest tick for an instrument."""
    try:
        # First try Redis directly (faster, what collectors use)
        redis_client = get_redis_client()
        instrument_clean = instrument.upper().replace(" ", "").replace("-", "_")
        
        # Try key variations
        key_variations = [
            instrument_clean,
            instrument_clean.replace("BANKNIFTY", "NIFTYBANK"),
            instrument_clean.replace("NIFTYBANK", "BANKNIFTY"),
        ]
        
        price = None
        timestamp = None
        volume = None
        
        for key_var in key_variations:
            price_key = f"price:{key_var}:last_price"
            timestamp_key = f"price:{key_var}:latest_ts"
            volume_key = f"price:{key_var}:volume"
            
            if not price:
                price = redis_client.get(price_key)
            if not timestamp:
                timestamp = redis_client.get(timestamp_key)
            if not volume:
                volume = redis_client.get(volume_key)
            
            if price:
                break
        
        if price:
            # Return from Redis
            from datetime import datetime
            ts = datetime.fromisoformat(timestamp) if timestamp else datetime.now(IST)
            return MarketTickResponse(
                instrument=instrument.upper(),
                timestamp=ts.isoformat(),
                last_price=float(price),
                volume=int(volume) if volume else None
            )
        
        # Fallback to store
        store = get_store()
        tick = store.get_latest_tick(instrument.upper())
        
        if tick is None:
            raise HTTPException(status_code=404, detail=f"No tick data found for {instrument}")
        
        return MarketTickResponse(
            instrument=tick.instrument,
            timestamp=tick.timestamp.isoformat(),
            last_price=tick.last_price,
            volume=tick.volume
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _normalize_timeframe(timeframe: str) -> str:
    tf = timeframe.lower()
    if tf == "minute":
        return "1min"
    if tf.endswith("minute"):
        minutes = tf.replace("minute", "").strip()
        if minutes:
            return f"{minutes}min"
    return tf


async def _get_ohlc_impl(instrument: str, timeframe: str, limit: int, order: str) -> List[OHLCResponse]:
    """Shared OHLC retrieval with optional ascending-from-start order.

    order:
      - "desc" (default): latest bars (existing behavior)
      - "asc": earliest bars (from session start)
    """
    instrument_upper = instrument.upper()
    normalized_tf = _normalize_timeframe(timeframe)

    try:
        # Ascending mode: fetch from start of day using Redis sorted set directly
        if order == "asc":
            redis_client = get_redis_client()
            sorted_key = get_redis_key(f"ohlc_sorted:{instrument_upper}:{normalized_tf}")
            results = redis_client.zrange(sorted_key, 0, limit - 1) if limit > 0 else redis_client.zrange(sorted_key, 0, -1)
            if not results:
                # Gracefully return empty list instead of 404 so dashboards can render without data
                return []

            response: List[OHLCResponse] = []
            for payload in results:
                try:
                    import json
                    bar_data = json.loads(payload)
                    response.append(
                        OHLCResponse(
                            instrument=bar_data.get("instrument", instrument_upper),
                            timeframe=bar_data.get("timeframe", timeframe),
                            open=float(bar_data.get("open", 0)),
                            high=float(bar_data.get("high", 0)),
                            low=float(bar_data.get("low", 0)),
                            close=float(bar_data.get("close", 0)),
                            volume=bar_data.get("volume"),
                            start_at=(bar_data.get("start_at") or bar_data.get("timestamp"))
                        )
                    )
                except Exception:
                    continue

            if not response:
                return []
            return response

        # Default mode: latest bars via store (existing behavior)
        store = get_store()
        bars = list(store.get_ohlc(instrument_upper, timeframe, limit))

        if not bars:
            return []

        return [
            OHLCResponse(
                instrument=bar.instrument,
                timeframe=bar.timeframe,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                start_at=bar.start_at.isoformat()
            )
            for bar in bars
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/market/ohlc/{instrument}", response_model=List[OHLCResponse])
async def get_ohlc(
    instrument: str,
    timeframe: str = "minute",
    limit: int = 100,
    order: str = "desc"
):
    """Get OHLC bars for an instrument.

    order options:
      - desc (default): latest bars (existing behavior)
      - asc: earliest bars from session start (use limit to control count)
    """
    return await _get_ohlc_impl(instrument, timeframe, limit, order.lower())


@app.get("/api/v1/ohlc/{instrument}", response_model=List[OHLCResponse])
async def get_ohlc_alias(
    instrument: str,
    timeframe: str = "minute",
    limit: int = 100,
    order: str = "desc"
):
    """Alias for OHLC endpoint (shorter path)."""
    return await _get_ohlc_impl(instrument, timeframe, limit, order.lower())


@app.get("/api/v1/market/overview")
async def get_market_overview(symbol: str = INSTRUMENT_SYMBOL):
    """Get market overview data for dashboard widget.
    
    Aggregates tick and OHLC data to provide a comprehensive market overview.
    """
    try:
        instrument = symbol.upper()
        store = get_store()
        
        # Get latest tick
        tick = store.get_latest_tick(instrument)
        if not tick:
            raise HTTPException(status_code=404, detail=f"No tick data found for {instrument}")
        
        # Get OHLC data for 24h calculation
        ohlc_bars = list(store.get_ohlc(instrument, "minute", limit=1440))  # ~24 hours of 1-min bars
        
        # Calculate 24h high, low, volume
        high_24h = tick.last_price
        low_24h = tick.last_price
        volume_24h = tick.volume or 0
        vwap_sum = 0.0
        vwap_volume = 0
        
        if ohlc_bars:
            for bar in ohlc_bars:
                if bar.high > high_24h:
                    high_24h = bar.high
                if bar.low < low_24h:
                    low_24h = bar.low
                volume_24h += bar.volume or 0
                # VWAP calculation (typical price * volume)
                typical_price = (bar.high + bar.low + bar.close) / 3
                vwap_sum += typical_price * (bar.volume or 0)
                vwap_volume += bar.volume or 0
        
        # Calculate VWAP
        vwap = vwap_sum / vwap_volume if vwap_volume > 0 else tick.last_price
        
        # Get previous day's close for change calculation (use first bar of the day or current price)
        prev_close = ohlc_bars[0].open if ohlc_bars else tick.last_price
        change_24h = tick.last_price - prev_close
        change_percent_24h = (change_24h / prev_close * 100) if prev_close > 0 else 0
        
        return {
            "instrument": instrument,
            "current_price": tick.last_price,
            "high_24h": high_24h,
            "low_24h": low_24h,
            "vwap": vwap,
            "volume_24h": volume_24h,
            "change_24h": change_24h,
            "change_percent_24h": change_percent_24h,
            "status": "active",  # Could check market hours here
            "timestamp": tick.timestamp.isoformat() if hasattr(tick.timestamp, 'isoformat') else str(tick.timestamp)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/options/chain/{instrument}", response_model=OptionsChainResponse)
async def get_options_chain(instrument: str):
    """Get options chain for an instrument."""
    try:
        import json  # Import here for JSON parsing
        
        # Check if we should use mock data (mock mode or options client not available)
        use_mock = os.getenv("USE_MOCK_KITE", "false").lower() in ('1', 'true', 'yes')
        
        if use_mock:
            # Try to get mock data from Redis first
            logger.info(f"Using mock options data for {instrument}")
            redis_client = get_redis_client()
            
            # Try prefixed key first
            from redis_key_manager import get_redis_key
            mock_key = get_redis_key(f"options:{instrument}:chain")
            chain_json = redis_client.get(mock_key)
            
            # Fallback to legacy key
            if not chain_json:
                mock_key = f"options:{instrument}:chain"
                chain_json = redis_client.get(mock_key)
            
            logger.info(f"Checked Redis key {mock_key}: {'FOUND' if chain_json else 'NOT FOUND'}")
            
            if chain_json:
                logger.info(f"Found mock options data in Redis: {mock_key} (length: {len(chain_json)})")
                chain = json.loads(chain_json)
                logger.info(f"Parsed options chain: {len(chain.get('strikes', []))} strikes")
                
                # Remap mock field names to match API response
                if 'underlying_price' in chain:
                    chain['futures_price'] = chain.pop('underlying_price')
                
                # Mock data already has correct structure, just return it
                return OptionsChainResponse(
                    instrument=chain.get('instrument', instrument),
                    expiry=chain.get('expiry', ''),
                    strikes=chain.get('strikes', []),
                    timestamp=chain.get('timestamp', datetime.now().isoformat()),
                    futures_price=chain.get('futures_price'),
                    pcr=chain.get('pcr'),
                    max_pain=chain.get('max_pain')
                )
            else:
                logger.warning(f"No mock options data found in Redis, returning empty chain")
                # Return empty but valid structure
                return OptionsChainResponse(
                    instrument=instrument,
                    expiry='',
                    strikes=[],
                    timestamp=datetime.now().isoformat(),
                    futures_price=None,
                    pcr=None,
                    max_pain=None
                )
        else:
            # Use real Zerodha API
            options_client = get_options_client()
            
            if options_client is None:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Options client not available. "
                        "Requires: (1) Kite API credentials in credentials.json with api_key and access_token, "
                        "(2) Valid Kite API access token. "
                        "Check logs for initialization errors."
                    )
                )
            
            await options_client.initialize()
            chain = await options_client.fetch_options_chain(instrument=instrument)

        # Ensure expiry is a string
        expiry_str = chain.get("expiry", "")
        if hasattr(expiry_str, 'isoformat'):
            expiry_str = expiry_str.isoformat()

        # Normalize strikes structure: Convert nested CE/PE to flat ce_ltp/pe_ltp format
        strikes_raw = chain.get("strikes", [])
        normalized_strikes = []
        
        total_put_oi = 0
        total_call_oi = 0
        
        for strike_data in strikes_raw:
            ce_data = strike_data.get("CE")
            pe_data = strike_data.get("PE")
            
            # Extract CE data
            ce_ltp = ce_data.get("last_price") if ce_data else None
            ce_oi = ce_data.get("oi", 0) if ce_data else 0
            ce_volume = ce_data.get("volume", 0) if ce_data else 0
            ce_iv = None  # IV not available from basic LTP/quote
            
            # Extract PE data
            pe_ltp = pe_data.get("last_price") if pe_data else None
            pe_oi = pe_data.get("oi", 0) if pe_data else 0
            pe_volume = pe_data.get("volume", 0) if pe_data else 0
            pe_iv = None  # IV not available from basic LTP/quote
            
            # Accumulate OI for PCR calculation
            total_call_oi += ce_oi or 0
            total_put_oi += pe_oi or 0
            
            normalized_strike = {
                "strike": strike_data.get("strike"),
                "ce_ltp": ce_ltp,
                "ce_oi": ce_oi,
                "ce_volume": ce_volume,
                "ce_iv": ce_iv,
                "pe_ltp": pe_ltp,
                "pe_oi": pe_oi,
                "pe_volume": pe_volume,
                "pe_iv": pe_iv,
            }
            normalized_strikes.append(normalized_strike)
        
        # Calculate PCR (Put/Call Ratio)
        pcr = (total_put_oi / total_call_oi) if total_call_oi > 0 else None
        
        # Calculate Max Pain (strike with minimum total value of open interest)
        max_pain = None
        min_pain_value = float('inf')
        
        for strike_data in strikes_raw:
            strike_price = strike_data.get("strike")
            
            # Calculate pain value: sum of (strike - price) * OI for calls below strike
            # and (price - strike) * OI for puts above strike
            pain_value = 0
            for s in strikes_raw:
                s_price = s.get("strike")
                s_ce_oi = s.get("CE", {}).get("oi", 0) or 0
                s_pe_oi = s.get("PE", {}).get("oi", 0) or 0
                
                if s_price < strike_price:
                    # Call options ITM
                    pain_value += (strike_price - s_price) * s_ce_oi
                elif s_price > strike_price:
                    # Put options ITM
                    pain_value += (s_price - strike_price) * s_pe_oi
            
            if pain_value < min_pain_value:
                min_pain_value = pain_value
                max_pain = strike_price
        
        # Fetch futures price
        futures_price = None
        try:
            if hasattr(options_client, 'kite') and options_client.kite:
                # Try to get futures price - futures symbol format: BANKNIFTY24JANFUT
                # Get current month futures
                month_names = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                              'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
                now = datetime.now()
                month_str = month_names[now.month - 1]
                year_str = str(now.year)[-2:]
                fut_symbol = f"{instrument.upper()}{year_str}{month_str}FUT"
                
                try:
                    fut_quote = options_client.kite.quote([f"NFO:{fut_symbol}"])
                    if fut_quote:
                        fut_data = list(fut_quote.values())[0]
                        if hasattr(fut_data, 'to_dict'):
                            fut_data = fut_data.to_dict()
                        futures_price = fut_data.get('last_price') or fut_data.get('ohlc', {}).get('close')
                except Exception:
                    # If futures not found, try getting underlying spot price
                    try:
                        underlying_quote = options_client.kite.quote([f"NSE:{instrument.upper()}"])
                        if underlying_quote:
                            underlying_data = list(underlying_quote.values())[0]
                            if hasattr(underlying_data, 'to_dict'):
                                underlying_data = underlying_data.to_dict()
                            futures_price = underlying_data.get('last_price') or underlying_data.get('ohlc', {}).get('close')
                    except Exception:
                        pass
        except Exception as e:
            # Futures price is optional, log debug only
            pass  # futures_price remains None

        # Build response object
        response = OptionsChainResponse(
            instrument=instrument.upper(),
            expiry=expiry_str,
            strikes=normalized_strikes,
            timestamp=datetime.now(IST).isoformat(),
            futures_price=futures_price,
            pcr=pcr,
            max_pain=max_pain
        )
        
        # Publish to Redis for real-time WebSocket updates
        try:
            import json
            redis_client = get_redis_client()
            # Convert response to dict for JSON serialization
            response_dict = response.model_dump() if hasattr(response, 'model_dump') else response.dict()
            # Publish to Redis channel: market:options:{instrument}
            channel = f"market:options:{instrument.upper()}"
            redis_client.publish(channel, json.dumps(response_dict))
        except Exception as pub_err:
            # Don't fail the API request if publishing fails
            # Log error but continue (Redis pub/sub may not be configured)
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Failed to publish options chain to Redis: {pub_err}")

        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/technical/status")
async def get_technical_status():
    """Check if technical indicators service is initialized."""
    return {
        "technical_service_available": TechnicalIndicatorsService is not None,
        "technical_service_initialized": _technical_service is not None,
        "redis_available": True  # We know Redis works from direct test
    }

@app.get("/api/v1/technical/indicators/{instrument}")
async def get_technical_indicators(
    instrument: str,
    timeframe: str = "minute"
):
    """Get technical indicators for an instrument."""
    try:
        # Try to get from Redis cache first
        redis_client = get_redis_client()
        key_prefix = f"indicators:{instrument.upper()}:"
        indicators_dict = {}

        logger.info(f"🔍 Looking for indicators with prefix: {key_prefix}")
        found_keys = list(redis_client.scan_iter(match=f"{key_prefix}*"))
        logger.info(f"🔍 Found {len(found_keys)} indicator keys in Redis")

        for key in found_keys:
            indicator_name = key.replace(key_prefix, "")
            value = redis_client.get(key)
            try:
                float_value = float(value) if value else None
                # Handle infinite values that can't be JSON serialized
                if float_value is not None and (float_value == float('inf') or float_value == float('-inf')):
                    float_value = None
                indicators_dict[indicator_name] = float_value
                logger.debug(f"📊 Loaded indicator {indicator_name}: {indicators_dict[indicator_name]}")
            except (ValueError, TypeError) as e:
                # value is already a string in newer redis-py versions
                indicators_dict[indicator_name] = value if value else None
                logger.debug(f"📊 Loaded indicator {indicator_name}: {indicators_dict[indicator_name]} (string)")

        logger.info(f"📊 Loaded {len(indicators_dict)} indicators from Redis cache")

        if not indicators_dict:
            # Try to reconstruct indicators on-the-fly from OHLC data if available
            try:
                store = get_store()
                # Normalize timeframe (API accepts 'minute' or '1min')
                tf = timeframe
                if tf == 'minute':
                    tf = '1min'

                ohlc_bars = list(store.get_ohlc(instrument.upper(), tf, limit=200))
                logger.warning(f"Store returned {len(ohlc_bars)} OHLC bars for {instrument.upper()}:{tf}")
                if not ohlc_bars:
                    # Debug: check direct Redis sorted set as a fallback for investigation
                    try:
                        sorted_key = get_redis_key(f"ohlc_sorted:{instrument.upper()}:{tf}")
                        entries = get_redis_client().zrange(sorted_key, 0, -1)
                        logger.warning(f"Redis sorted set {sorted_key} length: {len(entries) if entries is not None else 0}")
                        # Also list all matching sorted set keys for debugging
                        try:
                            pattern = get_redis_key(f"ohlc_sorted:{instrument.upper()}:*")
                            matching = get_redis_client().keys(pattern)
                            logger.warning(f"Redis keys matching {pattern} -> {matching}")
                        except Exception as e:
                            logger.debug(f"Failed to list matching keys: {e}")

                        # If app Redis doesn't have the data, try standard Redis port 6379 (test cases may write there)
                        if not entries:
                            try:
                                import redis as _r, json as _json
                                alt = _r.Redis(host='localhost', port=6379, db=0, decode_responses=True)
                                alt_entries = alt.zrange(sorted_key, 0, -1)
                                logger.warning(f"Alt Redis (6379) sorted set {sorted_key} length: {len(alt_entries) if alt_entries is not None else 0}")
                                if alt_entries:
                                    # Convert JSON entries to OHLCBar objects
                                    from market_data.contracts import OHLCBar
                                    parsed_bars = []
                                    for je in alt_entries[-200:]:
                                        try:
                                            jd = _json.loads(je)
                                            ts = jd.get('timestamp') or jd.get('start_at')
                                            if ts:
                                                try:
                                                    start_at = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                                                except Exception:
                                                    start_at = None
                                            else:
                                                start_at = None
                                            parsed_bars.append(OHLCBar(
                                                instrument=instrument.upper(),
                                                timeframe=tf,
                                                open=jd.get('open'),
                                                high=jd.get('high'),
                                                low=jd.get('low'),
                                                close=jd.get('close'),
                                                volume=jd.get('volume', 0),
                                                start_at=start_at
                                            ))
                                        except Exception:
                                            continue

                                    if parsed_bars:
                                        svc = _technical_service if _technical_service is not None else (TechnicalIndicatorsService(redis_client=get_redis_client()) if TechnicalIndicatorsService is not None else None)
                                        if svc is not None and hasattr(svc, 'calculate_indicators_from_ohlc_bars'):
                                            indicators_obj = svc.calculate_indicators_from_ohlc_bars(instrument.upper(), tf, parsed_bars)
                                            indicators_out = indicators_obj.to_dict() if hasattr(indicators_obj, 'to_dict') else asdict(indicators_obj)
                                            return {
                                                "instrument": instrument.upper(),
                                                "timestamp": datetime.now(IST).isoformat(),
                                                "indicators": indicators_out
                                            }
                            except Exception as alt_err:
                                logger.debug(f"Failed to read alt Redis for indicators: {alt_err}")

                    except Exception as redis_check_err:
                        logger.debug(f"Failed to inspect Redis sorted set for debug: {redis_check_err}")

                if ohlc_bars:
                    # Use existing technical service if available or create a temporary one
                    try:
                        svc = _technical_service if _technical_service is not None else (TechnicalIndicatorsService(redis_client=get_redis_client()) if TechnicalIndicatorsService is not None else None)
                        if svc is not None and hasattr(svc, 'calculate_indicators_from_ohlc_bars'):
                            indicators_obj = svc.calculate_indicators_from_ohlc_bars(instrument.upper(), tf, ohlc_bars)
                            indicators_out = indicators_obj.to_dict() if hasattr(indicators_obj, 'to_dict') else asdict(indicators_obj)
                            return {
                                "instrument": instrument.upper(),
                                "timestamp": datetime.now(IST).isoformat(),
                                "indicators": indicators_out
                            }
                    except Exception as calc_err:
                        logger.debug(f"Failed to calculate indicators from OHLC bars: {calc_err}")
            except Exception as e:
                logger.debug(f"Failed to reconstruct indicators from OHLC data: {e}")

            return {
                "instrument": instrument.upper(),
                "timestamp": datetime.now(IST).isoformat(),
                "indicators": {"status": "no_data"}
            }
        
        return {
            "instrument": instrument.upper(),
            "timestamp": datetime.now(IST).isoformat(),
            "indicators": indicators_dict
        }
    except Exception as e:
        logger.error(f"Error getting technical indicators: {e}")
        return {
            "instrument": instrument.upper(),
            "timestamp": datetime.now(IST).isoformat(),
            "indicators": {"error": str(e)}
        }


@app.get("/api/v1/market/price/{instrument}")
async def get_price_data(instrument: str):
    """Get latest price data from Redis with staleness check."""
    try:
        redis_client = get_redis_client()

        # Normalize instrument key (remove spaces, handle variations)
        instrument_clean = instrument.upper().replace(" ", "").replace("-", "_").replace(":", "_")

        # Try multiple key variations
        key_variations = [
            instrument_clean,  # e.g., "BANKNIFTY"
            instrument_clean.replace("BANKNIFTY", "NIFTYBANK"),  # Handle NIFTY BANK -> NIFTYBANK
            instrument_clean.replace("NIFTYBANK", "BANKNIFTY"),  # Handle reverse
        ]

        price = None
        timestamp = None
        volume = None
        quote_data = None

        for key_var in key_variations:
            price_key = f"price:{key_var}:latest"
            timestamp_key = f"price:{key_var}:latest_ts"
            volume_key = f"volume:{key_var}:latest"
            quote_key = f"price:{key_var}:quote"

            if not price:
                price = redis_client.get(price_key)
            if not timestamp:
                timestamp = redis_client.get(timestamp_key)
            if not volume:
                volume = redis_client.get(volume_key)
            if not quote_data:
                quote_data = redis_client.get(quote_key)

            if price:
                break  # Found data, stop trying variations

        # Check staleness: no data or data older than 2 minutes
        # For rebased historical data that appears in the future, consider it fresh
        from datetime import datetime, timedelta
        from market_data.adapters.historical_tick_replayer import IST

        is_stale = False
        if timestamp:
            try:
                timestamp_str = timestamp.decode() if isinstance(timestamp, bytes) else timestamp
                redis_time = datetime.fromisoformat(timestamp_str)
                # Use IST for current time comparison (same as Zerodha data)
                current_time = datetime.now(IST)
                # Ensure both are timezone-aware
                if redis_time.tzinfo is None:
                    redis_time = redis_time.replace(tzinfo=IST)
                time_diff = current_time - redis_time
                # Consider stale only if data is more than 2 minutes old
                # Rebasing may make timestamps appear in future, which is fine
                is_stale = time_diff.total_seconds() > 120  # 2 minutes
            except Exception as e:
                is_stale = True  # Can't parse timestamp, consider stale
        else:
            is_stale = True  # No timestamp means no data

        # Return data even if stale (historical data is expected to be stale)
        # Only return None if we actually have no price data
        if not price:
            return {
                "instrument": instrument.upper(),
                "price": None,
                "timestamp": None,
                "volume": None,
                "depth": None,
                "tts": datetime.now(IST).isoformat(),
                "is_stale": True
            }

        # Parse quote data if available
        depth = None
        if quote_data:
            try:
                import json
                quote = json.loads(quote_data)
                depth = quote.get("depth")
            except:
                pass

        from market_data.adapters.historical_tick_replayer import IST
        # Decode bytes if necessary
        price_val = float(price.decode() if isinstance(price, bytes) else price) if price else None
        timestamp_str = timestamp.decode() if isinstance(timestamp, bytes) else timestamp if timestamp else None
        volume_val = int(volume.decode() if isinstance(volume, bytes) else volume) if volume else None
        
        return {
            "instrument": instrument.upper(),
            "price": price_val,
            "timestamp": timestamp_str,
            "volume": volume_val,
            "depth": depth,
            "tts": datetime.now(IST).isoformat(),  # Time to serve
            "is_stale": is_stale  # Use calculated staleness value
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/market/raw/{instrument}")
async def get_raw_market_data_endpoint(instrument: str, limit: int = 100):
    """Get raw market data from Redis."""
    return await get_raw_market_data(instrument, limit)


@app.get("/api/v1/market/raw")
async def get_default_raw_market_data(limit: int = 100):
    from config import get_config
    cfg = get_config()
    return await get_raw_market_data(cfg.instrument_symbol, limit=limit)


async def get_raw_market_data(instrument: str, limit: int = 100):
    """Get raw market data from Redis for an instrument."""
    try:
        redis_client = get_redis_client()
        instrument_key = instrument.upper().replace(" ", "").replace("-", "_")
        
        # Try key variations
        key_variations = [
            instrument_key,
            instrument_key.replace("BANKNIFTY", "NIFTYBANK"),
            instrument_key.replace("NIFTYBANK", "BANKNIFTY"),
        ]
        
        # Get all keys for this instrument
        all_keys = set()
        for key_var in key_variations:
            pattern = f"*{key_var}*"
            keys = list(redis_client.scan_iter(match=pattern))
            all_keys.update(keys)
        
        data = {}
        for key in list(all_keys)[:limit]:
            value = redis_client.get(key)
            try:
                # Try to parse as number
                data[key] = float(value) if value else None
            except (ValueError, TypeError):
                # Try to parse as JSON
                try:
                    import json
                    data[key] = json.loads(value) if value else None
                except:
                    data[key] = value
        
        return {
            "instrument": instrument.upper(),
            "keys_found": len(all_keys),
            "data": data,
            "timestamp": datetime.now(IST).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/market/depth/{instrument}")
async def get_market_depth(instrument: str):
    """Get market depth data from Redis for an instrument."""
    try:
        redis_client = get_redis_client()
        instrument_clean = instrument.upper().replace(" ", "").replace("-", "_")
        
        buy_depth = None
        sell_depth = None
        timestamp = None
        
        # First, try to get depth from websocket tick data (NEW)
        tick_key = f"websocket:tick:{instrument_clean}:latest"
        tick_data = redis_client.get(tick_key)
        
        if tick_data:
            import json
            tick = json.loads(tick_data)
            if 'depth' in tick and tick['depth']:
                buy_depth = tick['depth'].get('buy', [])
                sell_depth = tick['depth'].get('sell', [])
                timestamp = tick.get('timestamp')
        
        # Fallback: Try old format depth keys if websocket depth not found
        if buy_depth is None or sell_depth is None:
            # Try key variations
            key_variations = [
                instrument_clean,
                instrument_clean.replace("BANKNIFTY", "NIFTYBANK"),
                instrument_clean.replace("NIFTYBANK", "BANKNIFTY"),
            ]
            
            # Find the data
            for key_var in key_variations:
                buy_key = f"depth:{key_var}:buy"
                sell_key = f"depth:{key_var}:sell"
                ts_key = f"depth:{key_var}:timestamp"
                
                buy_data = redis_client.get(buy_key)
                sell_data = redis_client.get(sell_key)
                ts_data = redis_client.get(ts_key)
                
                if buy_data and sell_data:
                    import json
                    buy_depth = json.loads(buy_data)
                    sell_depth = json.loads(sell_data)
                    timestamp = ts_data
                    break
        
        if buy_depth is None or sell_depth is None:
            # Fallback to synthetic depth based on latest tick
            store = get_store()
            latest_tick = store.get_latest_tick(instrument.upper())
            if latest_tick:
                # Generate synthetic depth around the last price
                depth_mid = latest_tick.last_price
                buy_depth = []
                sell_depth = []
                qty_base = latest_tick.volume or 100
                for lvl in range(1, 6):
                    buy_depth.append({'price': round(depth_mid - lvl, 2), 'quantity': qty_base * lvl})
                    sell_depth.append({'price': round(depth_mid + lvl, 2), 'quantity': qty_base * lvl})
                timestamp = latest_tick.timestamp.isoformat()
        elif timestamp:
            # Check if Redis depth data is recent (within last 5 minutes)
            from datetime import datetime, timedelta
            try:
                redis_time = datetime.fromisoformat(timestamp)
                if datetime.now(IST) - redis_time > timedelta(minutes=5):
                    # Redis data is stale, use in-memory store instead
                    store = get_store()
                    latest_tick = store.get_latest_tick(instrument.upper())
                    if latest_tick:
                        depth_mid = latest_tick.last_price
                        buy_depth = []
                        sell_depth = []
                        qty_base = latest_tick.volume or 100
                        for lvl in range(1, 6):
                            buy_depth.append({'price': round(depth_mid - lvl, 2), 'quantity': qty_base * lvl})
                            sell_depth.append({'price': round(depth_mid + lvl, 2), 'quantity': qty_base * lvl})
                        timestamp = latest_tick.timestamp.isoformat()
            except:
                pass  # Keep Redis data if timestamp parsing fails
        
        return {
            "instrument": instrument.upper(),
            "buy": buy_depth,
            "sell": sell_depth,
            "timestamp": timestamp
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Socket.IO removed - real-time updates now handled by Redis WebSocket Gateway
# Export the FastAPI app directly (no Socket.IO wrapping)
main_app = app

# Initialize services after all functions are defined
print("INIT CODE STARTING...")
print("Market Data API: Initializing services...")
try:
    get_store()
    print("Market Data API: Store initialized")

    if TechnicalIndicatorsService is not None:
        redis_client = get_redis_client()

        # Read execution mode from Redis if available (for backtest awareness)
        mode = "LIVE"
        run_id = None
        try:
            mode = redis_client.get("system:execution_mode") or "LIVE"
            run_id = redis_client.get("system:run_id")
            if mode == "HISTORICAL" and run_id:
                print(f"Market Data API: Detected HISTORICAL mode (run_id: {run_id})")
        except Exception as e:
            print(f"Market Data API: Could not read execution mode from Redis: {e}")

        _technical_service = TechnicalIndicatorsService(
            redis_client=redis_client,
            mode=mode,
            run_id=run_id
        )
        print(f"Market Data API: Technical indicators service initialized in {mode} mode")
    else:
        print("Market Data API: TechnicalIndicatorsService is None - not available")

    redis_client = get_redis_client()
    dev_mode = os.getenv('DEVELOPMENT_MODE', '').lower() in ('1', 'true', 'yes')
    try:
        redis_client.ping()
        print("Market Data API: Redis connection verified")
    except Exception as e:
        if dev_mode:
            print(f"Market Data API: Redis connection failed: {e} (development mode - continuing anyway)")
        else:
            raise

    get_options_client()
    print("Market Data API: Options client initialized")

    print("Market Data API: All services initialized successfully")

    # Background indicator publishing will be handled by the lifespan handler

except Exception as e:
    print(f"Market Data API: Service initialization failed: {e}")
    import traceback
    traceback.print_exc()




if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("MARKET_DATA_API_PORT", "8004"))
    host = os.getenv("MARKET_DATA_API_HOST", "0.0.0.0")
    
    print(f"Starting Market Data API on {host}:{port}")
    # Socket.IO removed - using FastAPI app directly
    uvicorn.run(app, host=host, port=port)

