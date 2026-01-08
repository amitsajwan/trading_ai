"""FastAPI REST API service for market_data module.

This provides HTTP endpoints for:
- Market data (LTP, OHLC, ticks)
- Options chain data
- Technical indicators
- Health checks
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import redis

# Add parent directory to path for config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from config import get_config

# IST timezone for Indian financial markets
IST = timezone(timedelta(hours=5, minutes=30))

from .api import build_store
from .adapters.mock_options_chain import MockOptionsChainAdapter
from .contracts import MarketTick, OHLCBar, OptionsData, MarketStore
try:
    from .technical_indicators_service import TechnicalIndicatorsService
except ImportError:
    # Fallback if technical indicators service is not available
    TechnicalIndicatorsService = None


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


class TechnicalIndicatorsResponse(BaseModel):
    """Technical indicators response."""
    instrument: str
    timestamp: str
    indicators: Dict[str, Any]


# Lifespan handler for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources using FastAPI lifespan events."""
    try:
        print("Market Data API: Starting initialization...")
        # Startup: initialize services
        get_store()
        
        # Initialize technical indicators service with Redis
        if TechnicalIndicatorsService is not None:
            global _technical_service
            redis_client = get_redis_client()
            _technical_service = TechnicalIndicatorsService(redis_client=redis_client)
        
        # Check Redis connection
        redis_client = get_redis_client()
        redis_client.ping()
        
        # Try to initialize options client (non-blocking)
        get_options_client()
        
        print("Market Data API: Services initialized successfully")
        yield
    except Exception as e:
        print(f"Market Data API: Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        print("Market Data API: Starting cleanup...")
        # Cleanup if needed
        pass


# FastAPI app
app = FastAPI(
    title="Market Data API",
    description="REST API for market data, options chain, and technical indicators",
    version="1.0.0",
    lifespan=lifespan
)

# Global store instance (initialized on startup)
_store: Optional[MarketStore] = None
_options_client: Optional[OptionsData] = None
_redis_client: Optional[redis.Redis] = None
_technical_service: Optional[TechnicalIndicatorsService] = None


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
        
        # Determine if we're in live mode or historical mode
        # Check Redis for virtual time status (more reliable than env vars)
        is_live_mode = True  # Default to live mode
        try:
            redis_client = get_redis_client()
            virtual_time_enabled = redis_client.get("system:virtual_time:enabled")
            if virtual_time_enabled:
                # If virtual_time is enabled, we're in historical replay mode
                virtual_time_str = virtual_time_enabled.decode() if isinstance(virtual_time_enabled, bytes) else virtual_time_enabled
                if virtual_time_str == "1":
                    is_live_mode = False
        except Exception:
            # If Redis check fails, fall back to environment variable
            provider_name = os.getenv("TRADING_PROVIDER", "").lower()
            use_mock_env = os.getenv("USE_MOCK_KITE", "false").lower() in ('1', 'true', 'yes')
            is_live_mode = provider_name in ('zerodha', 'kite') and not use_mock_env
        
        # Use Zerodha Options Chain Adapter
        # For live mode: uses kite.quote() for real-time bid/ask prices
        # For historical mode: uses kite.ltp() for last traded price (works after hours)
        try:
            instrument = os.getenv("INSTRUMENT_SYMBOL", "BANKNIFTY")
            if is_live_mode:
                print(f"Market Data API: Using Zerodha Options Chain (LIVE mode - real-time quote() API) for {instrument}")
                _options_client = MockOptionsChainAdapter(kite, instrument, use_live_quotes=True)
                print(f"Market Data API: ✅ Zerodha options client initialized (LIVE - real-time quotes, no mock data)")
            else:
                print(f"Market Data API: Using Zerodha Options Chain (historical mode - ltp() API) for {instrument}")
                _options_client = MockOptionsChainAdapter(kite, instrument, use_live_quotes=False)
                print(f"Market Data API: ✅ Zerodha options client initialized (historical - last traded price)")
            return _options_client
        except Exception as e:
            print(f"Market Data API: Mock options client failed: {e}")
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
            
            instrument = "BANKNIFTY"
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
    
    # Determine overall status
    from market_data.adapters.historical_tick_replayer import IST
    status = "healthy"
    if redis_status != "healthy":
        status = "degraded"
    elif "missing" in dependencies.get("data_availability", ""):
        status = "degraded"  # Data missing - this is critical
    elif "stale" in dependencies.get("data_availability", ""):
        # Stale data is not ideal but still usable - keep as healthy but note in dependencies
        status = "healthy"  # Data exists, just not fresh - still functional
    
    return HealthResponse(
        status=status,
        module="market_data",
        timestamp=datetime.now(IST).isoformat(),
        dependencies=dependencies
    )


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


@app.get("/api/v1/market/ohlc/{instrument}", response_model=List[OHLCResponse])
async def get_ohlc(
    instrument: str,
    timeframe: str = "minute",
    limit: int = 100
):
    """Get OHLC bars for an instrument."""
    try:
        store = get_store()
        bars = list(store.get_ohlc(instrument.upper(), timeframe, limit))
        
        if not bars:
            raise HTTPException(status_code=404, detail=f"No OHLC data found for {instrument}")
        
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


@app.get("/api/v1/options/chain/{instrument}", response_model=OptionsChainResponse)
async def get_options_chain(instrument: str):
    """Get options chain for an instrument."""
    try:
        # Try to get or initialize options client
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

        return OptionsChainResponse(
            instrument=instrument.upper(),
            expiry=expiry_str,
            strikes=chain.get("strikes", []),
            timestamp=datetime.now(IST).isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/technical/indicators/{instrument}", response_model=TechnicalIndicatorsResponse)
async def get_technical_indicators(
    instrument: str,
    timeframe: str = "minute"
):
    """Get technical indicators for an instrument."""
    try:
        if TechnicalIndicatorsService is None:
            raise HTTPException(
                status_code=503,
                detail="Technical indicators service not available"
            )

        if _technical_service is None:
            raise HTTPException(
                status_code=503,
                detail="Technical indicators service not initialized"
            )

        # Try to get from Redis cache first
        redis_client = get_redis_client()
        key_prefix = f"indicators:{instrument.upper()}:"
        indicators_dict = {}
        for key in redis_client.scan_iter(match=f"{key_prefix}*"):
            indicator_name = key.replace(key_prefix, "")
            value = redis_client.get(key)
            try:
                indicators_dict[indicator_name] = float(value) if value else None
            except (ValueError, TypeError):
                indicators_dict[indicator_name] = value

        # If no cached indicators, try to calculate from OHLC data
        if not indicators_dict and _technical_service is not None:
            try:
                store = get_store()
                # Get recent OHLC bars to calculate indicators
                ohlc_bars = list(store.get_ohlc(instrument.upper(), timeframe, limit=100))
                if ohlc_bars and len(ohlc_bars) >= 20:  # Need at least 20 bars for meaningful indicators
                    # Feed OHLC data to technical service
                    for bar in ohlc_bars:
                        candle_dict = {
                            "open": bar.open,
                            "high": bar.high,
                            "low": bar.low,
                            "close": bar.close,
                            "volume": bar.volume or 0,
                            "start_at": bar.start_at.isoformat(),
                            "timestamp": bar.start_at.isoformat()
                        }
                        _technical_service.update_candle(instrument.upper(), candle_dict)
                    
                    # Get calculated indicators
                    indicators = _technical_service.get_indicators_dict(instrument.upper())
                    if indicators:
                        indicators_dict = indicators
            except Exception as e:
                logger.warning(f"Failed to calculate indicators from OHLC: {e}")
        
        if not indicators_dict:
            raise HTTPException(
                status_code=404,
                detail=f"No indicators available for {instrument}. Data may not be collected yet."
            )
        
        return TechnicalIndicatorsResponse(
            instrument=instrument.upper(),
            timestamp=datetime.now(IST).isoformat(),
            indicators=indicators_dict
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        
        # Try key variations
        key_variations = [
            instrument_clean,
            instrument_clean.replace("BANKNIFTY", "NIFTYBANK"),
            instrument_clean.replace("NIFTYBANK", "BANKNIFTY"),
        ]
        
        buy_depth = None
        sell_depth = None
        timestamp = None
        
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


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("MARKET_DATA_API_PORT", "8004"))
    host = os.getenv("MARKET_DATA_API_HOST", "0.0.0.0")
    
    print(f"Starting Market Data API on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

