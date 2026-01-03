"""System health checker for all components."""

import logging
from typing import Dict, Any, List
from datetime import datetime
from mongodb_schema import get_mongo_client, get_collection
from data.market_memory import MarketMemory
from config.settings import settings

logger = logging.getLogger(__name__)


class SystemHealthChecker:
    """Check health of all system components."""
    
    def __init__(self):
        """Initialize health checker."""
        self.market_memory = MarketMemory()
        # Circuit breaker state for endpoints
        self._endpoint_circuits = {}
        self.failure_threshold = 2
        self.cooldown_seconds = 30
    
    def check_all(self) -> Dict[str, Any]:
        """Check health of all components."""
        health = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "components": {}
        }
        
        # Check MongoDB
        health["components"]["mongodb"] = self._check_mongodb()
        
        # Check Redis
        health["components"]["redis"] = self._check_redis()
        
        # Check Market Data
        health["components"]["market_data"] = self._check_market_data()
        
        # Check Agents
        health["components"]["agents"] = self._check_agents()
        
        # Check Data Feed
        health["components"]["data_feed"] = self._check_data_feed()
        
        # Determine overall status
        all_healthy = all(
            comp.get("status") == "healthy" 
            for comp in health["components"].values()
        )
        health["overall_status"] = "healthy" if all_healthy else "degraded"
        
        return health
    
    def _check_mongodb(self) -> Dict[str, Any]:
        """Check MongoDB connection."""
        try:
            client = get_mongo_client()
            client.server_info()
            
            # Check if collections exist
            db = client[settings.mongodb_db_name]
            collections = db.list_collection_names()
            
            # Count documents in key collections
            trades_count = db.trades_executed.count_documents({})
            ohlc_count = db.ohlc_history.count_documents({})
            
            return {
                "status": "healthy",
                "connected": True,
                "database": settings.mongodb_db_name,
                "collections": len(collections),
                "trades_count": trades_count,
                "ohlc_count": ohlc_count,
                "message": f"MongoDB connected, {trades_count} trades, {ohlc_count} OHLC records"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "message": f"MongoDB connection failed: {e}"
            }
    
    def _check_redis(self) -> Dict[str, Any]:
        """Check Redis connection."""
        try:
            if self.market_memory._redis_available:
                self.market_memory.redis_client.ping()
                
                # Check for data
                keys = self.market_memory.redis_client.keys("tick:*")
                ohlc_keys = self.market_memory.redis_client.keys("ohlc:*")
                
                return {
                    "status": "healthy",
                    "connected": True,
                    "tick_keys": len(keys),
                    "ohlc_keys": len(ohlc_keys),
                    "message": f"Redis connected, {len(keys)} ticks, {len(ohlc_keys)} OHLC records"
                }
            else:
                return {
                    "status": "degraded",
                    "connected": False,
                    "message": "Redis not available (fallback mode active)"
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "message": f"Redis connection failed: {e}"
            }
    
    def _check_market_data(self) -> Dict[str, Any]:
        """Check market data availability."""
        try:
            instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
            current_price = self.market_memory.get_current_price(instrument_key)
            ohlc_data = self.market_memory.get_recent_ohlc(instrument_key, "1min", 1)
            
            # Also check MongoDB as fallback
            ohlc_count_mongo = 0
            try:
                mongo_client = get_mongo_client()
                db = mongo_client[settings.mongodb_db_name]
                ohlc_collection = get_collection(db, "ohlc_history")
                ohlc_count_mongo = ohlc_collection.count_documents({"instrument": settings.instrument_symbol})
                
                # If no price from Redis, try MongoDB
                if not current_price and ohlc_count_mongo > 0:
                    last_ohlc = ohlc_collection.find_one(
                        {"instrument": settings.instrument_symbol},
                        sort=[("timestamp", -1)]
                    )
                    if last_ohlc and last_ohlc.get("close"):
                        current_price = float(last_ohlc["close"])
            except Exception as e:
                logger.debug(f"Error checking MongoDB for market data: {e}")
            
            if current_price:
                currency_symbol = "$" if settings.data_source == "CRYPTO" else "₹"
                return {
                    "status": "healthy",
                    "current_price": current_price,
                    "has_ohlc": len(ohlc_data) > 0 or ohlc_count_mongo > 0,
                    "ohlc_count": len(ohlc_data) or ohlc_count_mongo,
                    "message": f"Market data available, price: {currency_symbol}{current_price:.2f}"
                }
            else:
                # More specific error message
                if ohlc_count_mongo > 0:
                    return {
                        "status": "degraded",
                        "current_price": None,
                        "has_ohlc": True,
                        "ohlc_count": ohlc_count_mongo,
                        "message": f"No current price in Redis, but {ohlc_count_mongo} OHLC records in MongoDB. Data feed may have stopped."
                    }
                else:
                    return {
                        "status": "degraded",
                        "current_price": None,
                        "has_ohlc": False,
                        "message": f"No market data for {settings.instrument_name} ({instrument_key}). Start data feed: python scripts/start_all.py {settings.instrument_symbol.split('-')[0] if '-' in settings.instrument_symbol else settings.instrument_symbol}"
                    }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "message": f"Market data check failed: {e}"
            }
    
    def _check_agents(self) -> Dict[str, Any]:
        """Check agent status."""
        try:
            # List of all agents
            agents = [
                "TechnicalAnalysisAgent",
                "FundamentalAnalysisAgent",
                "SentimentAnalysisAgent",
                "MacroAnalysisAgent",
                "BullResearcherAgent",
                "BearResearcherAgent",
                "AggressiveRiskAgent",
                "ConservativeRiskAgent",
                "NeutralRiskAgent",
                "PortfolioManagerAgent",
                "ExecutionAgent",
                "LearningAgent"
            ]
            
            # Check if agents can be imported
            agent_status = {}
            for agent_name in agents:
                try:
                    # Try to import agent module
                    module_name = agent_name.lower().replace("agent", "_agent")
                    if "researcher" in agent_name.lower():
                        module_name = agent_name.lower().replace("researcheragent", "_researcher")
                    elif "risk" in agent_name.lower():
                        module_name = "risk_agents"
                    elif "portfolio" in agent_name.lower():
                        module_name = "portfolio_manager"
                    elif "execution" in agent_name.lower():
                        module_name = "execution_agent"
                    elif "learning" in agent_name.lower():
                        module_name = "learning_agent"
                    
                    agent_status[agent_name] = {
                        "status": "available",
                        "message": "Agent module available"
                    }
                except Exception as e:
                    agent_status[agent_name] = {
                        "status": "error",
                        "error": str(e),
                        "message": f"Agent import failed: {e}"
                    }
            
            # Check LLM provider
            llm_status = "configured" if (settings.groq_api_key or settings.openai_api_key) else "not_configured"
            
            return {
                "status": "healthy" if llm_status == "configured" else "degraded",
                "llm_provider": settings.llm_provider,
                "llm_configured": llm_status == "configured",
                "agents": agent_status,
                "total_agents": len(agents),
                "message": f"{len(agents)} agents available, LLM: {settings.llm_provider}"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "message": f"Agent check failed: {e}"
            }
    
    def check_endpoint(self, url: str, timeout: int = 3, max_retries: int = 2) -> Dict[str, Any]:
        """Check an external HTTP endpoint using retries and a circuit breaker.

        Returns a dict with status: healthy/degraded/unhealthy and details.
        """
        import requests
        from datetime import datetime, timedelta

        # Circuit open? skip
        state = self._endpoint_circuits.get(url, {'count': 0})
        if state.get('open_until') and state['open_until'] > datetime.now().timestamp():
            return {'status': 'degraded', 'message': 'circuit_open'}

        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                r = requests.get(url, timeout=timeout)
                r.raise_for_status()
                # reset state on success
                if url in self._endpoint_circuits:
                    self._endpoint_circuits.pop(url, None)
                return {'status': 'healthy', 'status_code': r.status_code}
            except Exception as e:
                last_exc = e
                # backoff
                import time
                time.sleep(0.1 * (2 ** (attempt - 1)))
                continue

        # mark failure and possibly open circuit
        state['count'] = state.get('count', 0) + 1
        if state['count'] >= self.failure_threshold:
            state['open_until'] = (datetime.now() + timedelta(seconds=self.cooldown_seconds)).timestamp()
        self._endpoint_circuits[url] = state
        return {'status': 'unhealthy', 'error': str(last_exc)}

    def _check_data_feed(self) -> Dict[str, Any]:
        """Check data feed status - supports Zerodha and Crypto."""
        try:
            from datetime import datetime, timedelta
            from pathlib import Path
            
            # Get instrument key for data lookup
            instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()            
            # Check data source configuration
            data_source = settings.data_source or "UNKNOWN"
            zerodha_configured = Path("credentials.json").exists()
            crypto_configured = data_source == "CRYPTO"
            
            # Check if we have recent data (from Redis or MongoDB)
            current_price = self.market_memory.get_current_price(instrument_key)
            
            # Also check MongoDB for recent OHLC data as fallback
            ohlc_count = 0
            recent_data_timestamp = None
            if not current_price:
                try:
                    mongo_client = get_mongo_client()
                    db = mongo_client[settings.mongodb_db_name]
                    ohlc_collection = get_collection(db, "ohlc_history")
                    last_ohlc = ohlc_collection.find_one(
                        {"instrument": settings.instrument_symbol},
                        sort=[("timestamp", -1)]
                    )
                    if last_ohlc:
                        if last_ohlc.get("close"):
                            current_price = last_ohlc["close"]
                        if last_ohlc.get("timestamp"):
                            try:
                                if isinstance(last_ohlc["timestamp"], str):
                                    recent_data_timestamp = datetime.fromisoformat(last_ohlc["timestamp"].replace("Z", "+00:00"))
                                else:
                                    recent_data_timestamp = last_ohlc["timestamp"]
                            except:
                                pass
                    ohlc_count = ohlc_collection.count_documents({"instrument": settings.instrument_symbol})
                except Exception as e:
                    logger.debug(f"Error checking MongoDB for OHLC: {e}")
            
            instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
            ohlc_data = self.market_memory.get_recent_ohlc(instrument_key, "1min", 1)
            
            # Check if market is open - for 24/7 markets (crypto), always open
            now = datetime.now()
            if settings.market_24_7:
                market_open = True
            else:
                try:
                    open_time = datetime.strptime(settings.market_open_time, "%H:%M:%S").time()
                    close_time = datetime.strptime(settings.market_close_time, "%H:%M:%S").time()
                    market_open = (now.weekday() < 5 and open_time <= now.time() <= close_time)
                except ValueError:
                    market_open = False
            
            # Check if data is recent (within last 5 minutes)
            data_is_recent = False
            if recent_data_timestamp:
                time_diff = now - (recent_data_timestamp.replace(tzinfo=None) if recent_data_timestamp.tzinfo else recent_data_timestamp)
                data_is_recent = time_diff < timedelta(minutes=5)
            
            # If we have price data OR recent OHLC records, feed is working
            has_data = current_price is not None or (ohlc_count > 0 and data_is_recent)
            
            # Determine data source name for display
            data_source_map = {
                "CRYPTO": "Binance WebSocket",
                "ZERODHA": "Zerodha Kite",
                "FINNHUB": "Finnhub"
            }
            source_name = data_source_map.get(data_source, data_source)

            # Example: allow external endpoint check via circuit breaker helper
            # (used for checking external API endpoints if configured)
            def _check_endpoint_with_circuit(url: str, timeout: int = 3) -> Dict[str, Any]:
                import requests
                from datetime import datetime, timedelta
                state = self._endpoint_circuits.get(url, {'count': 0})
                if state.get('open_until') and state['open_until'] > datetime.now().timestamp():
                    return {'status': 'degraded', 'message': 'circuit_open'}

                last_exc = None
                for attempt in range(1, 3):
                    try:
                        r = requests.get(url, timeout=timeout)
                        r.raise_for_status()
                        # on success reset failure count
                        if url in self._endpoint_circuits:
                            self._endpoint_circuits.pop(url, None)
                        return {'status': 'healthy', 'status_code': r.status_code}
                    except Exception as e:
                        last_exc = e
                        # backoff
                        import time
                        time.sleep(0.1 * (2 ** (attempt - 1)))
                        continue

                # mark failure
                state['count'] = state.get('count', 0) + 1
                if state['count'] >= self.failure_threshold:
                    state['open_until'] = (datetime.now() + timedelta(seconds=self.cooldown_seconds)).timestamp()
                self._endpoint_circuits[url] = state
                return {'status': 'unhealthy', 'error': str(last_exc)}

            # Optionally use _check_endpoint_with_circuit for external data source checks if available
            # e.g., check an API endpoint from settings.api_health_check_url
            api_check_url = getattr(settings, 'api_health_check_url', None)
            if api_check_url:
                endpoint_status = self.check_endpoint(api_check_url)
                if endpoint_status.get('status') != 'healthy':
                    return {
                        'status': 'degraded',
                        'source': source_name,
                        'configured': True,
                        'receiving_data': False,
                        'market_open': market_open,
                        'message': f"{source_name} configured but external endpoint check failed: {endpoint_status}"
                    }            
            # Check configuration based on data source
            if data_source == "CRYPTO":
                # Crypto doesn't need credentials.json
                configured = True
                if has_data:
                    return {
                        "status": "healthy",
                        "source": source_name,
                        "configured": True,
                        "receiving_data": True,
                        "current_price": current_price,
                        "ohlc_count": ohlc_count,
                        "market_open": True,  # Crypto is 24/7
                        "data_is_recent": data_is_recent,
                        "message": f"{source_name} active, receiving data" + (f" at ${current_price:.2f}" if current_price else f" ({ohlc_count} OHLC records)")
                    }
                else:
                    return {
                        "status": "degraded",
                        "source": source_name,
                        "configured": True,
                        "receiving_data": False,
                        "market_open": True,
                        "message": f"{source_name} configured but not receiving data. Start feed: python scripts/start_all.py BTC"
                    }
            elif data_source == "ZERODHA" or zerodha_configured:
                # Zerodha requires credentials.json
                if not zerodha_configured:
                    return {
                        "status": "unhealthy",
                        "source": source_name,
                        "configured": False,
                        "receiving_data": False,
                        "zerodha_configured": False,
                        "message": "Zerodha not configured. Run: python auto_login.py"
                    }
                
                # Check if Zerodha is receiving data
                if has_data:
                    return {
                        "status": "healthy",
                        "source": source_name,
                        "configured": True,
                        "receiving_data": True,
                        "current_price": current_price,
                        "ohlc_count": ohlc_count,
                        "zerodha_configured": True,
                        "market_open": market_open,
                        "data_is_recent": data_is_recent,
                        "message": f"{source_name} active, receiving data" + (f" at ₹{current_price:.2f}" if current_price else f" ({ohlc_count} OHLC records)")
                    }
                else:
                    # No data - determine reason
                    if not market_open:
                        return {
                            "status": "degraded",
                            "source": source_name,
                            "configured": True,
                            "receiving_data": False,
                            "zerodha_configured": True,
                            "market_open": False,
                            "message": f"{source_name} configured but market is closed (data only available 9:15 AM - 3:30 PM IST, Mon-Fri)"
                        }
                    else:
                        # Market is open but no data - provide specific instructions
                        return {
                            "status": "degraded",
                            "source": source_name,
                            "configured": True,
                            "receiving_data": False,
                            "zerodha_configured": True,
                            "market_open": True,
                            "message": f"{source_name} configured but not receiving data. Start feed: python scripts/start_all.py BANKNIFTY"
                        }
            else:
                # Unknown or unconfigured data source
                return {
                    "status": "unhealthy",
                    "source": source_name,
                    "configured": False,
                    "receiving_data": False,
                    "message": f"Data source '{data_source}' not properly configured. Check DATA_SOURCE in .env"
                }
        except Exception as e:
            logger.error(f"Error in data feed check: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "error": str(e),
                "message": f"Data feed check failed: {e}"
            }
    
    def get_agent_status_details(self) -> Dict[str, Any]:
        """Get detailed agent status."""
        try:
            mongo_client = get_mongo_client()
            db = mongo_client[settings.mongodb_db_name]
            trades_collection = get_collection(db, "trades_executed")
            analysis_collection = get_collection(db, "agent_decisions")
            ohlc_collection = get_collection(db, "ohlc_history")
            
            # Check if we have market data (required for agents)
            has_market_data = False
            instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
            current_price = self.market_memory.get_current_price(instrument_key)
            ohlc_count = ohlc_collection.count_documents({"instrument": settings.instrument_symbol})
            
            if current_price or ohlc_count > 0:
                has_market_data = True
            
            # Get latest analysis from agent_decisions collection (includes HOLD decisions)
            latest_analysis = analysis_collection.find_one(
                sort=[("timestamp", -1)]
            )
            
            # Get latest trade with agent decisions
            latest_trade = trades_collection.find_one(
                {"agent_decisions": {"$exists": True}},
                sort=[("entry_timestamp", -1)]
            )
            
            # Prefer analysis collection (has all runs), fallback to trades
            if latest_analysis:
                agents = latest_analysis.get("agent_decisions", {})
                return {
                    "status": "active",
                    "last_analysis": latest_analysis.get("timestamp"),
                    "final_signal": latest_analysis.get("final_signal", "N/A"),
                    "agents": agents,
                    "has_market_data": has_market_data,
                    "current_price": current_price,
                    "message": f"Agents are active. Last analysis: {latest_analysis.get('timestamp', 'N/A')} - Signal: {latest_analysis.get('final_signal', 'N/A')}"
                }
            elif latest_trade and latest_trade.get("agent_decisions"):
                agents = latest_trade["agent_decisions"]
                return {
                    "status": "active",
                    "last_analysis": latest_trade.get("entry_timestamp"),
                    "final_signal": latest_trade.get("signal", "N/A"),
                    "agents": agents,
                    "has_market_data": has_market_data,
                    "current_price": current_price,
                    "message": f"Agents are active. Last trade: {latest_trade.get('entry_timestamp', 'N/A')} - Signal: {latest_trade.get('signal', 'N/A')}"
                }
            else:
                if not has_market_data:
                    return {
                        "status": "waiting",
                        "agents": {},
                        "has_market_data": False,
                        "current_price": None,
                        "message": "Waiting for market data. Start data feed: python -m data.run_ingestion"
                    }
                else:
                    return {
                        "status": "ready",
                        "agents": {},
                        "has_market_data": True,
                        "current_price": current_price,
                        "message": "Market data available. Agents will run automatically every 60 seconds. Start trading service: python start_trading_system.py"
                    }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": f"Error checking agent status: {e}"
            }

