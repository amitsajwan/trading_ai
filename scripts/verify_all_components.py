"""Comprehensive component verification before starting system."""
import sys
import os

# Immediate output to show script started
print("=" * 70, flush=True)
print("VERIFICATION SCRIPT STARTED", flush=True)
print("=" * 70, flush=True)

import asyncio
import json
from pathlib import Path
from datetime import datetime

# Fix Windows encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

print("   Setting up paths...", flush=True)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Suppress verbose logging during verification
print("   Configuring logging...", flush=True)
import logging
logging.basicConfig(level=logging.WARNING)
print("   Imports complete, starting verification...", flush=True)

class ComponentVerifier:
    """Verify each component individually."""
    
    def __init__(self):
        self.results = {}
        self.notes = []
    
    def add_note(self, component: str, status: str, message: str, details: str = ""):
        """Add a verification note."""
        self.notes.append({
            "component": component,
            "status": status,  # PASS, FAIL, WARNING
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        self.results[component] = status
    
    def verify_mongodb(self):
        """Verify MongoDB connection and collections."""
        try:
            from mongodb_schema import get_mongo_client, get_collection
            from config.settings import settings
            
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            
            # Test connection
            client.server_info()
            self.add_note("MongoDB", "PASS", "MongoDB connection successful")
            
            # Check collections exist
            collections = db.list_collection_names()
            required_collections = ["agent_decisions", "trades_executed", "ohlc_history"]
            missing = [c for c in required_collections if c not in collections]
            
            if missing:
                self.add_note("MongoDB Collections", "WARNING", 
                            f"Some collections missing: {', '.join(missing)}",
                            "Collections will be created automatically when needed")
            else:
                self.add_note("MongoDB Collections", "PASS", 
                            "All required collections exist")
            
            return True
        except Exception as e:
            self.add_note("MongoDB", "FAIL", f"MongoDB connection failed: {str(e)[:100]}")
            return False
    
    def verify_redis(self):
        """Verify Redis connection."""
        try:
            import redis
            from config.settings import settings
            
            r = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            r.ping()
            self.add_note("Redis", "PASS", "Redis connection successful")
            return True
        except Exception as e:
            self.add_note("Redis", "WARNING", f"Redis not accessible: {str(e)[:50]}",
                         "System can work without Redis, but performance may be reduced")
            return False
    
    def verify_llm_provider(self):
        """Verify LLM provider is accessible."""
        try:
            from config.settings import settings
            
            provider = settings.llm_provider.lower()
            
            # Handle "multi" provider - check Ollama first since it's local and preferred
            if provider == "multi":
                # Check Ollama first (local, free, preferred)
                import httpx
                base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
                try:
                    response = httpx.get(f'{base_url}/api/tags', timeout=1.0)  # Fast timeout
                    if response.status_code == 200:
                        models = response.json().get('models', [])
                        if models:
                            self.add_note("LLM Provider (Multi - Ollama)", "PASS", 
                                        f"Multi-provider mode: Ollama available with {len(models)} model(s)",
                                        f"Ollama will be used first. Models: {', '.join([m.get('name', 'unknown') for m in models[:3]])}")
                            return True
                        else:
                            self.add_note("LLM Provider (Multi - Ollama)", "WARNING", 
                                        "Multi-provider mode: Ollama running but no models found",
                                        "Run: ollama pull llama3.1:8b. System will fallback to cloud providers.")
                            return True  # Allow to continue, will use cloud fallback
                    else:
                        self.add_note("LLM Provider (Multi - Ollama)", "WARNING", 
                                    f"Multi-provider mode: Ollama returned status {response.status_code}",
                                    "System will fallback to cloud providers if configured.")
                        return True  # Allow to continue, will use cloud fallback
                except Exception as e:
                    self.add_note("LLM Provider (Multi - Ollama)", "WARNING", 
                                f"Multi-provider mode: Ollama not accessible: {str(e)[:50]}",
                                "System will fallback to cloud providers if configured.")
                    return True  # Allow to continue, will use cloud fallback
            
            if provider == "ollama":
                import httpx
                base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
                response = httpx.get(f'{base_url}/api/tags', timeout=1.0)  # Fast timeout
                if response.status_code == 200:
                    models = response.json().get('models', [])
                    if models:
                        self.add_note("LLM Provider (Ollama)", "PASS", 
                                    f"Ollama running with {len(models)} model(s)",
                                    f"Models: {', '.join([m.get('name', 'unknown') for m in models[:3]])}")
                        return True
                    else:
                        self.add_note("LLM Provider (Ollama)", "FAIL", 
                                    "Ollama running but no models found",
                                    "Run: ollama pull llama3.1:8b")
                        return False
                else:
                    self.add_note("LLM Provider (Ollama)", "FAIL", 
                                f"Ollama returned status {response.status_code}")
                    return False
            else:
                # Cloud provider - check API key exists
                api_keys = {
                    'groq': 'GROQ_API_KEY',
                    'gemini': 'GOOGLE_API_KEY',
                    'google': 'GOOGLE_API_KEY',
                    'openai': 'OPENAI_API_KEY',
                    'together': 'TOGETHER_API_KEY',
                    'openrouter': 'OPENROUTER_API_KEY',
                }
                key_name = api_keys.get(provider, '')
                if not key_name:
                    # Unknown provider
                    self.add_note("LLM Provider (Cloud)", "FAIL", 
                                f"Unknown LLM provider: {provider}",
                                f"Supported providers: {', '.join(api_keys.keys())}, or 'ollama'")
                    return False
                elif os.getenv(key_name):
                    self.add_note("LLM Provider (Cloud)", "PASS", 
                                f"{provider} API key configured",
                                "Note: Actual API call will be tested during agent verification")
                    return True
                else:
                    self.add_note("LLM Provider (Cloud)", "FAIL", 
                                f"{provider} API key not found",
                                f"Set {key_name} in .env file")
                    return False
        except ImportError as e:
            self.add_note("LLM Provider", "FAIL", f"Required module missing: {str(e)[:50]}")
            return False
        except Exception as e:
            self.add_note("LLM Provider", "FAIL", f"LLM provider check failed: {str(e)[:100]}")
            return False
    
    def verify_market_data(self):
        """Verify market data is available."""
        try:
            from data.market_memory import MarketMemory
            from config.settings import settings
            import pandas as pd
            
            mm = MarketMemory()
            key = settings.instrument_symbol.replace('-', '').replace(' ', '').upper()
            
            price = mm.get_current_price(key)
            ohlc_1min = mm.get_recent_ohlc(key, '1min', 5)
            ohlc_5min = mm.get_recent_ohlc(key, '5min', 5)
            
            if price and price > 0:
                self.add_note("Market Data (Price)", "PASS", 
                            f"Current price available: ${price:,.2f}")
            else:
                self.add_note("Market Data (Price)", "WARNING", 
                            "No current price available",
                            "Data feed may need time to populate")
            
            # Check OHLC data format
            ohlc_to_check = ohlc_5min if ohlc_5min else ohlc_1min
            if ohlc_to_check and len(ohlc_to_check) > 0:
                # Check data format
                sample = ohlc_to_check[0]
                required_cols = ['open', 'high', 'low', 'close']
                missing_cols = [col for col in required_cols if col not in sample]
                
                if missing_cols:
                    self.add_note("Market Data (OHLC Format)", "FAIL",
                                f"OHLC data missing required columns: {missing_cols}",
                                f"Available columns: {list(sample.keys())}. Data feed may need fixing.")
                else:
                    # Try to convert to DataFrame to verify
                    try:
                        df = pd.DataFrame(ohlc_to_check)
                        for col in required_cols:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                        if df[required_cols].isna().any().any():
                            self.add_note("Market Data (OHLC Format)", "WARNING",
                                        "Some OHLC values are not numeric",
                                        "Technical indicators may fail")
                        else:
                            self.add_note("Market Data (OHLC Format)", "PASS",
                                        "OHLC data format is valid",
                                        f"Sample: O={sample.get('open')}, H={sample.get('high')}, L={sample.get('low')}, C={sample.get('close')}")
                    except Exception as e:
                        self.add_note("Market Data (OHLC Format)", "WARNING",
                                    f"Could not validate OHLC format: {str(e)[:50]}",
                                    "Technical indicators may fail")
            
            if ohlc_1min and len(ohlc_1min) > 0:
                self.add_note("Market Data (OHLC 1min)", "PASS", 
                            f"{len(ohlc_1min)} 1-minute candles available")
            else:
                self.add_note("Market Data (OHLC 1min)", "WARNING", 
                            "No 1-minute OHLC data",
                            "Agents need OHLC data for technical analysis")
            
            if ohlc_5min and len(ohlc_5min) > 0:
                self.add_note("Market Data (OHLC 5min)", "PASS", 
                            f"{len(ohlc_5min)} 5-minute candles available")
            else:
                self.add_note("Market Data (OHLC 5min)", "WARNING", 
                            "No 5-minute OHLC data",
                            "Some analysis may be limited")
            
            return price is not None and price > 0
        except Exception as e:
            self.add_note("Market Data", "FAIL", f"Market data check failed: {str(e)[:100]}")
            return False
    
    def verify_data_feed(self, instrument: str):
        """Verify data feed connectivity."""
        try:
            if instrument == "BTC":
                import httpx
                response = httpx.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    price = float(data.get('price', 0))
                    self.add_note("Data Feed (Binance)", "PASS", 
                                f"Binance API accessible (BTC: ${price:,.2f})")
                    return True
                else:
                    self.add_note("Data Feed (Binance)", "FAIL", 
                                f"Binance API returned status {response.status_code}")
                    return False
            else:
                # Zerodha
                cred_path = Path(__file__).parent.parent / "credentials.json"
                if not cred_path.exists():
                    self.add_note("Data Feed (Zerodha)", "FAIL", 
                                "credentials.json not found",
                                "Run: python auto_login.py")
                    return False
                
                with open(cred_path) as f:
                    creds = json.load(f)
                
                if not creds.get("access_token"):
                    self.add_note("Data Feed (Zerodha)", "FAIL", 
                                "Access token missing",
                                "Run: python auto_login.py")
                    return False
                
                from kiteconnect import KiteConnect
                kite = KiteConnect(api_key=creds["api_key"])
                kite.set_access_token(creds["access_token"])
                profile = kite.profile()
                self.add_note("Data Feed (Zerodha)", "PASS", 
                            f"Zerodha credentials valid (User: {profile.get('user_name', 'Unknown')})")
                return True
        except Exception as e:
            self.add_note("Data Feed", "FAIL", f"Data feed check failed: {str(e)[:100]}")
            return False
    
    async def verify_agents(self):
        """Verify agents can produce meaningful analysis."""
        try:
            from trading_orchestration.trading_graph import TradingGraph
            from data.market_memory import MarketMemory
            from config.settings import settings
            
            print("   Initializing trading graph...", flush=True)
            market_memory = MarketMemory()
            print("   MarketMemory initialized", flush=True)
            kite = None
            
            if settings.instrument_exchange != "CRYPTO":
                try:
                    from kiteconnect import KiteConnect
                    cred_path = Path(__file__).parent.parent / "credentials.json"
                    if cred_path.exists():
                        with open(cred_path) as f:
                            creds = json.load(f)
                        kite = KiteConnect(api_key=creds.get("api_key"))
                        kite.set_access_token(creds.get("access_token"))
                except Exception:
                    pass
            
            print("   Creating TradingGraph (this initializes LLM providers)...", flush=True)
            trading_graph = TradingGraph(kite=kite, market_memory=market_memory)
            print("   TradingGraph created successfully", flush=True)
            self.add_note("Trading Graph", "PASS", "Trading graph initialized successfully")
            
            # Temporarily enable INFO logging to see agent progress
            graph_logger = logging.getLogger("trading_orchestration.trading_graph")
            agent_logger = logging.getLogger("agents.base_agent")
            original_graph_level = graph_logger.level
            original_agent_level = agent_logger.level
            graph_logger.setLevel(logging.INFO)
            agent_logger.setLevel(logging.INFO)
            
            # Check which LLM provider is being used
            from agents.llm_provider_manager import get_llm_manager
            llm_manager = get_llm_manager()
            current_provider = llm_manager.current_provider
            
            print("   Running single analysis cycle (30-60 seconds)...", flush=True)
            if current_provider:
                # Get model from provider config
                provider_config = llm_manager.providers.get(current_provider)
                model_name = provider_config.model if provider_config else "unknown"
                print(f"   Using LLM provider: {current_provider} (model: {model_name})", flush=True)
                if current_provider == "ollama":
                    print("   ⚠️  Note: Ollama's first call can take 30-60s (model loading).", flush=True)
                    print("   ⚠️  Warning: Ollama handles parallel requests poorly - 4 parallel calls may hang.", flush=True)
                    print("   💡 Tip: If this hangs, try a faster model: ollama pull llama3.2:3b", flush=True)
                    print("   💡 Or use cloud provider (Groq/Gemini) for faster verification.", flush=True)
                print("   Note: 4 agents run in parallel, each making LLM calls...", flush=True)
            else:
                print("   ⚠️  Warning: No LLM provider selected!", flush=True)
            
            # Track which agent is currently running
            current_agent = [None]
            agent_start_time = [None]
            
            # Add progress monitoring with agent tracking
            async def run_with_progress():
                import time
                start_time = time.time()
                last_update_time = start_time
                last_agent_log = None
                
                # Create a task that will run the graph
                task = asyncio.create_task(trading_graph.arun())
                
                # Monitor progress every 10 seconds
                while not task.done():
                    await asyncio.sleep(5)  # Check every 5 seconds
                    elapsed = time.time() - start_time
                    time_since_last_update = time.time() - last_update_time
                    
                    # Check if we're stuck on the same agent for too long
                    if current_agent[0] and agent_start_time[0]:
                        agent_elapsed = time.time() - agent_start_time[0]
                        if agent_elapsed > 60:  # More than 60 seconds on one agent
                            print(f"   ⚠️  Agent '{current_agent[0]}' has been running for {int(agent_elapsed)}s - may be hanging on LLM call", flush=True)
                    
                    if time_since_last_update >= 10:  # Every 10 seconds
                        agent_info = f" (on agent: {current_agent[0]})" if current_agent[0] else ""
                        print(f"   ... still running ({int(elapsed)}s elapsed){agent_info}...", flush=True)
                        last_update_time = time.time()
                    
                    # If it's been more than 90 seconds, warn
                    if elapsed > 90:
                        print(f"   ⚠️  Taking longer than expected ({int(elapsed)}s)...", flush=True)
                        print(f"   💡 Tip: Check if LLM provider is responding. Ollama may need more time for first call.", flush=True)
                
                return await task
            
            try:
                result = await asyncio.wait_for(
                    run_with_progress(),
                    timeout=120.0
                )
                print("   ✅ Analysis cycle completed", flush=True)
            except asyncio.TimeoutError:
                print("   ❌ Analysis cycle timed out after 2 minutes", flush=True)
                raise
            finally:
                # Restore original logging levels
                graph_logger.setLevel(original_graph_level)
                agent_logger.setLevel(original_agent_level)
            
            # Debug: Check what technical agent actually produced
            if hasattr(result, 'technical_analysis'):
                tech_analysis = result.technical_analysis
                if isinstance(tech_analysis, dict):
                    calculated = {k: tech_analysis[k] for k in ['rsi', 'macd', 'atr', 'support_level', 'resistance_level', 'trend_direction'] 
                                 if k in tech_analysis and tech_analysis[k] is not None}
                    patterns = {k: tech_analysis[k] for k in ['reversal_pattern', 'continuation_pattern', 'candlestick_pattern'] 
                               if k in tech_analysis}
                    empty_patterns = [k for k, v in patterns.items() if v is None]
                    
                    if calculated:
                        self.add_note("Agent Debug (technical)", "INFO", 
                                    f"✅ Calculated indicators present: {list(calculated.keys())}",
                                    f"Sample values: RSI={calculated.get('rsi', 'N/A')}, Trend={calculated.get('trend_direction', 'N/A')}")
                    else:
                        self.add_note("Agent Debug (technical)", "FAIL", 
                                    "❌ No calculated indicators found",
                                    "Technical agent failed to calculate RSI/MACD/ATR. Check OHLC data format.")
                    
                    if empty_patterns:
                        self.add_note("Agent Debug (technical)", "WARNING", 
                                    f"⚠️ LLM pattern fields are None: {', '.join(empty_patterns)}",
                                    "LLM pattern recognition call likely failed. Check LLM logs for errors.")
            
            # Check results in MongoDB
            from mongodb_schema import get_mongo_client, get_collection
            mongo_client = get_mongo_client()
            db = mongo_client[settings.mongodb_db_name]
            analysis_collection = get_collection(db, "agent_decisions")
            latest = analysis_collection.find_one(sort=[("timestamp", -1)])
            
            if not latest:
                self.add_note("Agent Analysis", "FAIL", 
                            "Analysis completed but no results stored",
                            "Check MongoDB write permissions")
                return False
            
            agent_decisions = latest.get("agent_decisions", {})
            required_agents = ['technical', 'fundamental', 'sentiment', 'macro']
            
            agent_status = {}
            for agent_name in required_agents:
                if agent_name not in agent_decisions:
                    agent_status[agent_name] = "MISSING"
                else:
                    agent_data = agent_decisions[agent_name]
                    if isinstance(agent_data, dict):
                        non_empty = [v for v in agent_data.values() 
                                   if v is not None and v != "" and v != False]
                        if non_empty:
                            agent_status[agent_name] = "OK"
                        else:
                            agent_status[agent_name] = "EMPTY"
                    elif isinstance(agent_data, str) and agent_data.strip():
                        agent_status[agent_name] = "OK"
                    else:
                        agent_status[agent_name] = "EMPTY"
            
            # Report on each agent with detailed analysis
            all_ok = True
            for agent_name, status in agent_status.items():
                if status == "OK":
                    agent_data = agent_decisions.get(agent_name, {})
                    # Count meaningful fields
                    if isinstance(agent_data, dict):
                        meaningful_fields = [k for k, v in agent_data.items() 
                                           if v is not None and v != "" and v != False]
                        self.add_note(f"Agent ({agent_name})", "PASS", 
                                    f"{agent_name.capitalize()} agent producing analysis",
                                    f"Has {len(meaningful_fields)} meaningful fields: {', '.join(meaningful_fields[:5])}")
                    else:
                        self.add_note(f"Agent ({agent_name})", "PASS", 
                                    f"{agent_name.capitalize()} agent producing analysis")
                elif status == "EMPTY":
                    agent_data = agent_decisions.get(agent_name, {})
                    if isinstance(agent_data, dict):
                        empty_fields = list(agent_data.keys())
                        # Check if calculated indicators are present (for technical agent)
                        calculated_fields = ['rsi', 'macd', 'atr', 'support_level', 'resistance_level', 'trend_direction']
                        has_calculated = any(k in agent_data for k in calculated_fields)
                        
                        if agent_name == "technical":
                            # For technical agent, check what's actually there
                            actual_values = {k: v for k, v in agent_data.items() if v is not None and v != "" and v != False}
                            if has_calculated and actual_values:
                                # Has calculated indicators but LLM patterns are empty
                                self.add_note(f"Agent ({agent_name})", "WARNING", 
                                            f"{agent_name.capitalize()} agent: Calculated indicators present but LLM patterns empty",
                                            f"LLM pattern recognition failed. Calculated fields: {list(actual_values.keys())}. Missing: {', '.join([f for f in empty_fields if f not in actual_values])}")
                            else:
                                # No calculated indicators either - this is a FAILURE
                                self.add_note(f"Agent ({agent_name})", "FAIL", 
                                            f"{agent_name.capitalize()} agent producing completely empty analysis",
                                            f"All {len(empty_fields)} fields are empty/None. Check: 1) OHLC data available? 2) LLM responding? 3) Parsing working?")
                                all_ok = False
                        else:
                            self.add_note(f"Agent ({agent_name})", "FAIL", 
                                        f"{agent_name.capitalize()} agent producing empty analysis",
                                        f"All {len(empty_fields)} fields are empty/None. LLM may not be responding properly or parsing may be failing")
                        all_ok = False
                    else:
                        self.add_note(f"Agent ({agent_name})", "FAIL", 
                                    f"{agent_name.capitalize()} agent producing empty analysis",
                                    "LLM may not be responding properly or parsing may be failing")
                        all_ok = False
                else:
                    self.add_note(f"Agent ({agent_name})", "FAIL", 
                                f"{agent_name.capitalize()} agent missing from results",
                                "Agent did not execute or results were not stored")
                    all_ok = False
            
            # Check additional agents (bull, bear, portfolio_manager)
            for agent_name in ['bull', 'bear', 'portfolio_manager']:
                if agent_name in agent_decisions:
                    agent_data = agent_decisions[agent_name]
                    if isinstance(agent_data, dict):
                        if agent_name == 'portfolio_manager':
                            signal = agent_data.get('signal', 'UNKNOWN')
                            bullish = agent_data.get('bullish_score')
                            bearish = agent_data.get('bearish_score')
                            self.add_note(f"Agent ({agent_name})", "PASS", 
                                        f"Portfolio manager producing decisions",
                                        f"Signal: {signal}, Bullish: {bullish}, Bearish: {bearish}")
                        else:
                            thesis = agent_data.get('thesis', '')
                            confidence = agent_data.get('confidence', 0)
                            if thesis:
                                self.add_note(f"Agent ({agent_name})", "PASS", 
                                            f"{agent_name.capitalize()} researcher producing thesis",
                                            f"Confidence: {confidence}")
                            else:
                                self.add_note(f"Agent ({agent_name})", "WARNING", 
                                            f"{agent_name.capitalize()} researcher has empty thesis")
                                all_ok = False
            
            signal = latest.get("final_signal", "UNKNOWN")
            
            # Determine overall status based on what actually failed
            empty_count = sum(1 for s in agent_status.values() if s == 'EMPTY')
            missing_count = sum(1 for s in agent_status.values() if s == 'MISSING')
            
            # Check if technical agent has calculated indicators even if patterns are empty
            tech_status = agent_status.get('technical')
            tech_has_calculated = False
            if tech_status == 'EMPTY':
                tech_data = agent_decisions.get('technical', {})
                if isinstance(tech_data, dict):
                    tech_has_calculated = any(k in tech_data and tech_data[k] is not None 
                                             for k in ['rsi', 'macd', 'atr', 'trend_direction'])
            
            if missing_count > 0:
                overall_status = "FAIL"
                overall_msg = f"Analysis cycle completed but {missing_count} agent(s) missing"
            elif empty_count > 0 and not (tech_status == 'EMPTY' and tech_has_calculated):
                # If agents are empty AND technical doesn't have calculated indicators, it's a failure
                overall_status = "FAIL"
                overall_msg = f"Analysis cycle completed but {empty_count} agent(s) producing empty analysis"
            elif empty_count > 0:
                # Technical has calculated indicators but LLM patterns failed - warning
                overall_status = "WARNING"
                overall_msg = f"Analysis cycle completed (Signal: {signal}) - LLM patterns missing but calculated indicators present"
            else:
                overall_status = "PASS"
                overall_msg = f"Analysis cycle completed successfully (Signal: {signal})"
            
            self.add_note("Agent Analysis (Overall)", overall_status,
                         overall_msg,
                         f"Agents checked: {len(agent_status)}, Empty: {empty_count}, Missing: {missing_count}")
            
            # Return False if overall status is FAIL, otherwise return all_ok
            if overall_status == "FAIL":
                return False
            return all_ok
        except asyncio.TimeoutError:
            self.add_note("Agent Analysis", "FAIL", 
                        "Agent analysis timed out after 2 minutes",
                        "LLM calls may be hanging - check LLM provider")
            return False
        except Exception as e:
            self.add_note("Agent Analysis", "FAIL", 
                        f"Agent verification failed: {str(e)[:100]}",
                        f"Full error: {str(e)[:300]}")
            return False
    
    def print_report(self):
        """Print comprehensive verification report."""
        print("\n" + "=" * 70)
        print("COMPREHENSIVE COMPONENT VERIFICATION REPORT")
        print("=" * 70)
        print()
        
        # Group by status
        passed = [n for n in self.notes if n["status"] == "PASS"]
        warnings = [n for n in self.notes if n["status"] == "WARNING"]
        failed = [n for n in self.notes if n["status"] == "FAIL"]
        
        print(f"✅ PASSED: {len(passed)}")
        print(f"⚠️  WARNINGS: {len(warnings)}")
        print(f"❌ FAILED: {len(failed)}")
        print()
        
        if passed:
            print("=" * 70)
            print("✅ PASSED COMPONENTS")
            print("=" * 70)
            for note in passed:
                print(f"  ✅ {note['component']}")
                print(f"     {note['message']}")
                if note['details']:
                    print(f"     Note: {note['details']}")
                print()
        
        if warnings:
            print("=" * 70)
            print("⚠️  WARNINGS")
            print("=" * 70)
            for note in warnings:
                print(f"  ⚠️  {note['component']}")
                print(f"     {note['message']}")
                if note['details']:
                    print(f"     Note: {note['details']}")
                print()
        
        if failed:
            print("=" * 70)
            print("❌ FAILED COMPONENTS")
            print("=" * 70)
            for note in failed:
                print(f"  ❌ {note['component']}")
                print(f"     {note['message']}")
                if note['details']:
                    print(f"     Fix: {note['details']}")
                print()
        
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        
        # Critical failures: MongoDB, LLM, Data Feed, or any Agent FAIL
        critical_failures = [n for n in failed if any(x in n['component'] for x in 
                            ["MongoDB", "LLM", "Data Feed", "Agent"])]
        
        # Also treat empty agent analysis as critical failure
        agent_warnings = [n for n in warnings if "Agent" in n['component'] and "empty" in n['message'].lower()]
        if agent_warnings:
            # Check if it's just LLM patterns missing (warning) vs complete failure (critical)
            for note in agent_warnings:
                if "completely empty" in note['message'].lower() or "all" in note['message'].lower():
                    critical_failures.append(note)
        
        if critical_failures:
            print("❌ CRITICAL FAILURES DETECTED")
            print("System cannot start without fixing these:")
            for note in critical_failures:
                print(f"   - {note['component']}: {note['message']}")
                if note['details']:
                    print(f"     {note['details']}")
            return False
        elif failed:
            print("⚠️  Some non-critical components failed")
            print("System may start but functionality may be limited")
            return True
        elif warnings:
            print("⚠️  Some warnings detected")
            print("System should work but may have reduced functionality")
            # Show warnings for visibility
            for note in warnings:
                if "Agent" in note['component']:
                    print(f"   ⚠️  {note['component']}: {note['message']}")
            return True
        else:
            print("✅ All components verified successfully!")
            return True

async def main():
    """Main verification function."""
    import sys
    
    # Get instrument
    if len(sys.argv) > 1:
        instrument = sys.argv[1].upper()
    else:
        instrument = os.getenv("TRADING_INSTRUMENT", "BTC").upper()
    
    print("Creating ComponentVerifier...", flush=True)
    verifier = ComponentVerifier()
    
    print("=" * 70, flush=True)
    print("COMPREHENSIVE COMPONENT VERIFICATION", flush=True)
    print("=" * 70, flush=True)
    print(f"Instrument: {instrument}", flush=True)
    print(flush=True)
    
    # Verify each component (with immediate flush)
    print("Verifying MongoDB...", flush=True)
    verifier.verify_mongodb()
    print("   MongoDB check complete", flush=True)
    
    print("Verifying Redis...", flush=True)
    verifier.verify_redis()
    print("   Redis check complete", flush=True)
    
    print("Verifying LLM Provider...", flush=True)
    verifier.verify_llm_provider()
    print("   LLM Provider check complete", flush=True)
    
    print("Verifying Market Data...", flush=True)
    verifier.verify_market_data()
    print("   Market Data check complete", flush=True)
    
    print("Verifying Data Feed...", flush=True)
    verifier.verify_data_feed(instrument)
    print("   Data Feed check complete", flush=True)
    
    print("Verifying Agents (this may take 30-60 seconds)...", flush=True)
    await verifier.verify_agents()
    print("   Agent verification complete", flush=True)
    
    # Print report
    all_ok = verifier.print_report()
    
    return all_ok

if __name__ == "__main__":
    try:
        print("Starting verification script...", flush=True)
        success = asyncio.run(main())
        print(f"\nVerification complete. Success: {success}", flush=True)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Verification interrupted by user", flush=True)
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Verification failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

