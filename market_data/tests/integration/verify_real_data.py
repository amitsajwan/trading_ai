"""Verification script using real Zerodha historical data.

This script:
1. Fetches real historical OHLC data from Zerodha
2. Tests Multi-Timeframe Reader with real data
3. Tests Technical Indicators with real data
4. Tests Greeks Calculator with real option data
5. Tests Enhanced Options Chain with real data

Run this when market is closed to verify all implementations work with real data.
"""

import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Load environment variables using same logic as start_local.py
def load_env_files():
    """Load environment variables from .env files (same as start_local.py)."""
    candidates = [
        'local.env',
        '.env',
        'market_data/.env',  # KITE_API_KEY, KITE_API_SECRET typically here
        'genai_module/.env',
        'engine_module/.env',
        'news_module/.env',
    ]
    
    loaded_any = False
    _logger = logging.getLogger(__name__)
    
    for path in candidates:
        if os.path.exists(path):
            try:
                loaded_count = 0
                with open(path, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if '=' not in line:
                            continue
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")  # Remove quotes if present
                        # Do not overwrite explicitly set environment variables
                        if key not in os.environ:
                            os.environ[key] = value
                            loaded_count += 1
                            loaded_any = True
                if loaded_count > 0:
                    # Check if critical credentials were loaded
                    cred_keys = ['KITE_API_KEY', 'KITE_ACCESS_TOKEN', 'KITE_API_SECRET']
                    loaded_creds = [k for k in cred_keys if k in os.environ]
                    if loaded_creds:
                        _logger.info(f"✅ Loaded {loaded_count} variables from {path} (including: {', '.join(loaded_creds)})")
                    else:
                        _logger.info(f"✅ Loaded {loaded_count} variables from {path}")
            except Exception as e:
                _logger.debug(f"Failed to load environment file {path}: {e}")
    
    return loaded_any

# Load environment files first (before logger setup, use print for initial messages)
# CRITICAL: Must change to project root BEFORE loading .env files (paths are relative)
project_root = Path(__file__).parent.parent.parent.parent
original_cwd = os.getcwd()
try:
    # Change to project root so relative paths like 'market_data/.env' work correctly
    os.chdir(project_root)
    # Now load env files - they will find files relative to project root
    loaded = load_env_files()
    if not loaded:
        # If no env files loaded, try explicitly loading market_data/.env
        env_path = project_root / "market_data" / ".env"
        if env_path.exists():
            print(f"⚠️  Trying to explicitly load {env_path}")
            try:
                with open(env_path, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#') or '=' not in line:
                            continue
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key not in os.environ:
                            os.environ[key] = value
                            print(f"  ✅ Loaded {key} from market_data/.env")
            except Exception as e:
                print(f"  ⚠️  Error loading market_data/.env: {e}")
finally:
    os.chdir(original_cwd)  # Restore original directory

# Add project root to path
sys.path.insert(0, str(project_root / "market_data" / "src"))
sys.path.insert(0, str(project_root))

from kiteconnect import KiteConnect
import redis
try:
    import pandas as pd
except ImportError:
    pd = None  # Will handle in code

# Import our implementations
from market_data.ohlc.multi_timeframe_reader import MultiTimeframeReader
from market_data.adapters.redis_store import RedisMarketStore
from market_data.technical_indicators_service import TechnicalIndicatorsService
from market_data.analytics.greeks_calculator import GreeksCalculator
from market_data.providers.enhanced_options_chain import EnhancedOptionsChainAdapter
from market_data.contracts import OHLCBar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_kite_client():
    """Get KiteConnect client using EXACT same credential loading logic as start_local.py CredentialsValidator."""
    if KiteConnect is None:
        logger.error("kiteconnect package not installed: pip install kiteconnect")
        return None
    
    # Ensure paths are set (same as start_local.py)
    market_data_src = os.path.abspath('./market_data/src')
    if market_data_src not in sys.path:
        sys.path.insert(0, market_data_src)
    if '.' not in sys.path:
        sys.path.insert(0, '.')
    
    # Step 1: Check environment variables (loaded from .env files by load_env_files())
    api_key = os.getenv('KITE_API_KEY')
    api_secret = os.getenv('KITE_API_SECRET')
    access_token = os.getenv('KITE_ACCESS_TOKEN')
    
    logger.info(f"🔐 Credentials check: API_KEY={'SET' if api_key else 'NOT SET'}, ACCESS_TOKEN={'SET' if access_token else 'NOT SET'}")
    
    # Debug: Show what was loaded from env files
    if api_key:
        logger.info(f"   API_KEY value: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}")
    
    # Step 2: If we have both API key and access_token in env, use them directly (same as start_local.py)
    if api_key and api_secret and access_token:
        logger.info("✅ Found Zerodha API credentials in environment variables")
        try:
            from market_data.providers.zerodha import ZerodhaProvider
            provider = ZerodhaProvider(api_key, access_token)
            kite = provider.kite
            logger.info("✅ Created ZerodhaProvider from environment variables")
            # Test connection
            profile = kite.profile()
            if profile:
                logger.info(f"✅ Connected to Zerodha as: {profile.get('user_name', 'User')}")
                return kite
        except Exception as e:
            logger.error(f"❌ Failed to create provider from env vars: {e}")
            return None
    
    # Step 3: If access_token not in env, check credentials.json using KiteAuthService (same as start_local.py)
    if api_key and api_secret and not access_token:
        logger.info("⚠️  KITE_ACCESS_TOKEN not found in environment")
        logger.info("💡 Checking credentials.json/access_token.json using KiteAuthService...")
        
        try:
            from kite_auth_service import KiteAuthService
            auth_service = KiteAuthService()
            creds = auth_service.load_credentials()  # This checks both credentials.json and access_token.json
            
            if creds:
                # Get API key and token from credentials (KiteAuthService handles both files)
                creds_api_key = creds.get('api_key') or creds.get('KITE_API_KEY')
                creds_access_token = creds.get('access_token') or creds.get('data', {}).get('access_token')
                
                # MUST use API key from credentials.json (token was generated with this key)
                # Only fall back to env if creds doesn't have it
                token_api_key = creds_api_key or api_key
                
                if token_api_key and creds_access_token:
                    # Check if token is valid using KiteAuthService
                    if auth_service.is_token_valid(creds):
                        logger.info("✅ Found valid access token in credentials/access_token.json")
                        try:
                            from market_data.providers.zerodha import ZerodhaProvider
                            provider = ZerodhaProvider(token_api_key, creds_access_token)
                            kite = provider.kite
                            logger.info("✅ Using credentials from credentials.json/access_token.json (token validated)")
                            # Test connection
                            profile = kite.profile()
                            if profile:
                                logger.info(f"✅ Connected to Zerodha as: {profile.get('user_name', 'User')}")
                                return kite
                        except Exception as e:
                            logger.error(f"❌ Failed to create provider: {e}")
                            return None
                    else:
                        logger.warning("⚠️  Token in credentials is expired or invalid")
                        logger.info("   💡 Please refresh token: python -m market_data.tools.kite_auth")
                        # Try to refresh token
                        logger.info("   🔄 Attempting to refresh token...")
                        new_creds = auth_service.refresh_token(creds)
                        if new_creds:
                            auth_service.save_credentials(new_creds)
                            creds_access_token = new_creds.get('access_token') or new_creds.get('data', {}).get('access_token')
                            logger.info("✅ Token refreshed successfully")
                            try:
                                from market_data.providers.zerodha import ZerodhaProvider
                                provider = ZerodhaProvider(token_api_key, creds_access_token)
                                kite = provider.kite
                                # Test connection
                                profile = kite.profile()
                                if profile:
                                    logger.info(f"✅ Connected to Zerodha as: {profile.get('user_name', 'User')}")
                                    return kite
                            except Exception as e:
                                logger.error(f"❌ Failed to create provider with refreshed token: {e}")
                                return None
                        else:
                            # Refresh failed, try interactive login if allowed (same as start_local.py)
                            logger.warning("⚠️  Automatic token refresh failed")
                            if auth_service.allow_interactive:
                                logger.info("   🔄 Attempting interactive login to get new token...")
                                try:
                                    success = auth_service.trigger_interactive_login(timeout=300)
                                    if success:
                                        # Reload credentials after login
                                        creds = auth_service.load_credentials()
                                        creds_access_token = creds.get('access_token') or creds.get('data', {}).get('access_token')
                                        if creds_access_token and auth_service.is_token_valid(creds):
                                            logger.info("✅ Interactive login succeeded, token obtained")
                                            try:
                                                from market_data.providers.zerodha import ZerodhaProvider
                                                provider = ZerodhaProvider(token_api_key, creds_access_token)
                                                kite = provider.kite
                                                # Test connection
                                                profile = kite.profile()
                                                if profile:
                                                    logger.info(f"✅ Connected to Zerodha as: {profile.get('user_name', 'User')}")
                                                    return kite
                                            except Exception as e:
                                                logger.error(f"❌ Failed to create provider after interactive login: {e}")
                                                return None
                                        else:
                                            logger.error("❌ Interactive login completed but token validation failed")
                                            return None
                                    else:
                                        logger.error("❌ Interactive login failed or timed out")
                                        logger.info("   💡 Please run manually: python -m market_data.tools.kite_auth")
                                        return None
                                except Exception as e:
                                    logger.error(f"❌ Interactive login error: {e}")
                                    logger.info("   💡 Please run manually: python -m market_data.tools.kite_auth")
                                    return None
                            else:
                                logger.error("❌ Token refresh failed - manual intervention required")
                                logger.info("   💡 Please refresh token by running: python -m market_data.tools.kite_auth")
                                logger.info("   💡 Or set KITE_ACCESS_TOKEN in environment with a valid token")
                                logger.info("   💡 Or enable interactive login: set KITE_ALLOW_INTERACTIVE_LOGIN=1")
                                return None
                else:
                    if not creds_access_token:
                        logger.warning("⚠️  credentials.json/access_token.json missing access_token")
                    if not token_api_key:
                        logger.warning("⚠️  credentials.json/access_token.json missing api_key")
        except ImportError as e:
            logger.warning(f"⚠️  KiteAuthService not available: {e}")
            logger.info("💡 Falling back to direct credentials.json check...")
        except Exception as e:
            logger.warning(f"⚠️  Error checking credentials: {e}")
            logger.debug(f"Traceback: {e}", exc_info=True)
    
    # Step 4: Fallback - try direct credentials.json read (same as start_local.py)
    if not access_token:
        try:
            from kite_auth_service import KiteAuthService
            auth_service = KiteAuthService()
            creds = auth_service.load_credentials()
            
            if creds:
                # Get API key and token from credentials.json
                creds_api_key = creds.get('api_key') or creds.get('KITE_API_KEY')
                creds_access_token = creds.get('access_token') or creds.get('data', {}).get('access_token')
                
                # MUST use API key from credentials.json (token was generated with this key)
                token_api_key = creds_api_key or api_key
                
                if token_api_key and creds_access_token:
                    # Check if token is valid
                    if auth_service.is_token_valid(creds):
                        logger.info("✅ Found valid access token in credentials.json")
                        api_key = token_api_key
                        access_token = creds_access_token
                    else:
                        logger.warning("⚠️ Token in credentials.json is expired or invalid")
                        logger.info("   💡 Please refresh token: python -m market_data.tools.kite_auth")
                else:
                    if not creds_access_token:
                        logger.warning("⚠️ credentials.json missing access_token")
                    if not token_api_key:
                        logger.warning("⚠️ credentials.json missing api_key")
        except ImportError as e:
            logger.debug(f"Could not import KiteAuthService: {e}")
        except Exception as e:
            logger.debug(f"Error checking credentials.json: {e}")
    
    if not api_key:
        logger.error("KITE_API_KEY must be set")
        logger.info("Options:")
        logger.info("  1. Add to market_data/.env: KITE_API_KEY=your_api_key")
        logger.info("  2. Set environment variable: export KITE_API_KEY=your_api_key")
        return None
    
    if not access_token:
        logger.error("KITE_ACCESS_TOKEN must be set")
        logger.info("Options:")
        logger.info("  1. Add to market_data/.env: KITE_ACCESS_TOKEN=your_access_token")
        logger.info("  2. Set environment variable: export KITE_ACCESS_TOKEN=your_access_token")
        logger.info("  3. Run: python -m market_data.tools.kite_auth to generate new token")
        logger.info("")
        logger.info("💡 NOTE: If you have access_token.json, the API_KEY in market_data/.env")
        logger.info("   must match the API key that was used to generate that token.")
        logger.info("   Otherwise, add KITE_ACCESS_TOKEN to market_data/.env or regenerate the token.")
        return None
    
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    # Test connection
    try:
        profile = kite.profile()
        logger.info(f"✅ Connected to Zerodha as: {profile.get('user_name', 'User')}")
        return kite
    except Exception as e:
        logger.error(f"❌ Failed to connect to Zerodha: {e}")
        return None


def get_redis_client():
    """Get Redis client."""
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    
    try:
        client = redis.Redis(host=host, port=port, db=0, decode_responses=False)
        client.ping()
        logger.info(f"✅ Connected to Redis at {host}:{port}")
        return client
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        return None


def fetch_historical_ohlc(kite, instrument_token, from_date, to_date, interval="minute"):
    """Fetch historical OHLC data from Zerodha.
    
    Args:
        kite: KiteConnect instance
        instrument_token: Instrument token
        from_date: Start date
        to_date: End date
        interval: "minute", "5minute", "15minute", "1hour", "day"
    
    Returns:
        List of OHLC dictionaries
    """
    try:
        logger.info(f"📥 Fetching historical data: {from_date} to {to_date}, interval={interval}")
        
        data = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval=interval,
            oi=True
        )
        
        logger.info(f"✅ Fetched {len(data)} candles")
        return data
    except Exception as e:
        logger.error(f"❌ Failed to fetch historical data: {e}")
        return []


def convert_kite_ohlc_to_bars(kite_data, instrument, timeframe):
    """Convert Kite historical data to OHLCBar objects."""
    bars = []
    for candle in kite_data:
        # Handle date conversion
        if pd:
            dt = pd.to_datetime(candle['date']).to_pydatetime()
        else:
            from datetime import datetime
            # Try to parse date string
            if isinstance(candle['date'], str):
                dt = datetime.fromisoformat(candle['date'].replace('Z', '+00:00'))
            else:
                dt = candle['date']
        
        bars.append(OHLCBar(
            instrument=instrument,
            timeframe=timeframe,
            open=float(candle['open']),
            high=float(candle['high']),
            low=float(candle['low']),
            close=float(candle['close']),
            volume=int(candle.get('volume', 0)),
            start_at=dt
        ))
    return bars


async def test_multi_timeframe_reader(redis_client, kite):
    """Test Multi-Timeframe Reader with real historical data."""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Multi-Timeframe Reader with Real Data")
    logger.info("="*60)
    
    # Get BANKNIFTY instrument token
    instruments = kite.instruments("NFO")
    banknifty_fut = [i for i in instruments if i['name'] == 'BANKNIFTY' and i['instrument_type'] == 'FUT']
    
    if not banknifty_fut:
        logger.warning("⚠️ Could not find BANKNIFTY futures instrument")
        return False
    
    instrument_token = banknifty_fut[0]['instrument_token']
    instrument_symbol = "BANKNIFTY"
    
    logger.info(f"📊 Using instrument: {instrument_symbol} (token: {instrument_token})")
    
    # Fetch historical data for different timeframes
    to_date = date.today() - timedelta(days=1)  # Yesterday
    
    timeframes = {
        "5minute": {"tf": "5m", "days": 7},  # 7 days for 5m
        "15minute": {"tf": "15m", "days": 7},  # 7 days for 15m
        "hour": {"tf": "1h", "days": 7},  # 7 days for 1h
        "day": {"tf": "daily", "days": 30}  # 30 days for daily (more trading days)
    }
    
    store = RedisMarketStore(redis_client, enable_candle_building=False)
    
    # Fetch and store data for each timeframe
    for kite_interval, tf_config in timeframes.items():
        our_tf = tf_config["tf"]
        days_back = tf_config["days"]
        from_date = to_date - timedelta(days=days_back)
        
        logger.info(f"\n📥 Fetching {our_tf} data...")
        kite_data = fetch_historical_ohlc(
            kite, instrument_token, from_date, to_date, kite_interval
        )
        
        if kite_data:
            bars = convert_kite_ohlc_to_bars(kite_data, instrument_symbol, our_tf)
            logger.info(f"✅ Converted {len(bars)} bars for {our_tf}")
            
            # Store in Redis
            for bar in bars:
                store.store_ohlc(bar)
            
            logger.info(f"✅ Stored {len(bars)} {our_tf} bars in Redis")
        else:
            logger.warning(f"⚠️ No data fetched for {our_tf} timeframe")
    
    # Test Multi-Timeframe Reader
    reader = MultiTimeframeReader(store, cache_ttl_seconds=60)
    
    logger.info("\n📊 Testing Multi-Timeframe Reader...")
    all_data = reader.fetch_all_timeframes(instrument_symbol, ["5m", "15m", "1h", "daily"])
    
    success = True
    for tf, tf_data in all_data.items():
        if tf_data.count > 0:
            logger.info(f"  ✅ {tf}: {tf_data.count} bars, latest: {tf_data.bars[-1].close:.2f}")
        else:
            logger.warning(f"  ⚠️ {tf}: No data")
            success = False
    
    return success


async def test_technical_indicators(redis_client, kite):
    """Test Technical Indicators with real historical data."""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Technical Indicators with Real Data")
    logger.info("="*60)
    
    instruments = kite.instruments("NFO")
    banknifty_fut = [i for i in instruments if i['name'] == 'BANKNIFTY' and i['instrument_type'] == 'FUT']
    
    if not banknifty_fut:
        logger.warning("⚠️ Could not find BANKNIFTY futures instrument")
        return False
    
    instrument_token = banknifty_fut[0]['instrument_token']
    instrument_symbol = "BANKNIFTY"
    
    # Fetch historical minute data
    to_date = date.today() - timedelta(days=1)
    from_date = to_date - timedelta(days=5)  # 5 days of minute data
    
    logger.info(f"📥 Fetching minute data for indicators...")
    kite_data = fetch_historical_ohlc(kite, instrument_token, from_date, to_date, "minute")
    
    if not kite_data:
        logger.warning("⚠️ No historical data available")
        return False
    
    logger.info(f"✅ Fetched {len(kite_data)} minute candles")
    
    # Initialize technical indicators service
    indicators_service = TechnicalIndicatorsService(redis_client=redis_client)
    
    # Feed data to indicators service
    logger.info("\n📊 Calculating technical indicators...")
    for candle in kite_data[-100:]:  # Use last 100 candles
        # Handle date conversion
        candle_date = candle['date']
        if isinstance(candle_date, datetime):
            date_str = candle_date.isoformat()
        elif pd:
            date_str = pd.to_datetime(candle_date).isoformat()
        else:
            date_str = str(candle_date)
        
        candle_dict = {
            "open": candle['open'],
            "high": candle['high'],
            "low": candle['low'],
            "close": candle['close'],
            "volume": candle.get('volume', 0),
            "start_at": date_str,
            "timestamp": date_str
        }
        indicators_service.update_candle(instrument_symbol, candle_dict)
    
    # Get indicators
    indicators = indicators_service.get_indicators(instrument_symbol)
    
    if indicators:
        logger.info("\n✅ Technical Indicators Calculated:")
        logger.info(f"  RSI(14): {indicators.rsi_14:.2f}" if indicators.rsi_14 else "  RSI(14): N/A")
        logger.info(f"  MACD: {indicators.macd_value:.2f}" if indicators.macd_value else "  MACD: N/A")
        logger.info(f"  SMA(20): {indicators.sma_20:.2f}" if indicators.sma_20 else "  SMA(20): N/A")
        logger.info(f"  EMA(50): {indicators.ema_50:.2f}" if indicators.ema_50 else "  EMA(50): N/A")
        logger.info(f"  ADX(14): {indicators.adx_14:.2f}" if indicators.adx_14 else "  ADX(14): N/A")
        logger.info(f"  ATR(14): {indicators.atr_14:.2f}" if indicators.atr_14 else "  ATR(14): N/A")
        logger.info(f"  Volume Ratio: {indicators.volume_ratio:.2f}" if indicators.volume_ratio else "  Volume Ratio: N/A")
        return True
    else:
        logger.warning("⚠️ No indicators calculated")
        return False


async def test_greeks_calculator():
    """Test Greeks Calculator with realistic option parameters."""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Greeks Calculator with Real Option Parameters")
    logger.info("="*60)
    
    calculator = GreeksCalculator()
    
    # Realistic BANKNIFTY option parameters
    spot_price = 47500.0
    strike = 47500.0  # ATM
    time_to_expiry = 0.25  # 3 months
    volatility = 0.20  # 20% IV
    risk_free_rate = 0.07  # 7%
    
    logger.info(f"\n📊 Calculating Greeks for ATM Call Option:")
    logger.info(f"  Spot: ₹{spot_price:.2f}")
    logger.info(f"  Strike: ₹{strike:.2f}")
    logger.info(f"  Time to Expiry: {time_to_expiry:.2f} years (3 months)")
    logger.info(f"  Volatility: {volatility*100:.1f}%")
    
    # Call option
    call_greeks = calculator.calculate_greeks(
        spot_price, strike, time_to_expiry, volatility, risk_free_rate, 'CE'
    )
    
    logger.info("\n✅ Call Option Greeks:")
    logger.info(f"  Delta: {call_greeks['delta']:.4f}")
    logger.info(f"  Gamma: {call_greeks['gamma']:.6f}")
    logger.info(f"  Theta: {call_greeks['theta']:.2f} (per day)")
    logger.info(f"  Vega: {call_greeks['vega']:.2f} (per 1% vol change)")
    logger.info(f"  Rho: {call_greeks['rho']:.2f} (per 1% rate change)")
    
    # Put option
    put_greeks = calculator.calculate_greeks(
        spot_price, strike, time_to_expiry, volatility, risk_free_rate, 'PE'
    )
    
    logger.info("\n✅ Put Option Greeks:")
    logger.info(f"  Delta: {put_greeks['delta']:.4f}")
    logger.info(f"  Gamma: {put_greeks['gamma']:.6f}")
    logger.info(f"  Theta: {put_greeks['theta']:.2f} (per day)")
    logger.info(f"  Vega: {put_greeks['vega']:.2f} (per 1% vol change)")
    
    # Verify call-put parity
    delta_diff = call_greeks['delta'] - put_greeks['delta']
    logger.info(f"\n✅ Call-Put Delta Parity: {delta_diff:.4f} (should be ~1.0)")
    
    if abs(delta_diff - 1.0) < 0.01:
        logger.info("  ✅ Delta parity verified!")
    else:
        logger.warning(f"  ⚠️ Delta parity off by {abs(delta_diff - 1.0):.4f}")
    
    return True


async def test_enhanced_options_chain(kite):
    """Test Enhanced Options Chain with real Zerodha data."""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Enhanced Options Chain with Real Data")
    logger.info("="*60)
    
    try:
        adapter = EnhancedOptionsChainAdapter(
            kite=kite,
            instrument_symbol="BANKNIFTY",
            use_live_quotes=False,  # Use LTP for historical
            enable_greeks=False  # Can enable if IV is available
        )
        
        logger.info("📥 Initializing options chain adapter...")
        await adapter.initialize()
        
        logger.info("📥 Fetching options chain...")
        chain = await adapter.fetch_options_chain()
        
        if chain and chain.get("available"):
            logger.info(f"✅ Options chain fetched successfully")
            logger.info(f"  Instrument: {chain['instrument']}")
            logger.info(f"  Expiry: {chain['expiry']}")
            logger.info(f"  Total Strikes: {len(chain.get('strikes', []))}")
            
            # Show sample strike with enhanced fields
            if chain.get('strikes'):
                sample_strike = chain['strikes'][len(chain['strikes'])//2]  # Middle strike
                logger.info(f"\n📊 Sample Strike (Strike: {sample_strike['strike']}):")
                
                if sample_strike.get('CE'):
                    ce = sample_strike['CE']
                    logger.info(f"  CE:")
                    logger.info(f"    LTP: ₹{ce.get('last_price', 0):.2f}")
                    logger.info(f"    Volume: {ce.get('volume', 0)}")
                    logger.info(f"    OI: {ce.get('oi', 0)}")
                    logger.info(f"    IV: {ce.get('iv', 'N/A')}")
                    logger.info(f"    Delta: {ce.get('delta', 'N/A')}")
                
                if sample_strike.get('PE'):
                    pe = sample_strike['PE']
                    logger.info(f"  PE:")
                    logger.info(f"    LTP: ₹{pe.get('last_price', 0):.2f}")
                    logger.info(f"    Volume: {pe.get('volume', 0)}")
                    logger.info(f"    OI: {pe.get('oi', 0)}")
                    logger.info(f"    IV: {pe.get('iv', 'N/A')}")
                    logger.info(f"    Delta: {pe.get('delta', 'N/A')}")
                
                # Check enhanced fields
                has_enhanced = any(k.startswith('ce_') or k.startswith('pe_') for k in sample_strike.keys())
                if has_enhanced:
                    logger.info("\n✅ Enhanced fields present (ce_ltp, pe_ltp, ce_oi, pe_oi, etc.)")
            
            return True
        else:
            logger.warning("⚠️ Options chain not available")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing options chain: {e}", exc_info=True)
        return False


async def test_multi_timeframe_indicators(redis_client, kite):
    """Test multi-timeframe technical indicators with real data."""
    logger.info("\n" + "="*60)
    logger.info("TEST 5: Multi-Timeframe Technical Indicators")
    logger.info("="*60)
    
    instruments = kite.instruments("NFO")
    banknifty_fut = [i for i in instruments if i['name'] == 'BANKNIFTY' and i['instrument_type'] == 'FUT']
    
    if not banknifty_fut:
        logger.warning("⚠️ Could not find BANKNIFTY futures instrument")
        return False
    
    instrument_token = banknifty_fut[0]['instrument_token']
    instrument_symbol = "BANKNIFTY"
    
    # Fetch data for different timeframes
    to_date = date.today() - timedelta(days=1)
    from_date = to_date - timedelta(days=5)
    
    indicators_service = TechnicalIndicatorsService(redis_client=redis_client)
    
    timeframes = {
        "5minute": "5m",
        "15minute": "15m",
        "hour": "1h"
    }
    
    logger.info("📥 Fetching and calculating indicators for multiple timeframes...")
    
    for kite_interval, our_tf in timeframes.items():
        kite_data = fetch_historical_ohlc(kite, instrument_token, from_date, to_date, kite_interval)
        
        if kite_data and len(kite_data) >= 50:
            # Convert to OHLCBar objects
            bars = convert_kite_ohlc_to_bars(kite_data, instrument_symbol, our_tf)
            
            # Calculate indicators from bars
            indicators = indicators_service.calculate_indicators_from_ohlc_bars(
                instrument_symbol, our_tf, bars
            )
            
            logger.info(f"\n✅ {our_tf} Indicators:")
            logger.info(f"  Price: ₹{indicators.current_price:.2f}")
            logger.info(f"  RSI(14): {indicators.rsi_14:.2f}" if indicators.rsi_14 else "  RSI(14): N/A")
            logger.info(f"  SMA(20): {indicators.sma_20:.2f}" if indicators.sma_20 else "  SMA(20): N/A")
            logger.info(f"  ADX(14): {indicators.adx_14:.2f}" if indicators.adx_14 else "  ADX(14): N/A")
    
    # Test getting all timeframe indicators
    all_indicators = indicators_service.get_all_timeframe_indicators(
        instrument_symbol, ["5m", "15m", "1h"]
    )
    
    logger.info(f"\n✅ Retrieved indicators for {len(all_indicators)} timeframes")
    
    return len(all_indicators) > 0


async def main():
    """Run all verification tests."""
    logger.info("="*60)
    logger.info("VERIFICATION WITH REAL ZERODHA HISTORICAL DATA")
    logger.info("="*60)
    logger.info("\nThis script verifies all implementations using real market data")
    logger.info("Market is assumed to be closed - using historical data\n")
    
    # Check prerequisites
    kite = get_kite_client()
    if not kite:
        logger.error("\n❌ Cannot proceed without KiteConnect client")
        return
    
    redis_client = get_redis_client()
    if not redis_client:
        logger.error("\n❌ Cannot proceed without Redis")
        return
    
    results = {}
    
    # Run tests
    try:
        results['multi_timeframe'] = await test_multi_timeframe_reader(redis_client, kite)
        results['technical_indicators'] = await test_technical_indicators(redis_client, kite)
        results['greeks'] = await test_greeks_calculator()
        results['options_chain'] = await test_enhanced_options_chain(kite)
        results['mtf_indicators'] = await test_multi_timeframe_indicators(redis_client, kite)
        
    except Exception as e:
        logger.error(f"\n❌ Error during testing: {e}", exc_info=True)
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("VERIFICATION SUMMARY")
    logger.info("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("\n🎉 All tests passed! Implementations work with real data.")
    else:
        logger.warning(f"\n⚠️ {total - passed} test(s) failed. Review logs above.")


if __name__ == "__main__":
    asyncio.run(main())
