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
import math
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from dataclasses import asdict
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import redis

logger = logging.getLogger(__name__)

# Add parent directory to path for config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from config import get_config
from redis_key_manager import get_redis_key, get_execution_mode
from .env_settings import credentials_path_candidates, redis_config, resolve_instrument_symbol
from .kite_client import create_kite_client

# Get configuration for dynamic instrument usage
config = get_config()
INSTRUMENT_SYMBOL = config.instrument_symbol
INSTRUMENT_KEY = config.instrument_key

# IST timezone for Indian financial markets
IST = timezone(timedelta(hours=5, minutes=30))
INDICATOR_WARMUP_REQUIREMENTS = {
    "rsi": 14,
    "macd": 26,
    "bollinger": 20,
    "cci": 20,
    "stoch": 14,
    "atr": 14,
    "mfi": 14,
    "roc": 12,
    "momentum": 10,
    "adx": 14,
}

from .api import build_store
try:
    from .adapters.zerodha_options_chain import ZerodhaOptionsChainAdapter
except (ImportError, KeyboardInterrupt) as e:
    if isinstance(e, KeyboardInterrupt):
        raise
    print(f"WARNING: Zerodha options chain adapter not available: {e}")
    ZerodhaOptionsChainAdapter = None
except Exception as e:
    print(f"WARNING: Zerodha options chain adapter not available: {e}")
    ZerodhaOptionsChainAdapter = None
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


def _redis_value_to_str(value: Any) -> Optional[str]:
    """Normalize Redis value (bytes/str/other) to string."""
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            return value.decode()
        except Exception:
            return None
    return str(value)


def _redis_is_enabled(value: Any) -> bool:
    """Return True for common truthy Redis flag values."""
    s = _redis_value_to_str(value)
    if s is None:
        return False
    return s.strip().lower() in {"1", "true", "yes", "on"}


def resample_ohlc_bars(bars: List[Any], target_timeframe: str) -> List[Any]:
    """Resample OHLC bars from 1min to target timeframe.
    
    Args:
        bars: List of OHLCBar objects (assumed to be 1min)
        target_timeframe: Target timeframe (e.g., '5min', '15min', '1h')
    
    Returns:
        List of resampled OHLCBar objects
    """
    if not bars:
        return []
    
    import pandas as pd
    from .contracts import OHLCBar
    
    # Convert to DataFrame
    data = []
    for bar in bars:
        data.append({
            'timestamp': bar.start_at,
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume or 0,
            'open_interest': bar.open_interest or 0
        })
    
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
    df = df.dropna(subset=['timestamp']).sort_values('timestamp').set_index('timestamp')
    
    # Parse target timeframe
    if target_timeframe.endswith('min'):
        # Pandas 2.2+ prefers explicit "min" over legacy "T"
        freq = f"{target_timeframe[:-3]}min"
    elif target_timeframe.endswith('m') and target_timeframe[:-1].isdigit():
        freq = f"{target_timeframe[:-1]}min"
    elif target_timeframe.endswith('h'):
        freq = f"{target_timeframe[:-1]}h"
    elif target_timeframe == '1d' or target_timeframe.endswith('d'):
        freq = target_timeframe
    else:
        # Default to 5min
        freq = '5T'
    
    # Resample
    resampled = df.resample(freq).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'open_interest': 'last'
    }).dropna()
    
    # Convert back to OHLCBar objects
    resampled_bars = []
    for timestamp, row in resampled.iterrows():
        resampled_bars.append(OHLCBar(
            instrument=bars[0].instrument,
            timeframe=target_timeframe,
            open=row['open'],
            high=row['high'],
            low=row['low'],
            close=row['close'],
            volume=int(row['volume']),
            start_at=timestamp.to_pydatetime(),
            end_at=(timestamp + pd.Timedelta(freq)).to_pydatetime(),
            open_interest=int(row['open_interest']) if pd.notna(row['open_interest']) else None
        ))
    
    return resampled_bars


def _persist_resampled_ohlc(instrument: str, timeframe: str, bars: List[Any], keep_bars: int = 600) -> None:
    """Persist derived OHLC bars to canonical Redis sorted-set key."""
    if not bars:
        return
    try:
        redis_client = get_redis_client()
        key = get_redis_key(f"ohlc_sorted:{instrument.upper()}:{timeframe}")
        pipe = redis_client.pipeline()
        for bar in bars:
            payload = {
                "instrument": bar.instrument,
                "timeframe": bar.timeframe,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "oi": bar.open_interest,
                "start_at": bar.start_at.isoformat(),
            }
            pipe.zadd(key, {json.dumps(payload, default=str): float(bar.start_at.timestamp())})
        pipe.execute()

        size = int(redis_client.zcard(key) or 0)
        overflow = size - keep_bars
        if overflow > 0:
            redis_client.zremrangebyrank(key, 0, overflow - 1)
    except Exception:
        # Best-effort writeback only.
        pass


def _timeframe_aliases_for_ohlc(timeframe: str) -> List[str]:
    """Return best-effort aliases for OHLC timeframe keys."""
    tf = (timeframe or "").strip().lower()
    if not tf:
        return ["1m", "1min"]

    aliases: List[str] = [tf]
    if tf == "minute":
        aliases.extend(["1m", "1min"])
    if tf == "1m":
        aliases.append("1min")
    if tf == "1min":
        aliases.append("1m")

    if tf.endswith("min"):
        digits = tf[:-3]
        if digits.isdigit():
            aliases.append(f"{digits}m")
    elif tf.endswith("m") and tf[:-1].isdigit():
        aliases.append(f"{tf[:-1]}min")

    # Preserve order while removing duplicates
    return list(dict.fromkeys(aliases))


def _canonical_indicator_timeframe(timeframe: str) -> str:
    """Normalize timeframe labels for indicator cache/storage."""
    tf = (timeframe or "").strip().lower()
    if tf in ("minute", "1m", "1min", "1minute"):
        return "1m"
    if tf.endswith("min") and tf[:-3].isdigit():
        n = tf[:-3]
        return "1m" if n == "1" else f"{n}m"
    return tf or "1m"


def _read_ohlc_from_redis_any_mode(instrument: str, timeframe: str, limit: int = 200) -> List[OHLCBar]:
    """Read OHLC rows from Redis sorted sets across live/historical/paper prefixes."""
    instrument_upper = instrument.upper()
    tfs = _timeframe_aliases_for_ohlc(timeframe)
    prefixes = ["live", "historical", "paper", ""]

    try:
        redis_client = get_redis_client()
    except Exception:
        return []

    rows: List[str] = []
    used_key: Optional[str] = None

    for tf in tfs:
        for prefix in prefixes:
            sorted_key = f"{prefix + ':' if prefix else ''}ohlc_sorted:{instrument_upper}:{tf}"
            try:
                if redis_client.zcard(sorted_key) <= 0:
                    continue
                rows = redis_client.zrange(sorted_key, -max(limit, 1), -1) if limit > 0 else redis_client.zrange(sorted_key, 0, -1)
                if rows:
                    used_key = sorted_key
                    break
            except Exception:
                continue
        if rows:
            break

    if not rows:
        return []

    parsed: List[OHLCBar] = []
    for payload in rows:
        try:
            import json
            item = json.loads(payload)
            ts_raw = item.get("start_at") or item.get("timestamp")
            if ts_raw is None:
                continue

            if isinstance(ts_raw, (int, float)):
                start_at = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
            else:
                start_at = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))

            end_raw = item.get("end_at")
            if isinstance(end_raw, (int, float)):
                end_at = datetime.fromtimestamp(end_raw, tz=timezone.utc)
            elif end_raw:
                end_at = datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))
            else:
                end_at = start_at

            parsed.append(OHLCBar(
                instrument=item.get("instrument") or instrument_upper,
                timeframe=item.get("timeframe") or timeframe,
                open=float(item.get("open", 0.0)),
                high=float(item.get("high", 0.0)),
                low=float(item.get("low", 0.0)),
                close=float(item.get("close", 0.0)),
                volume=int(item.get("volume", 0) or 0),
                open_interest=item.get("oi") if item.get("oi") is not None else item.get("open_interest"),
                start_at=start_at,
                end_at=end_at,
            ))
        except Exception:
            continue

    parsed.sort(key=lambda b: b.start_at)
    if parsed:
        logger.info(f"Loaded {len(parsed)} OHLC bars from Redis key {used_key}")
    return parsed


# Pydantic models for API requests/responses
class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    module: str
    timestamp: str
    mode: str = ""
    dependencies: Dict[str, str]


class MarketTickResponse(BaseModel):
    """Market tick response."""
    instrument: str
    timestamp: str
    last_price: float
    volume: Optional[int] = None
    oi: Optional[int] = None
    oi_day_high: Optional[int] = None
    oi_day_low: Optional[int] = None


class OHLCResponse(BaseModel):
    """OHLC bar response."""
    instrument: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int]
    oi: Optional[int] = None
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
    indicator_task = None
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

        print("Market Data API: Services initialized successfully")

        # Start background task to continuously calculate and publish indicators
        indicator_publish_interval_sec = max(
            1.0,
            float(os.getenv("INDICATOR_PUBLISH_INTERVAL_SECONDS", "5"))
        )

        async def publish_indicators():
            """Background task to continuously calculate and publish technical indicators."""
            print(
                f"Market Data API: Starting indicator publisher background task "
                f"(interval={indicator_publish_interval_sec:.1f}s)..."
            )
            while True:
                try:
                    if _technical_service is not None and redis_client is not None:
                        # Use canonical sorted set for OHLC data
                        ohlc_dicts = []
                        sorted_key = get_redis_key(f"ohlc_sorted:{INSTRUMENT_KEY}:1m")
                        try:
                            sorted_entries = redis_client.zrange(sorted_key, -100, -1)
                            if sorted_entries:
                                for je in sorted_entries:
                                    try:
                                        bar = json.loads(je)
                                        ohlc_dicts.append({
                                            "timestamp": bar.get('start_at', bar.get('timestamp')),
                                            "open": bar.get('open'),
                                            "high": bar.get('high'),
                                            "low": bar.get('low'),
                                            "close": bar.get('close'),
                                            "volume": bar.get('volume', 0),
                                            "oi": bar.get('oi') or bar.get('open_interest')
                                        })
                                    except Exception:
                                        continue
                        except Exception as e:
                            print(f"Market Data API: Error accessing sorted set {sorted_key}: {e}")

                        # Sort by timestamp (oldest first for technical analysis)
                        ohlc_dicts.sort(key=lambda x: x['timestamp'])

                        if len(ohlc_dicts) >= 14:
                            _technical_service.initialize_with_ohlc_data(INSTRUMENT_KEY, ohlc_dicts)
                            _technical_service.calculate_indicators(INSTRUMENT_KEY)
                except Exception as e:
                    print(f"Market Data API: Error publishing indicators: {e}")

                await asyncio.sleep(indicator_publish_interval_sec)

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
_technical_service: Optional[Any] = None


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
        cfg = redis_config(decode_responses=True)
        cfg.setdefault("socket_connect_timeout", float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "2")))
        cfg.setdefault("socket_timeout", float(os.getenv("REDIS_SOCKET_TIMEOUT", "2")))
        cfg.setdefault("retry_on_timeout", True)
        cfg.setdefault("health_check_interval", int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "15")))
        _redis_client = redis.Redis(**cfg)
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
        import json

        # Prefer credentials.json over ambient env values because .env tokens can
        # become stale while credentials.json is refreshed by interactive login.
        api_key = None
        access_token = None

        for cred_path in credentials_path_candidates():
            if not cred_path.exists():
                continue
            try:
                with cred_path.open("r", encoding="utf-8-sig") as f:
                    creds = json.load(f)
                data_obj = creds.get("data") if isinstance(creds.get("data"), dict) else {}
                cand_api_key = creds.get("api_key")
                cand_access_token = creds.get("access_token") or data_obj.get("access_token")
                if cand_api_key and cand_access_token:
                    api_key = cand_api_key
                    access_token = cand_access_token
                    break
            except Exception:
                continue

        if not api_key or not access_token:
            env_api_key = os.getenv("KITE_API_KEY")
            env_access_token = os.getenv("KITE_ACCESS_TOKEN")
            if env_api_key and env_access_token:
                api_key = env_api_key
                access_token = env_access_token
        
        if not api_key or not access_token:
            return None
        
        kite = create_kite_client(api_key=api_key, access_token=access_token)
        
        # Determine execution mode and live/historical status
        is_live_mode = True  # Default to live mode
        is_backtest_mode = False

        try:
            redis_client = get_redis_client()

            # Check execution mode first (takes precedence)
            execution_mode = redis_client.get("system:execution_mode")
            if execution_mode:
                execution_mode = execution_mode.decode() if isinstance(execution_mode, bytes) else execution_mode
                if str(execution_mode).strip().lower() == "historical":
                    is_live_mode = False  # Historical mode uses LTP, not live quotes

            # If not BACKTEST, check for virtual time (historical replay)
            if not is_backtest_mode:
                virtual_time_enabled = redis_client.get("system:virtual_time:enabled")
                if _redis_is_enabled(virtual_time_enabled):
                    is_live_mode = False
        except Exception:
            # If Redis check fails, fall back to environment variable
            provider_name = os.getenv("TRADING_PROVIDER", "").lower()
            use_mock_env = os.getenv("USE_MOCK_KITE", "false").lower() in ('1', 'true', 'yes')
            is_live_mode = provider_name in ('zerodha', 'kite') and not use_mock_env
        
        historical_source = str(os.getenv("HISTORICAL_SOURCE", "")).strip().lower()

        # Use Zerodha Options Chain Adapter
        try:
            instrument = os.getenv("INSTRUMENT_SYMBOL", INSTRUMENT_SYMBOL)

            if is_live_mode:
                print(f"Market Data API: Using Zerodha Options Chain (LIVE mode - real-time quote() API) for {instrument}")
                _options_client = ZerodhaOptionsChainAdapter(kite, instrument, use_live_quotes=True)
                print(f"Market Data API: [OK] Zerodha options client initialized (LIVE - real-time quotes)")
            else:
                if historical_source == "zerodha":
                    print(f"Market Data API: Using Zerodha Options Chain (HISTORICAL mode - LTP API) for {instrument}")
                    _options_client = ZerodhaOptionsChainAdapter(kite, instrument, use_live_quotes=False)
                    print(f"Market Data API: [OK] Zerodha options client initialized (HISTORICAL - LTP quotes)")
                else:
                    # For synthetic/file replay, keep API-side synthetic fallback behavior.
                    print(f"Market Data API: Historical mode detected; using synthetic options fallback for {instrument}")
                    _options_client = None
                    return None
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


def _next_weekly_expiry(now: Optional[datetime] = None) -> datetime:
    """Best-effort next weekly expiry (Thursday 15:30 IST)."""
    now = now or datetime.now(IST)
    # Python weekday: Monday=0, Thursday=3
    days_ahead = (3 - now.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    target = now + timedelta(days=days_ahead)
    return target.replace(hour=15, minute=30, second=0, microsecond=0)


def _reference_price_for_options(instrument: str) -> Optional[float]:
    """Fetch a reference price from ticks/Redis for synthetic chain fallback."""
    try:
        store = get_store()
        tick = store.get_latest_tick(instrument.upper())
        if tick and tick.last_price:
            return float(tick.last_price)
    except Exception:
        pass

    try:
        redis_client = get_redis_client()
        price_val = redis_client.get(get_redis_key(f"price:{instrument.upper()}:latest"))
        if price_val is not None:
            return float(price_val)
    except Exception:
        pass

    return None


def _build_synthetic_options_chain(instrument: str) -> OptionsChainResponse:
    """Create a deterministic synthetic options chain when upstream data is unavailable."""
    price = _reference_price_for_options(instrument) or 50000.0

    # Pick a strike ladder around the reference price
    step = 100
    center = int(round(price / step) * step)
    strikes: List[Dict[str, Any]] = []
    total_call_oi = 0
    total_put_oi = 0

    for offset in range(-6, 7):  # 13 strikes wide
        strike_price = center + offset * step
        distance = abs(offset) or 1

        # Liquidity/oi decay with distance from ATM
        base_oi = max(1500 - (distance * 120), 200)
        ce_oi = int(base_oi * (0.6 if offset >= 0 else 0.4))
        pe_oi = int(base_oi * (0.6 if offset <= 0 else 0.4))
        total_call_oi += ce_oi
        total_put_oi += pe_oi

        # Simple priced ladder respecting intrinsic relationships
        intrinsic_call = max(price - strike_price, 0)
        intrinsic_put = max(strike_price - price, 0)
        ce_ltp = max(intrinsic_call + (distance * 3), 5)
        pe_ltp = max(intrinsic_put + (distance * 3), 5)

        strikes.append({
            "strike": strike_price,
            "ce_ltp": round(ce_ltp, 2),
            "ce_oi": ce_oi,
            "ce_volume": max(int(ce_oi * 0.1), 25),
            "pe_ltp": round(pe_ltp, 2),
            "pe_oi": pe_oi,
            "pe_volume": max(int(pe_oi * 0.1), 25),
            "liquidity_score": max(100 - distance * 8, 20),
        })

    pcr = (total_put_oi / total_call_oi) if total_call_oi > 0 else None

    # Max pain approximated at strike with highest combined OI
    max_pain = max(strikes, key=lambda s: (s.get("ce_oi", 0) + s.get("pe_oi", 0)))
    expiry_dt = _next_weekly_expiry()

    return OptionsChainResponse(
        instrument=instrument.upper(),
        expiry=expiry_dt.date().isoformat(),
        strikes=strikes,
        timestamp=datetime.now(IST).isoformat(),
        futures_price=price,
        pcr=pcr,
        max_pain=max_pain.get("strike") if isinstance(max_pain, dict) else None,
    )


def _count_ohlc_bars_fast(instrument: str, timeframe: str, limit_hint: int = 10) -> int:
    """Fast bar count probe using Redis zcard without materializing bar payloads."""
    instrument_upper = str(instrument or "").upper()
    if not instrument_upper:
        return 0

    redis_client = get_redis_client()
    best = 0
    for tf in _timeframe_aliases_for_ohlc(timeframe):
        for prefix in ("live", "historical", "paper", ""):
            key = f"{prefix + ':' if prefix else ''}ohlc_sorted:{instrument_upper}:{tf}"
            try:
                cnt = int(redis_client.zcard(key) or 0)
            except Exception:
                continue
            if cnt > best:
                best = cnt
            if best >= max(1, int(limit_hint or 1)):
                return best
    return best


def _cache_options_chain_snapshot(instrument: str, payload: Dict[str, Any], *, source: str = "market_data_api") -> None:
    """Store latest options chain in Redis and publish to market options channel."""
    try:
        instrument_upper = str(instrument or "").upper()
        if not instrument_upper:
            return
        mode_hint = str(get_execution_mode() or "").strip().lower()
        historical_source = str(os.getenv("HISTORICAL_SOURCE", "")).strip().lower()
        if mode_hint == "historical" and historical_source == "local" and source == "synthetic_fallback":
            logger.info("Skipping synthetic options cache in historical+local mode for %s", instrument_upper)
            return

        redis_client = get_redis_client()
        snapshot = dict(payload or {})
        snapshot["instrument"] = instrument_upper
        snapshot.setdefault("timestamp", datetime.now(IST).isoformat())
        snapshot.setdefault("status", "ok")
        snapshot.setdefault("source", source)
        snapshot.setdefault("mode_hint", str(get_execution_mode() or "").strip().lower())

        ttl = max(5, int(os.getenv("OPTIONS_CHAIN_TTL_SECONDS", "90")))
        # Historical sessions are replay-driven; keep options snapshots longer so
        # key presence is stable without requiring frequent re-fetches.
        if mode_hint == "historical":
            ttl = max(ttl, int(os.getenv("HISTORICAL_OPTIONS_CHAIN_TTL_SECONDS", "1800")))
        snapshot_json = json.dumps(snapshot, default=str)

        # Primary key with mode prefix.
        key = get_redis_key(f"options:{instrument_upper}:chain")
        redis_client.setex(key, ttl, snapshot_json)

        # Optional expiry-scoped key when expiry is available.
        expiry = snapshot.get("expiry")
        if expiry:
            exp_key = get_redis_key(f"options:{instrument_upper}:{expiry}:chain")
            redis_client.setex(exp_key, ttl, snapshot_json)

        redis_client.publish(f"market:options:{instrument_upper}", snapshot_json)
    except Exception as exc:
        logger.debug("Failed to cache/publish options snapshot for %s: %s", instrument, exc)


def _cache_depth_snapshot(
    instrument: str,
    buy_depth: Optional[List[Dict[str, Any]]],
    sell_depth: Optional[List[Dict[str, Any]]],
    timestamp: Optional[str],
) -> None:
    """Persist latest depth snapshot under canonical Redis keys."""
    try:
        instrument_upper = str(instrument or "").upper()
        if not instrument_upper:
            return

        redis_client = get_redis_client()
        ttl = max(5, int(os.getenv("DEPTH_TTL_SECONDS", "180")))
        buy = buy_depth or []
        sell = sell_depth or []
        ts = timestamp or datetime.now(IST).isoformat()

        redis_client.setex(get_redis_key(f"depth:{instrument_upper}:buy"), ttl, json.dumps(buy, default=str))
        redis_client.setex(get_redis_key(f"depth:{instrument_upper}:sell"), ttl, json.dumps(sell, default=str))
        redis_client.setex(get_redis_key(f"depth:{instrument_upper}:timestamp"), ttl, str(ts))
        redis_client.setex(
            get_redis_key(f"depth:{instrument_upper}:total_bid_qty"),
            ttl,
            str(sum(float(level.get("quantity", 0) or 0) for level in buy)),
        )
        redis_client.setex(
            get_redis_key(f"depth:{instrument_upper}:total_ask_qty"),
            ttl,
            str(sum(float(level.get("quantity", 0) or 0) for level in sell)),
        )
    except Exception as exc:
        logger.debug("Failed to cache depth snapshot for %s: %s", instrument, exc)


def _strict_real_only_live() -> bool:
    """When enabled, never serve synthetic/mock market data in live mode."""
    return os.getenv("LIVE_STRICT_REAL_ONLY", "1").strip().lower() in {"1", "true", "yes", "on"}


def _is_live_mode() -> bool:
    return str(get_execution_mode() or "").strip().lower() == "live"


def _exc_summary(exc: Exception) -> str:
    """Return a stable, non-empty error summary for API responses/logs."""
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__


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
            from datetime import datetime
            
            instrument = INSTRUMENT_KEY
            price_key = get_redis_key(f"price:{instrument}:latest")
            timestamp_key = get_redis_key(f"price:{instrument}:latest_ts")
            
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
                    if _redis_is_enabled(virtual_time_enabled):
                        # In historical replay mode, compare against virtual time
                        virtual_time_str = redis_client.get("system:virtual_time:current")
                        if virtual_time_str:
                            virtual_time_str = _redis_value_to_str(virtual_time_str)
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
            # Fast key-cardinality check avoids expensive object parsing in health path.
            five_min_count = _count_ohlc_bars_fast(INSTRUMENT_KEY, "5m", limit_hint=10)
            if five_min_count >= 5:  # Require at least 5 bars of 5-minute data
                dependencies["five_min_data"] = f"available_{five_min_count}_bars"
            else:
                dependencies["five_min_data"] = f"insufficient_data_{five_min_count}_bars_need_5"
        except Exception as e:
            dependencies["five_min_data"] = f"check_failed: {str(e)}"
    else:
        dependencies["five_min_data"] = "redis_unavailable"
    
    # Determine overall status

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
    
    # Get execution mode
    from redis_key_manager import get_execution_mode
    mode = get_execution_mode()
    
    return HealthResponse(
        status=status,
        module="market_data",
        timestamp=datetime.now(IST).isoformat(),
        mode=mode,
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
            instrument = resolve_instrument_symbol(INSTRUMENT_SYMBOL or INSTRUMENT_KEY)
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
        virtual_time_enabled_raw = redis_client.get("system:virtual_time:enabled")
        virtual_time_enabled = _redis_is_enabled(virtual_time_enabled_raw)
        
        virtual_time = None
        if virtual_time_enabled:
            vt_raw = redis_client.get("system:virtual_time:current")
            virtual_time = _redis_value_to_str(vt_raw)
        
        # Get Redis mode
        redis_mode_raw = redis_client.get("system:execution_mode")
        redis_mode = _redis_value_to_str(redis_mode_raw)
        
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
            price_key = get_redis_key(f"price:{key_var}:last_price")
            timestamp_key = get_redis_key(f"price:{key_var}:latest_ts")
            volume_key = get_redis_key(f"price:{key_var}:volume")
            
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
            volume=tick.volume,
            oi=tick.open_interest,
            oi_day_high=tick.oi_day_high,
            oi_day_low=tick.oi_day_low
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _normalize_timeframe(timeframe: str) -> str:
    tf = (timeframe or "1m").strip().lower()
    if tf in ("minute", "1m", "1min", "1minute"):
        return "1m"
    if tf.endswith("minute"):
        minutes = tf.replace("minute", "").strip()
        if minutes.isdigit():
            return "1m" if minutes == "1" else f"{minutes}m"
    if tf.endswith("min") and tf[:-3].isdigit():
        minutes = tf[:-3]
        return "1m" if minutes == "1" else f"{minutes}m"
    if tf.endswith("m") and tf[:-1].isdigit():
        minutes = tf[:-1]
        return "1m" if minutes == "1" else f"{minutes}m"
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
                    
                    # Handle timestamp conversion
                    ts_raw = bar_data.get("start_at") or bar_data.get("timestamp")
                    if isinstance(ts_raw, (int, float)):
                        # Unix timestamp - convert to ISO format
                        start_at_iso = datetime.fromtimestamp(ts_raw).isoformat() + 'Z'
                    else:
                        # Already ISO format or string
                        try:
                            dt = datetime.fromisoformat(ts_raw)
                            start_at_iso = dt.isoformat() + 'Z'
                        except:
                            start_at_iso = datetime.now().isoformat() + 'Z'
                    
                    response.append(
                        OHLCResponse(
                            instrument=bar_data.get("instrument", instrument_upper),
                            timeframe=bar_data.get("timeframe", timeframe),
                            open=float(bar_data.get("open", 0)),
                            high=float(bar_data.get("high", 0)),
                            low=float(bar_data.get("low", 0)),
                            close=float(bar_data.get("close", 0)),
                            volume=bar_data.get("volume"),
                            oi=bar_data.get("oi") or bar_data.get("open_interest"),
                            start_at=start_at_iso
                        )
                    )
                except Exception:
                    continue

            if not response:
                return []

            # Deduplicate by candle timestamp (keep latest payload for each timestamp).
            by_ts: Dict[str, OHLCResponse] = {}
            for row in response:
                by_ts[row.start_at] = row
            return [by_ts[k] for k in sorted(by_ts.keys())]

        # Default mode: latest bars via store (existing behavior)
        store = get_store()
        bars = list(store.get_ohlc(instrument_upper, normalized_tf, limit))

        # If requested timeframe is higher than 1m and not yet stored, resample on-demand
        if not bars and normalized_tf != "1m":
            try:
                base_limit = max(limit * 5, 100)
                base_bars = list(store.get_ohlc(instrument_upper, "1m", base_limit))
                if not base_bars:
                    base_bars = _read_ohlc_from_redis_any_mode(instrument_upper, "1m", base_limit)
                if base_bars:
                    bars = resample_ohlc_bars(base_bars, normalized_tf)
                    _persist_resampled_ohlc(instrument_upper, normalized_tf, bars)
            except Exception:
                bars = bars  # Keep empty if resample fails silently

        if not bars:
            return []

        if normalized_tf != "1m":
            _persist_resampled_ohlc(instrument_upper, normalized_tf, bars)

        # Deduplicate by candle timestamp while preserving returned order.
        unique_bars = []
        seen_ts = set()
        for bar in bars:
            ts = bar.start_at.isoformat() if hasattr(bar.start_at, "isoformat") else str(bar.start_at)
            if ts in seen_ts:
                continue
            seen_ts.add(ts)
            unique_bars.append(bar)

        return [
            OHLCResponse(
                instrument=bar.instrument,
                timeframe=bar.timeframe,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                oi=bar.open_interest,
                start_at=bar.start_at.isoformat() + 'Z'
            )
            for bar in unique_bars
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/market/ohlc/{instrument}", response_model=List[OHLCResponse])
async def get_ohlc(
    instrument: str,
    timeframe: str = "1m",
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
    timeframe: str = "1m",
    limit: int = 100,
    order: str = "desc"
):
    """Alias for OHLC endpoint (shorter path)."""
    return await _get_ohlc_impl(instrument, timeframe, limit, order.lower())


def _discover_market_instruments(redis_client, max_instruments: int = 100) -> List[str]:
    """Best-effort discovery of instrument symbols from Redis keys."""
    instruments = set()
    skip_instruments = {"FALLBACK_TEST"}
    patterns = [
        "*:ohlc_sorted:*:*",
        "ohlc_sorted:*:*",
        "*:websocket:tick:*:latest",
        "websocket:tick:*:latest",
        "*:price:*:latest",
        "price:*:latest",
    ]

    for pattern in patterns:
        cursor = 0
        while True:
            try:
                cursor, keys = redis_client.scan(cursor=cursor, match=pattern, count=500)
            except Exception:
                break

            for key in keys or []:
                try:
                    parts = str(key).split(":")
                    instrument = None

                    # live:ohlc_sorted:INSTRUMENT:TF / historical:... / paper:...
                    if len(parts) >= 4 and parts[1] == "ohlc_sorted":
                        instrument = parts[2]
                    # ohlc_sorted:INSTRUMENT:TF
                    elif len(parts) >= 3 and parts[0] == "ohlc_sorted":
                        instrument = parts[1]
                    # live:websocket:tick:INSTRUMENT:latest / historical:...
                    elif len(parts) >= 5 and parts[1] == "websocket" and parts[2] == "tick" and parts[-1] == "latest":
                        instrument = parts[3]
                    # websocket:tick:INSTRUMENT:latest
                    elif len(parts) >= 4 and parts[0] == "websocket" and parts[1] == "tick" and parts[-1] == "latest":
                        instrument = parts[2]
                    # live:price:INSTRUMENT:latest / historical:...
                    elif len(parts) >= 4 and parts[1] == "price" and parts[-1] == "latest":
                        instrument = parts[2]
                    # price:INSTRUMENT:latest
                    elif len(parts) >= 3 and parts[0] == "price" and parts[-1] == "latest":
                        instrument = parts[1]

                    if instrument:
                        instrument_upper = str(instrument).upper()
                        if instrument_upper in skip_instruments:
                            continue
                        instruments.add(instrument_upper)
                        if len(instruments) >= max_instruments:
                            return sorted(instruments)
                except Exception:
                    continue

            if cursor == 0:
                break

    return sorted(instruments)


@app.get("/api/v1/market/instruments")
async def get_market_instruments():
    """Return available market instruments discovered from Redis + config defaults."""
    skip_instruments = {"FALLBACK_TEST"}
    instruments = set()
    if INSTRUMENT_SYMBOL:
        candidate = str(INSTRUMENT_SYMBOL).upper()
        if candidate not in skip_instruments:
            instruments.add(candidate)
    if INSTRUMENT_KEY:
        candidate = str(INSTRUMENT_KEY).upper()
        if candidate not in skip_instruments:
            instruments.add(candidate)

    try:
        redis_client = get_redis_client()
        discovered = _discover_market_instruments(redis_client, max_instruments=100)
        for inst in discovered:
            instruments.add(inst)
    except Exception:
        # Keep endpoint resilient; return defaults even if Redis is unavailable.
        pass

    out = sorted(i for i in instruments if i)
    return {
        "instruments": out,
        "count": len(out),
        "timestamp": datetime.now(IST).isoformat(),
    }


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
        chain: Dict[str, Any] = {}
        instrument_upper = str(instrument or "").upper()
        
        # Check if we should use mock data (mock mode or options client not available)
        use_mock = os.getenv("USE_MOCK_KITE", "false").lower() in ('1', 'true', 'yes')
        strict_live_real_only = _strict_real_only_live() and _is_live_mode()
        mode_hint = str(get_execution_mode() or "").strip().lower()
        historical_source = str(os.getenv("HISTORICAL_SOURCE", "")).strip().lower()
        local_historical_strict = (mode_hint == "historical" and historical_source == "local")

        if local_historical_strict:
            redis_client = get_redis_client()
            candidate_instruments = [instrument_upper]
            if "BANKNIFTY-I" not in candidate_instruments:
                candidate_instruments.append("BANKNIFTY-I")

            for candidate in candidate_instruments:
                local_chain_json = redis_client.get(get_redis_key(f"options:{candidate}:chain"))
                if not local_chain_json:
                    local_chain_json = redis_client.get(f"options:{candidate}:chain")
                if not local_chain_json:
                    continue
                local_chain = json.loads(local_chain_json)
                source = str(local_chain.get("source") or "").strip().lower()
                strikes = list(local_chain.get("strikes") or [])
                if source != "local_historical" or not strikes:
                    continue
                response = OptionsChainResponse(
                    instrument=str(local_chain.get("instrument") or candidate),
                    expiry=str(local_chain.get("expiry") or ""),
                    strikes=strikes,
                    timestamp=str(local_chain.get("timestamp") or datetime.now().isoformat()),
                    futures_price=local_chain.get("futures_price"),
                    pcr=local_chain.get("pcr"),
                    max_pain=local_chain.get("max_pain"),
                )
                return response

            raise HTTPException(
                status_code=503,
                detail=(
                    f"Local historical options chain unavailable for {instrument_upper}. "
                    "Synthetic fallback is disabled in historical+local mode."
                ),
            )
        
        if use_mock:
            if strict_live_real_only:
                raise HTTPException(
                    status_code=503,
                    detail="LIVE_STRICT_REAL_ONLY is enabled: mock options data is disabled in live mode.",
                )
            # Try to get mock data from Redis first
            logger.info(f"Using mock options data for {instrument}")
            redis_client = get_redis_client()
            
            # Try prefixed key first
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
                response = OptionsChainResponse(
                    instrument=chain.get('instrument', instrument),
                    expiry=chain.get('expiry', ''),
                    strikes=chain.get('strikes', []),
                    timestamp=chain.get('timestamp', datetime.now().isoformat()),
                    futures_price=chain.get('futures_price'),
                    pcr=chain.get('pcr'),
                    max_pain=chain.get('max_pain')
                )
                response_dict = response.model_dump() if hasattr(response, "model_dump") else response.dict()
                _cache_options_chain_snapshot(instrument, response_dict, source="mock")
                return response
            else:
                if strict_live_real_only:
                    raise HTTPException(
                        status_code=503,
                        detail="No real options data available for this instrument in live mode.",
                    )
                if local_historical_strict:
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            f"Local historical options chain unavailable for {instrument_upper}. "
                            "Synthetic fallback is disabled in historical+local mode."
                        ),
                    )
                logger.warning("No mock options data found in Redis, returning synthetic fallback chain")
                response = _build_synthetic_options_chain(instrument)
                response_dict = response.model_dump() if hasattr(response, "model_dump") else response.dict()
                _cache_options_chain_snapshot(instrument, response_dict, source="synthetic_fallback")
                return response
        else:
            # Use real Zerodha API
            options_client = get_options_client()
            
            if options_client is None:
                mode_hint = str(get_execution_mode() or "").strip().lower()
                if local_historical_strict:
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            f"Local historical options chain unavailable for {instrument_upper}. "
                            "Synthetic fallback is disabled in historical+local mode."
                        ),
                    )
                if mode_hint in {"historical", "paper"}:
                    logger.info(
                        "Options client unavailable in %s mode; returning synthetic options chain for %s",
                        mode_hint,
                        instrument,
                    )
                    response = _build_synthetic_options_chain(instrument)
                    response_dict = response.model_dump() if hasattr(response, "model_dump") else response.dict()
                    _cache_options_chain_snapshot(instrument, response_dict, source="synthetic_fallback")
                    return response
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Options client not available. "
                        "Requires: (1) Kite API credentials in credentials.json with api_key and access_token, "
                        "(2) Valid Kite API access token. "
                        "Check logs for initialization errors."
                    )
                )
            
            needs_initialize = True
            try:
                cached_options_df = getattr(options_client, "_options_df", None)
                cached_instruments_df = getattr(options_client, "_instruments_df", None)
                if cached_options_df is not None and len(cached_options_df) > 0 and cached_instruments_df is not None and len(cached_instruments_df) > 0:
                    needs_initialize = False
            except Exception:
                needs_initialize = True

            if needs_initialize:
                options_init_timeout = float(os.getenv("OPTIONS_INIT_TIMEOUT_SECONDS", "25"))
                try:
                    await asyncio.wait_for(options_client.initialize(), timeout=options_init_timeout)
                except asyncio.TimeoutError as exc:
                    # allow quick retry on next request if initialize timed out mid-flight
                    if hasattr(options_client, "_last_initialize_attempt_at"):
                        setattr(options_client, "_last_initialize_attempt_at", None)
                    if hasattr(options_client, "_last_initialize_error"):
                        setattr(
                            options_client,
                            "_last_initialize_error",
                            f"initialize timeout after {options_init_timeout:.1f}s",
                        )
                    raise HTTPException(
                        status_code=503,
                        detail=f"Options initialization timed out after {options_init_timeout:.1f}s",
                    ) from exc

            options_fetch_timeout = float(os.getenv("OPTIONS_CHAIN_FETCH_TIMEOUT_SECONDS", "12"))
            try:
                chain = await asyncio.wait_for(
                    options_client.fetch_options_chain(instrument=instrument),
                    timeout=options_fetch_timeout,
                )
            except asyncio.TimeoutError as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"Options fetch timed out after {options_fetch_timeout:.1f}s",
                ) from exc

        # If upstream chain is missing/empty, fall back to synthetic so callers always get a response
        if not chain or chain.get("available") is False or not chain.get("strikes"):
            if strict_live_real_only:
                raise HTTPException(
                    status_code=503,
                    detail="Real-time options chain unavailable in live mode; synthetic fallback is disabled.",
                )
            if local_historical_strict:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        f"Local historical options chain unavailable for {instrument_upper}. "
                        "Synthetic fallback is disabled in historical+local mode."
                    ),
                )
            logger.warning("Options chain unavailable or empty (reason=%s), returning synthetic fallback", chain.get("reason"))
            response = _build_synthetic_options_chain(instrument)
            response_dict = response.model_dump() if hasattr(response, "model_dump") else response.dict()
            _cache_options_chain_snapshot(instrument, response_dict, source="synthetic_fallback")
            return response

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
                    fut_quote = await asyncio.to_thread(options_client.kite.quote, [f"NFO:{fut_symbol}"])
                    if fut_quote:
                        fut_data = list(fut_quote.values())[0]
                        if hasattr(fut_data, 'to_dict'):
                            fut_data = fut_data.to_dict()
                        futures_price = fut_data.get('last_price') or fut_data.get('ohlc', {}).get('close')
                except Exception:
                    # If futures not found, try getting underlying spot price
                    try:
                        underlying_quote = await asyncio.to_thread(options_client.kite.quote, [f"NSE:{instrument.upper()}"])
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
        response_dict = response.model_dump() if hasattr(response, "model_dump") else response.dict()
        _cache_options_chain_snapshot(instrument, response_dict, source=str(chain.get("source") or "zerodha_api"))

        return response
    except HTTPException:
        raise
    except Exception as e:
        strict_live_real_only = _strict_real_only_live() and _is_live_mode()
        mode_hint = str(get_execution_mode() or "").strip().lower()
        historical_source = str(os.getenv("HISTORICAL_SOURCE", "")).strip().lower()
        local_historical_strict = (mode_hint == "historical" and historical_source == "local")
        error_summary = _exc_summary(e)
        if strict_live_real_only:
            logger.warning(
                "Options chain failed in live strict mode (no synthetic fallback): %s",
                error_summary,
            )
            raise HTTPException(
                status_code=503,
                detail=f"Real options chain unavailable in live mode: {error_summary}",
            )
        if local_historical_strict:
            logger.warning(
                "Options chain unavailable in historical+local mode (no synthetic fallback): %s",
                error_summary,
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Local historical options chain unavailable for {instrument_upper}. "
                    f"Synthetic fallback is disabled. Reason: {error_summary}"
                ),
            )
        logger.warning(f"Options chain failed, serving synthetic fallback: {error_summary}")
        try:
            response = _build_synthetic_options_chain(instrument)
            response_dict = response.model_dump() if hasattr(response, "model_dump") else response.dict()
            _cache_options_chain_snapshot(instrument, response_dict, source="synthetic_fallback")
            return response
        except Exception:
            raise HTTPException(status_code=500, detail=error_summary)


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
    timeframe: str = "1m"
):
    """Get technical indicators for an instrument."""
    try:
        def _sanitize_json_numeric(obj: Any) -> Any:
            """Recursively replace NaN/Inf values so JSON serialization never fails."""
            if isinstance(obj, float):
                if math.isnan(obj) or math.isinf(obj):
                    return None
                return obj
            if isinstance(obj, dict):
                return {k: _sanitize_json_numeric(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_sanitize_json_numeric(v) for v in obj]
            if isinstance(obj, tuple):
                return tuple(_sanitize_json_numeric(v) for v in obj)
            # Handle numpy scalar-like values without importing numpy directly
            try:
                if hasattr(obj, "item"):
                    scalar = obj.item()
                    if isinstance(scalar, float) and (math.isnan(scalar) or math.isinf(scalar)):
                        return None
                    return scalar
            except Exception:
                pass
            return obj

        def _to_float(value: Any) -> Optional[float]:
            try:
                if value is None:
                    return None
                f = float(value)
                if math.isnan(f) or math.isinf(f):
                    return None
                return f
            except (TypeError, ValueError):
                return None

        def _is_indicator_cache_suspicious(indicators: Dict[str, Any]) -> bool:
            """Return True when cache contains obviously invalid combinations/values."""
            if not indicators:
                return False

            upper = _to_float(indicators.get("bollinger_upper"))
            lower = _to_float(indicators.get("bollinger_lower"))
            width = _to_float(indicators.get("bollinger_width"))

            if upper is not None and lower is not None and upper < lower:
                return True
            if width is not None and width < 0:
                return True

            for bounded_name in ("mfi_14", "stoch_k", "stoch_d"):
                bounded_value = _to_float(indicators.get(bounded_name))
                if bounded_value is not None and not (0.0 <= bounded_value <= 100.0):
                    return True

            cci = _to_float(indicators.get("cci_20"))
            if cci is not None and abs(cci) > 10000:
                return True

            return False

        # Normalize timeframe to canonical indicator key format.
        tf = _canonical_indicator_timeframe(timeframe)
        
        # Try to get from Redis cache first
        redis_client = get_redis_client()

        def _redis_get_first(keys: List[str]) -> Optional[str]:
            for k in keys:
                if not k:
                    continue
                try:
                    v = redis_client.get(k)
                    s = _redis_value_to_str(v)
                    if s:
                        return s
                except Exception:
                    continue
            return None

        def _derive_stream(update_type: Optional[str], source_hint: str) -> str:
            if (update_type or "").strip().lower() == "tick":
                return "LZ1"
            return "Y2"

        def _derive_update_type(update_type: Optional[str], source_hint: str) -> str:
            if update_type:
                return str(update_type)
            hint = (source_hint or "").strip().lower()
            if hint in {"tick"}:
                return "tick"
            if hint in {"candle", "candle_mtf"}:
                return "candle"
            if hint in {"ohlc_initialize"}:
                return "batch_initialize"
            if hint in {"no_data", "error"}:
                return hint
            return "batch_recalculate"

        def _count_ohlc_bars_for_timeframe() -> int:
            try:
                store = get_store()
                bars = list(store.get_ohlc(instrument.upper(), tf, limit=200))
                if bars:
                    return len(bars)
            except Exception:
                pass
            try:
                return len(_read_ohlc_from_redis_any_mode(instrument.upper(), tf, limit=200))
            except Exception:
                return 0

        def _build_indicators_response(
            indicators_payload: Dict[str, Any],
            source_hint: str,
            *,
            bars_available: Optional[int] = None,
        ) -> Dict[str, Any]:
            safe_payload = _sanitize_json_numeric(indicators_payload or {})

            indicator_timestamp = safe_payload.get("indicator_timestamp") or safe_payload.get("timestamp")
            indicator_source = safe_payload.get("source") or source_hint
            indicator_update_type = safe_payload.get("indicator_update_type") or safe_payload.get("update_type")
            indicator_stream = safe_payload.get("indicator_stream") or safe_payload.get("stream")
            indicator_age_seconds: Optional[float] = None
            indicator_is_stale: bool = True
            indicator_stale_threshold = int(os.getenv("INDICATOR_STALE_SECONDS", "180"))

            if not indicator_timestamp:
                timestamp_candidates = [
                    get_redis_key(f"indicators:{instrument.upper()}:{tf}:indicator_timestamp"),
                    get_redis_key(f"indicators:{instrument.upper()}:{tf}:timestamp"),
                    f"indicators:{instrument.upper()}:{tf}:indicator_timestamp",
                    f"indicators:{instrument.upper()}:{tf}:timestamp",
                ]
                indicator_timestamp = _redis_get_first(timestamp_candidates)

            if not indicator_source:
                source_candidates = [
                    get_redis_key(f"indicators:{instrument.upper()}:{tf}:source"),
                    f"indicators:{instrument.upper()}:{tf}:source",
                ]
                indicator_source = _redis_get_first(source_candidates) or source_hint

            if not indicator_update_type:
                update_type_candidates = [
                    get_redis_key(f"indicators:{instrument.upper()}:{tf}:indicator_update_type"),
                    get_redis_key(f"indicators:{instrument.upper()}:{tf}:update_type"),
                    f"indicators:{instrument.upper()}:{tf}:indicator_update_type",
                    f"indicators:{instrument.upper()}:{tf}:update_type",
                ]
                indicator_update_type = _redis_get_first(update_type_candidates)
            indicator_update_type = _derive_update_type(indicator_update_type, source_hint)

            if not indicator_stream:
                stream_candidates = [
                    get_redis_key(f"indicators:{instrument.upper()}:{tf}:indicator_stream"),
                    get_redis_key(f"indicators:{instrument.upper()}:{tf}:stream"),
                    f"indicators:{instrument.upper()}:{tf}:indicator_stream",
                    f"indicators:{instrument.upper()}:{tf}:stream",
                ]
                indicator_stream = _redis_get_first(stream_candidates)

            if not indicator_stream:
                indicator_stream = _derive_stream(indicator_update_type, source_hint)

            if bars_available is None:
                bars_available = _to_float(safe_payload.get("bars_available"))
                bars_available = int(bars_available) if bars_available is not None else _count_ohlc_bars_for_timeframe()

            # Freshness metadata
            if indicator_timestamp:
                try:
                    ts = datetime.fromisoformat(str(indicator_timestamp).replace("Z", "+00:00"))
                    now_ts = datetime.now(IST)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=IST)
                    indicator_age_seconds = abs((now_ts - ts).total_seconds())
                    indicator_is_stale = indicator_age_seconds > indicator_stale_threshold
                except Exception:
                    indicator_age_seconds = None
                    indicator_is_stale = True

            return {
                "instrument": instrument.upper(),
                "timeframe": tf,
                "timestamp": datetime.now(IST).isoformat(),
                "indicator_timestamp": indicator_timestamp,
                "indicator_source": indicator_source,
                "indicator_stream": indicator_stream,
                "indicator_update_type": indicator_update_type,
                "indicator_age_seconds": indicator_age_seconds,
                "indicator_is_stale": indicator_is_stale,
                "bars_available": int(bars_available) if bars_available is not None else 0,
                "warmup_requirements": dict(INDICATOR_WARMUP_REQUIREMENTS),
                "indicators": safe_payload,
            }

        prefix_candidates: List[str] = []
        # Read both canonical and historical alias prefixes to preserve backward compatibility.
        for tf_alias in _timeframe_aliases_for_ohlc(tf):
            key_prefix = f"indicators:{instrument.upper()}:{tf_alias}:"
            mode_prefixed_key_prefix = get_redis_key(key_prefix)
            prefix_candidates.append(mode_prefixed_key_prefix)
            if mode_prefixed_key_prefix != key_prefix:
                prefix_candidates.append(key_prefix)
        # Preserve order and remove duplicates.
        prefix_candidates = list(dict.fromkeys(prefix_candidates))

        indicators_dict = {}
        found_keys: List[str] = []
        active_prefix = prefix_candidates[0] if prefix_candidates else f"indicators:{instrument.upper()}:{tf}:"

        logger.info(f"🔍 Looking for indicators with prefixes: {prefix_candidates}")
        for prefix in prefix_candidates:
            candidate_keys = list(redis_client.scan_iter(match=f"{prefix}*"))
            if candidate_keys:
                found_keys = candidate_keys
                active_prefix = prefix
                break

        logger.info(f"🔍 Found {len(found_keys)} indicator keys in Redis (prefix={active_prefix})")

        for key in found_keys:
            key_str = key.decode() if isinstance(key, bytes) else str(key)
            if not key_str.startswith(active_prefix):
                continue

            indicator_name = key_str[len(active_prefix):]
            value = redis_client.get(key_str)
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

        if indicators_dict and _is_indicator_cache_suspicious(indicators_dict):
            logger.warning(
                "Detected suspicious indicator cache values for %s:%s (prefix=%s). "
                "Ignoring cache and recalculating from OHLC.",
                instrument.upper(),
                tf,
                active_prefix,
            )
            indicators_dict = {}

        if not indicators_dict:
            # Try to reconstruct indicators on-the-fly from OHLC data if available
            try:
                store = get_store()
                ohlc_bars = list(store.get_ohlc(instrument.upper(), tf, limit=200))
                if not ohlc_bars:
                    # Fallback: read directly across live/historical/paper prefixes
                    ohlc_bars = _read_ohlc_from_redis_any_mode(instrument.upper(), tf, limit=200)
                logger.warning(f"Store returned {len(ohlc_bars)} OHLC bars for {instrument.upper()}:{tf}")
                
                # If no data for requested timeframe and it's not 1m, resample from 1m data.
                if not ohlc_bars and tf != '1m':
                    logger.info(f"No {tf} data found, trying to resample from 1m data")
                    min1_bars = list(store.get_ohlc(instrument.upper(), '1m', limit=1000))  # Get more 1m bars
                    if not min1_bars:
                        min1_bars = _read_ohlc_from_redis_any_mode(instrument.upper(), '1m', limit=1000)
                    if min1_bars:
                        ohlc_bars = resample_ohlc_bars(min1_bars, tf)
                        _persist_resampled_ohlc(instrument.upper(), tf, ohlc_bars)
                        logger.info(f"Resampled {len(min1_bars)} 1m bars to {len(ohlc_bars)} {tf} bars")
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

                        # If app Redis doesn't have the data, try an alternate configured debug port.
                        alternate_port = os.getenv("REDIS_ALT_PORT")
                        if not entries:
                            try:
                                import redis as _r, json as _json
                                if not alternate_port:
                                    raise RuntimeError("REDIS_ALT_PORT not configured")
                                base_redis = redis_config(decode_responses=True)
                                alt = _r.Redis(
                                    host=os.getenv("REDIS_ALT_HOST", base_redis.get("host")),
                                    port=int(alternate_port),
                                    db=int(os.getenv("REDIS_ALT_DB", "0")),
                                    decode_responses=True,
                                )
                                alt_entries = alt.zrange(sorted_key, 0, -1)
                                logger.warning(
                                    "Alt Redis (%s) sorted set %s length: %s",
                                    alternate_port,
                                    sorted_key,
                                    len(alt_entries) if alt_entries is not None else 0,
                                )
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
                                            return _build_indicators_response(
                                                indicators_out,
                                                "alt_redis_ohlc_recalculated",
                                                bars_available=len(parsed_bars),
                                            )
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
                            return _build_indicators_response(
                                indicators_out,
                                "ohlc_recalculated",
                                bars_available=len(ohlc_bars),
                            )
                    except Exception as calc_err:
                        logger.debug(f"Failed to calculate indicators from OHLC bars: {calc_err}")
            except Exception as e:
                logger.debug(f"Failed to reconstruct indicators from OHLC data: {e}")

            return _build_indicators_response({"status": "no_data"}, "no_data", bars_available=0)

        return _build_indicators_response(indicators_dict, "redis_cache")
    except Exception as e:
        logger.error(f"Error getting technical indicators: {e}")
        return {
            "instrument": instrument.upper(),
            "timestamp": datetime.now(IST).isoformat(),
            "indicator_timestamp": None,
            "indicator_source": "error",
            "indicator_stream": "Y2",
            "indicator_update_type": "error",
            "bars_available": 0,
            "warmup_requirements": dict(INDICATOR_WARMUP_REQUIREMENTS),
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
            price_key = get_redis_key(f"price:{key_var}:latest")
            timestamp_key = get_redis_key(f"price:{key_var}:latest_ts")
            volume_key = get_redis_key(f"volume:{key_var}:latest")
            quote_key = get_redis_key(f"price:{key_var}:quote")

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

        def _depth_levels_valid(levels: Any) -> bool:
            return isinstance(levels, list) and len(levels) > 0
        
        buy_depth = None
        sell_depth = None
        timestamp = None
        
        # First, try to get depth from websocket tick data (NEW)
        tick_key = get_redis_key(f"websocket:tick:{instrument_clean}:latest")
        tick_data = redis_client.get(tick_key)
        
        if tick_data:
            import json
            tick = json.loads(tick_data)
            if 'depth' in tick and tick['depth']:
                buy_depth = tick['depth'].get('buy', [])
                sell_depth = tick['depth'].get('sell', [])
                timestamp = tick.get('timestamp')
                if not _depth_levels_valid(buy_depth) or not _depth_levels_valid(sell_depth):
                    buy_depth = None
                    sell_depth = None
        
        # Fallback: Try old format depth keys if websocket depth not found
        if buy_depth is None or sell_depth is None:
            # Try key variations
            key_variations = [
                instrument.upper(),
                instrument_clean,
                instrument_clean.replace("BANKNIFTY", "NIFTYBANK"),
                instrument_clean.replace("NIFTYBANK", "BANKNIFTY"),
            ]
            
            # Find the data
            for key_var in key_variations:
                buy_key = get_redis_key(f"depth:{key_var}:buy")
                sell_key = get_redis_key(f"depth:{key_var}:sell")
                ts_key = get_redis_key(f"depth:{key_var}:timestamp")
                
                buy_data = redis_client.get(buy_key)
                sell_data = redis_client.get(sell_key)
                ts_data = redis_client.get(ts_key)
                
                if buy_data and sell_data:
                    import json
                    parsed_buy = json.loads(buy_data)
                    parsed_sell = json.loads(sell_data)
                    if _depth_levels_valid(parsed_buy) and _depth_levels_valid(parsed_sell):
                        buy_depth = parsed_buy
                        sell_depth = parsed_sell
                        timestamp = ts_data
                        break
        
        if buy_depth is None or sell_depth is None:
            if _strict_real_only_live() and _is_live_mode():
                return {
                    "instrument": instrument.upper(),
                    "buy": [],
                    "sell": [],
                    "timestamp": None,
                    "depth_age_seconds": None,
                    "depth_is_stale": True,
                    "status": "no_data",
                    "message": "Real market depth unavailable in live mode; synthetic fallback is disabled.",
                }

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
                    buy_depth.append({'price': round(depth_mid - lvl, 2), 'quantity': qty_base * lvl, 'orders': lvl})
                    sell_depth.append({'price': round(depth_mid + lvl, 2), 'quantity': qty_base * lvl, 'orders': lvl})
                timestamp = latest_tick.timestamp.isoformat()
        elif timestamp:
            # Check if Redis depth data is recent (within last 5 minutes)
            from datetime import datetime, timedelta
            try:
                redis_time = datetime.fromisoformat(timestamp)
                mode_hint = str(get_execution_mode() or "").strip().lower()
                is_historical_mode = mode_hint == "historical"
                if (not is_historical_mode) and (datetime.now(IST) - redis_time > timedelta(minutes=5)):
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
        
        depth_stale_threshold = int(os.getenv("DEPTH_STALE_SECONDS", "120"))
        depth_age_seconds: Optional[float] = None
        depth_is_stale: bool = True
        if timestamp:
            try:
                ts = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=IST)

                mode_hint = str(get_execution_mode() or "").strip().lower()
                if mode_hint == "historical":
                    # In historical replay, freshness should be measured against replay progress,
                    # not wall-clock now. This avoids marking valid replay depth as stale.
                    store = get_store()
                    latest_tick = store.get_latest_tick(instrument.upper())
                    if latest_tick and getattr(latest_tick, "timestamp", None):
                        ref_ts = latest_tick.timestamp
                        if ref_ts.tzinfo is None:
                            ref_ts = ref_ts.replace(tzinfo=ts.tzinfo or IST)
                    else:
                        ref_ts = datetime.now(IST)
                else:
                    ref_ts = datetime.now(IST)

                depth_age_seconds = (ref_ts - ts).total_seconds()
                if depth_age_seconds < 0:
                    depth_age_seconds = 0.0
                depth_is_stale = depth_age_seconds > depth_stale_threshold
            except Exception:
                depth_age_seconds = None
                depth_is_stale = True

        # Persist whichever depth snapshot is returned (real or synthetic) so
        # mode-prefixed Redis depth keys are consistently available to consumers.
        _cache_depth_snapshot(instrument.upper(), buy_depth, sell_depth, timestamp)

        return {
            "instrument": instrument.upper(),
            "buy": buy_depth,
            "sell": sell_depth,
            "timestamp": timestamp,
            "depth_age_seconds": depth_age_seconds,
            "depth_is_stale": depth_is_stale,
            "status": "stale" if depth_is_stale else "ok",
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

