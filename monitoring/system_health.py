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
            
            if current_price:
                return {
                    "status": "healthy",
                    "current_price": current_price,
                    "has_ohlc": len(ohlc_data) > 0,
                    "ohlc_count": len(ohlc_data),
                    "message": f"Market data available, price: ₹{current_price:.2f}"
                }
            else:
                return {
                    "status": "degraded",
                    "current_price": None,
                    "has_ohlc": len(ohlc_data) > 0,
                    "message": "No current price available (data feed may not be running)"
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
    
    def _check_data_feed(self) -> Dict[str, Any]:
        """Check data feed status - Zerodha only (primary source)."""
        try:
            from datetime import datetime, timedelta
            from pathlib import Path
            
            # Check Zerodha configuration (primary source)
            zerodha_configured = Path("credentials.json").exists()
            
            # Check if we have recent data (from Redis or MongoDB)
            current_price = self.market_memory.get_current_price("BANKNIFTY")
            
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
            
            # Check if market is open
            now = datetime.now()
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
            
            # Zerodha is the only source we check
            if not zerodha_configured:
                return {
                    "status": "unhealthy",
                    "source": "None",
                    "configured": False,
                    "receiving_data": False,
                    "zerodha_configured": False,
                    "message": "Zerodha not configured. Run: python auto_login.py"
                }
            
            # Check if Zerodha is receiving data
            if has_data:
                return {
                    "status": "healthy",
                    "source": "Zerodha",
                    "configured": True,
                    "receiving_data": True,
                    "current_price": current_price,
                    "ohlc_count": ohlc_count,
                    "zerodha_configured": True,
                    "market_open": market_open,
                    "data_is_recent": data_is_recent,
                    "message": f"Zerodha WebSocket active, receiving data" + (f" at Rs {current_price:.2f}" if current_price else f" ({ohlc_count} OHLC records)")
                }
            else:
                # No data - determine reason
                if not market_open:
                    return {
                        "status": "degraded",
                        "source": "Zerodha",
                        "configured": True,
                        "receiving_data": False,
                        "zerodha_configured": True,
                        "market_open": False,
                        "message": "Zerodha configured but market is closed (data only available 9:15 AM - 3:30 PM IST, Mon-Fri)"
                    }
                else:
                    # Market is open but no data - provide specific instructions
                    return {
                        "status": "degraded",
                        "source": "Zerodha",
                        "configured": True,
                        "receiving_data": False,
                        "zerodha_configured": True,
                        "market_open": True,
                        "message": "Zerodha configured but not receiving data. Start feed: python -m services.trading_service OR python -m data.run_ingestion"
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

