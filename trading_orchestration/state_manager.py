"""State manager for AgentState initialization and updates."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from agents.state import AgentState
from data.market_memory import MarketMemory
from data.macro_collector import MacroCollector
from data.volume_analyzer import VolumeAnalyzer
from data.order_flow_analyzer import OrderFlowAnalyzer
from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings

logger = logging.getLogger(__name__)


class StateManager:
    """Manages AgentState initialization and updates from market data."""
    
    def __init__(self, market_memory: MarketMemory):
        """Initialize state manager."""
        self.market_memory = market_memory
        self.macro_collector = MacroCollector()
        # MongoDB connection for news loading
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.news_collection = get_collection(self.db, "market_events")
    
    def initialize_state(self) -> AgentState:
        """Initialize AgentState from current market data."""
        logger.info("Initializing AgentState from market data...")
        
        # Get instrument key from settings
        instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
        
        # Get current price
        current_price = self.market_memory.get_current_price(instrument_key) or 0.0
        
        # Get OHLC data
        ohlc_1min = self.market_memory.get_recent_ohlc(instrument_key, "1min", 60)
        ohlc_5min = self.market_memory.get_recent_ohlc(instrument_key, "5min", 100)
        ohlc_15min = self.market_memory.get_recent_ohlc(instrument_key, "15min", 100)
        ohlc_hourly = self.market_memory.get_recent_ohlc(instrument_key, "hourly", 60)
        ohlc_daily = self.market_memory.get_recent_ohlc(instrument_key, "daily", 60)
        
        # Get sentiment
        sentiment_score = self.market_memory.get_latest_sentiment("news") or 0.0
        
        # Get latest news items
        latest_news = self._load_latest_news(limit=20)
        
        # Get macro context
        macro_context = self.macro_collector.get_latest_macro_context()
        
        # Get latest tick for order flow data
        latest_tick = self._get_latest_tick(instrument_key)
        
        # Calculate volume analysis
        volume_analysis = self._calculate_volume_analysis(ohlc_5min)
        
        # Calculate order flow signals
        order_flow_signals = self._calculate_order_flow_signals(latest_tick)
        
        # Initialize state
        state = AgentState(
            current_price=current_price,
            current_time=datetime.now(),
            ohlc_1min=ohlc_1min,
            ohlc_5min=ohlc_5min,
            ohlc_15min=ohlc_15min,
            ohlc_hourly=ohlc_hourly,
            ohlc_daily=ohlc_daily,
            latest_news=latest_news,
            sentiment_score=sentiment_score,
            rbi_rate=macro_context.get("rbi_rate"),
            inflation_rate=macro_context.get("inflation_rate"),
            npa_ratio=macro_context.get("npa_ratio"),
            # Order flow data
            best_bid_price=latest_tick.get("best_bid_price") if latest_tick else None,
            best_ask_price=latest_tick.get("best_ask_price") if latest_tick else None,
            best_bid_quantity=latest_tick.get("best_bid_quantity", 0) if latest_tick else 0,
            best_ask_quantity=latest_tick.get("best_ask_quantity", 0) if latest_tick else 0,
            bid_ask_spread=latest_tick.get("bid_ask_spread") if latest_tick else None,
            buy_quantity=latest_tick.get("buy_quantity", 0) if latest_tick else 0,
            sell_quantity=latest_tick.get("sell_quantity", 0) if latest_tick else 0,
            buy_sell_imbalance=latest_tick.get("buy_sell_imbalance", 0.5) if latest_tick else 0.5,
            # Volume analysis
            volume_profile=volume_analysis.get("volume_profile", {}),
            volume_trends=volume_analysis.get("volume_trends", {}),
            vwap=volume_analysis.get("vwap"),
            obv=volume_analysis.get("obv"),
            # Order flow signals
            order_flow_signals=order_flow_signals
        )
        
        logger.info(f"State initialized: price={current_price}, sentiment={sentiment_score:.2f}, news_items={len(latest_news)}, "
                   f"order_flow={'available' if latest_tick else 'unavailable'}")
        
        return state
    
    def _get_latest_tick(self, instrument: str) -> Optional[Dict[str, Any]]:
        """Get latest tick data from Redis."""
        try:
            # Try to get from Redis
            if not self.market_memory._redis_available:
                return None
            
            pattern = f"tick:{instrument}:*"
            keys = self.market_memory.redis_client.keys(pattern)
            
            if not keys:
                return None
            
            # Get most recent tick
            latest_key = sorted(keys)[-1]
            data = self.market_memory.redis_client.get(latest_key)
            
            if data:
                import json
                return json.loads(data)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting latest tick: {e}")
            return None
    
    def _calculate_volume_analysis(self, ohlc_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate volume analysis metrics."""
        if not ohlc_data:
            return {}
        
        try:
            volume_analyzer = VolumeAnalyzer()
            
            volume_profile = volume_analyzer.calculate_volume_profile(ohlc_data)
            volume_trends = volume_analyzer.calculate_volume_trends(ohlc_data)
            vwap = volume_analyzer.calculate_vwap(ohlc_data)
            obv = volume_analyzer.calculate_obv(ohlc_data)
            
            return {
                "volume_profile": volume_profile,
                "volume_trends": volume_trends,
                "vwap": vwap,
                "obv": obv
            }
            
        except Exception as e:
            logger.error(f"Error calculating volume analysis: {e}")
            return {}
    
    def _calculate_order_flow_signals(self, latest_tick: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate order flow signals from latest tick."""
        if not latest_tick:
            return {}
        
        try:
            order_flow_analyzer = OrderFlowAnalyzer()
            
            buy_quantity = latest_tick.get("buy_quantity", 0)
            sell_quantity = latest_tick.get("sell_quantity", 0)
            bid_price = latest_tick.get("best_bid_price")
            ask_price = latest_tick.get("best_ask_price")
            current_price = latest_tick.get("last_price", 0.0)
            depth_buy = latest_tick.get("depth_buy", [])
            depth_sell = latest_tick.get("depth_sell", [])
            
            imbalance = order_flow_analyzer.calculate_buy_sell_imbalance(buy_quantity, sell_quantity)
            spread_analysis = order_flow_analyzer.analyze_bid_ask_spread(bid_price, ask_price, current_price)
            depth_analysis = order_flow_analyzer.analyze_market_depth(depth_buy, depth_sell)
            large_orders = order_flow_analyzer.detect_large_orders(depth_buy, depth_sell)
            
            return {
                "buy_sell_imbalance": imbalance,
                "spread_analysis": spread_analysis,
                "depth_analysis": depth_analysis,
                "large_orders": large_orders
            }
            
        except Exception as e:
            logger.error(f"Error calculating order flow signals: {e}")
            return {}
    
    def _load_latest_news(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Load latest news items from MongoDB."""
        try:
            # Query for news items from last 24 hours
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            news_items = list(
                self.news_collection.find(
                    {
                        "event_type": "NEWS",
                        "timestamp": {"$gte": cutoff_time.isoformat()}
                    }
                )
                .sort("timestamp", -1)
                .limit(limit)
            )
            
            # Convert MongoDB documents to dictionaries, removing _id
            result = []
            for item in news_items:
                item_dict = {k: v for k, v in item.items() if k != "_id"}
                # Ensure timestamp is string if it's datetime
                if "timestamp" in item_dict and isinstance(item_dict["timestamp"], datetime):
                    item_dict["timestamp"] = item_dict["timestamp"].isoformat()
                result.append(item_dict)
            
            logger.debug(f"Loaded {len(result)} news items from MongoDB")
            return result
            
        except Exception as e:
            logger.error(f"Error loading news items: {e}")
            return []
    
    def update_state_from_market(self, state: AgentState) -> AgentState:
        """Update state with latest market data."""
        # Update current price
        instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
        current_price = self.market_memory.get_current_price(instrument_key)
        if current_price:
            state.current_price = current_price
        
        # Update sentiment
        sentiment_score = self.market_memory.get_latest_sentiment("news")
        if sentiment_score is not None:
            state.sentiment_score = sentiment_score
        
        # Update news items (refresh periodically)
        latest_news = self._load_latest_news(limit=20)
        if latest_news:
            state.latest_news = latest_news
        
        # Update macro context
        macro_context = self.macro_collector.get_latest_macro_context()
        if macro_context.get("rbi_rate"):
            state.rbi_rate = macro_context["rbi_rate"]
        if macro_context.get("inflation_rate"):
            state.inflation_rate = macro_context["inflation_rate"]
        if macro_context.get("npa_ratio"):
            state.npa_ratio = macro_context["npa_ratio"]
        
        # Update order flow data from latest tick
        latest_tick = self._get_latest_tick(instrument_key)
        if latest_tick:
            state.best_bid_price = latest_tick.get("best_bid_price")
            state.best_ask_price = latest_tick.get("best_ask_price")
            state.best_bid_quantity = latest_tick.get("best_bid_quantity", 0)
            state.best_ask_quantity = latest_tick.get("best_ask_quantity", 0)
            state.bid_ask_spread = latest_tick.get("bid_ask_spread")
            state.buy_quantity = latest_tick.get("buy_quantity", 0)
            state.sell_quantity = latest_tick.get("sell_quantity", 0)
            state.buy_sell_imbalance = latest_tick.get("buy_sell_imbalance", 0.5)
            
            # Update order flow signals
            order_flow_signals = self._calculate_order_flow_signals(latest_tick)
            if order_flow_signals:
                state.order_flow_signals = order_flow_signals
        
        # Update volume analysis (recalculate periodically)
        if state.ohlc_5min:
            volume_analysis = self._calculate_volume_analysis(state.ohlc_5min)
            if volume_analysis:
                state.volume_profile = volume_analysis.get("volume_profile", {})
                state.volume_trends = volume_analysis.get("volume_trends", {})
                state.vwap = volume_analysis.get("vwap")
                state.obv = volume_analysis.get("obv")
        
        state.current_time = datetime.now()
        
        return state

