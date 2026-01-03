"""Fast rule-based execution engine for options chain trading."""

import asyncio
import json
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import redis.asyncio as redis
import pandas_ta as ta
from kiteconnect import KiteConnect
from data.market_memory import MarketMemory
from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class RuleSignal:
    """Represents a trading rule signal."""
    rule_id: str
    name: str
    direction: str  # BUY or SELL
    instrument: str
    conditions: List[Dict[str, Any]]
    risk_pct: float
    sl_pct: float
    target_pct: float
    max_trades: int = 1
    trades_executed: int = 0


class RuleEngine:
    """Fast rule evaluation engine for options trading."""
    
    def __init__(self, kite: Optional[KiteConnect] = None, market_memory: Optional[MarketMemory] = None):
        """Initialize rule engine."""
        self.kite = kite
        self.market_memory = market_memory or MarketMemory()
        self.redis_client: Optional[redis.Redis] = None  # type: ignore
        self.active_rules: List[RuleSignal] = []
        self.indicators: Dict[str, Any] = {}
        self.trade_counts: Dict[str, int] = {}  # Track trades per rule
        
        # MongoDB connection
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.trades_collection = get_collection(self.db, "rule_engine_trades")
        
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Rule engine Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    async def load_rules(self):
        """Load active rules from Redis (LLM-generated)."""
        if not self.redis_client:
            await self.initialize()
            if not self.redis_client:
                logger.warning("Redis not available, cannot load rules")
                return
        
        try:
            rules_json = await self.redis_client.get("active_rules")
            if rules_json:
                rules_data = json.loads(rules_json)
                self.active_rules = []
                
                for rule_data in rules_data.get("rules", []):
                    try:
                        rule = RuleSignal(
                            rule_id=rule_data.get("rule_id", f"rule_{len(self.active_rules)}"),
                            name=rule_data.get("name", "Unnamed Rule"),
                            direction=rule_data.get("direction", "BUY"),
                            instrument=rule_data.get("instrument", ""),
                            conditions=rule_data.get("conditions", []),
                            risk_pct=rule_data.get("position_size", {}).get("risk_pct", 0.5),
                            sl_pct=abs(rule_data.get("stop_loss", {}).get("premium_pct", -15)),
                            target_pct=rule_data.get("target", {}).get("premium_pct", 25),
                            max_trades=rule_data.get("max_trades", 1),
                            trades_executed=self.trade_counts.get(rule_data.get("rule_id", ""), 0)
                        )
                        self.active_rules.append(rule)
                    except Exception as e:
                        logger.error(f"Error parsing rule: {e}")
                        continue
                
                logger.info(f"Loaded {len(self.active_rules)} active rules")
            else:
                logger.debug("No active rules found in Redis")
        except Exception as e:
            logger.error(f"Error loading rules: {e}")
    
    async def update_indicators(self, tick_data: Dict[str, Any]):
        """Update technical indicators (RSI, OI changes, etc.)."""
        if not self.redis_client:
            return
        
        try:
            instrument = tick_data.get("instrument", "BANKNIFTY")
            price = tick_data.get("ltp") or tick_data.get("last_price") or tick_data.get("price")
            
            if not price:
                return
            
            # Store tick for RSI calculation
            tick_key = f"rule_engine_ticks:{instrument}"
            await self.redis_client.lpush(tick_key, json.dumps({
                "price": float(price),
                "timestamp": tick_data.get("timestamp", datetime.now().isoformat())
            }))
            await self.redis_client.ltrim(tick_key, 0, 19)  # Keep last 20 ticks
            
            # Calculate RSI(5)
            ticks_data = await self.redis_client.lrange(tick_key, 0, -1)
            if len(ticks_data) >= 5:
                import pandas as pd
                closes = [json.loads(t)["price"] for t in reversed(ticks_data)]
                closes_array = np.array(closes)
                rsi = ta.rsi(pd.Series(closes_array), length=5)
                if not rsi.empty and pd.notna(rsi.iloc[-1]):
                    self.indicators[f"{instrument}_rsi5"] = float(rsi.iloc[-1])
            
            # Update OI changes if provided
            if "oi_data" in tick_data:
                self._update_oi_changes(tick_data["oi_data"])
                
        except Exception as e:
            logger.debug(f"Error updating indicators: {e}")
    
    def _update_oi_changes(self, oi_data: Dict[str, Any]):
        """Update OI change tracking."""
        try:
            for strike, data in oi_data.items():
                if "ce_oi" in data:
                    oi_key = f"oi_ce_{strike}"
                    prev_oi = self.indicators.get(oi_key, data["ce_oi"])
                    if prev_oi > 0:
                        change_pct = ((data["ce_oi"] - prev_oi) / prev_oi) * 100
                        self.indicators[f"{oi_key}_change_pct"] = change_pct
                    self.indicators[oi_key] = data["ce_oi"]
                
                if "pe_oi" in data:
                    oi_key = f"oi_pe_{strike}"
                    prev_oi = self.indicators.get(oi_key, data["pe_oi"])
                    if prev_oi > 0:
                        change_pct = ((data["pe_oi"] - prev_oi) / prev_oi) * 100
                        self.indicators[f"{oi_key}_change_pct"] = change_pct
                    self.indicators[oi_key] = data["pe_oi"]
        except Exception as e:
            logger.debug(f"Error updating OI changes: {e}")
    
    async def evaluate_rules(self, tick: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate all active rules and return signals that match."""
        await self.update_indicators(tick)
        
        signals = []
        for rule in self.active_rules:
            try:
                if await self._conditions_met(rule, tick):
                    # Check if max trades reached
                    if rule.trades_executed >= rule.max_trades:
                        continue
                    
                    signals.append({
                        "rule_id": rule.rule_id,
                        "rule_name": rule.name,
                        "direction": rule.direction,
                        "instrument": rule.instrument,
                        "entry_price": tick.get("ltp") or tick.get("last_price") or tick.get("price"),
                        "risk_pct": rule.risk_pct,
                        "sl_pct": rule.sl_pct,
                        "target_pct": rule.target_pct
                    })
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.rule_id}: {e}")
                continue
        
        return signals
    
    async def _conditions_met(self, rule: RuleSignal, tick: Dict[str, Any]) -> bool:
        """Check if all conditions for a rule are met."""
        context = self._build_context(tick)
        
        for cond in rule.conditions:
            if not self._check_condition(cond, context):
                return False
        
        return True
    
    def _build_context(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        """Build evaluation context from tick and indicators."""
        instrument = tick.get("instrument", "BANKNIFTY")
        price = tick.get("ltp") or tick.get("last_price") or tick.get("price", 0)
        
        context = {
            "fut_ltp": float(price),
            "timestamp": tick.get("timestamp", datetime.now().isoformat()),
            "rsi5": self.indicators.get(f"{instrument}_rsi5", 50.0),
        }
        
        # Add OI data if available
        for key, value in self.indicators.items():
            if key.startswith("oi_"):
                context[key] = value
        
        return context
    
    def _check_condition(self, cond: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate a single condition."""
        cond_type = cond.get("type")
        value = cond.get("value")
        
        try:
            if cond_type == "fut_ltp_above":
                return context["fut_ltp"] > value
            elif cond_type == "fut_ltp_below":
                return context["fut_ltp"] < value
            elif cond_type == "rsi_5_above":
                return context.get("rsi5", 50) > value
            elif cond_type == "rsi_5_below":
                return context.get("rsi5", 50) < value
            elif cond_type == "oi_spike_ce":
                strike = cond.get("strike")
                min_pct = cond.get("min_pct", 10)
                oi_key = f"oi_ce_{strike}_change_pct"
                return context.get(oi_key, 0) > min_pct
            elif cond_type == "oi_spike_pe":
                strike = cond.get("strike")
                min_pct = cond.get("min_pct", 10)
                oi_key = f"oi_pe_{strike}_change_pct"
                return context.get(oi_key, 0) > min_pct
            elif cond_type == "premium_acceleration":
                # Simplified - would need premium history
                min_pct = cond.get("min_pct", 5)
                # For now, return True if RSI indicates momentum
                return context.get("rsi5", 50) > 55
            elif cond_type == "volume_spike":
                # Would need volume history
                min_pct = cond.get("min_pct", 30)
                # Simplified check
                return True  # Placeholder
            else:
                logger.warning(f"Unknown condition type: {cond_type}")
                return False
        except Exception as e:
            logger.error(f"Error checking condition {cond_type}: {e}")
            return False
    
    async def execute_trade(self, signal: Dict[str, Any], tick: Dict[str, Any]):
        """Execute a trade based on signal."""
        if not self.kite:
            logger.warning("Kite API not available, cannot execute trade")
            return None
        
        try:
            rule_id = signal["rule_id"]
            direction = signal["direction"]
            instrument = signal["instrument"]
            entry_price = signal["entry_price"]
            risk_pct = signal["risk_pct"]
            
            # Calculate position size based on risk
            qty = self._calculate_qty(risk_pct, entry_price)
            
            if qty <= 0:
                logger.warning(f"Invalid quantity calculated: {qty}")
                return None
            
            # Place order
            if settings.paper_trading_mode:
                order_result = await self._place_paper_order(signal, qty, entry_price)
            else:
                order_result = await self._place_real_order(signal, qty, entry_price)
            
            # Update trade count
            self.trade_counts[rule_id] = self.trade_counts.get(rule_id, 0) + 1
            
            # Update rule trades_executed
            for rule in self.active_rules:
                if rule.rule_id == rule_id:
                    rule.trades_executed += 1
                    break
            
            # Log to MongoDB
            trade_log = {
                "rule_id": rule_id,
                "rule_name": signal["rule_name"],
                "direction": direction,
                "instrument": instrument,
                "entry_price": entry_price,
                "quantity": qty,
                "stop_loss_pct": signal["sl_pct"],
                "target_pct": signal["target_pct"],
                "timestamp": datetime.now().isoformat(),
                "order_id": order_result.get("order_id"),
                "status": order_result.get("status", "PENDING")
            }
            
            await asyncio.to_thread(self.trades_collection.insert_one, trade_log)
            logger.info(f"Trade executed: {direction} {qty} {instrument} @ {entry_price}")
            
            return order_result
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}", exc_info=True)
            return None
    
    def _calculate_qty(self, risk_pct: float, entry_price: float) -> int:
        """Calculate position size based on risk percentage."""
        # Simplified calculation - would need account balance
        # For now, use fixed lot size for options
        if "CE" in str(entry_price) or "PE" in str(entry_price):
            # Options: typically 1 lot = 15 or 25 shares
            return 15  # 1 lot
        else:
            # Futures: calculate based on risk
            # Placeholder - would need account balance
            return 1
    
    async def _place_paper_order(self, signal: Dict[str, Any], qty: int, price: float) -> Dict[str, Any]:
        """Place paper trading order."""
        order_id = f"PAPER_RULE_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        return {
            "order_id": order_id,
            "filled_price": price,
            "filled_quantity": qty,
            "status": "COMPLETE",
            "paper_trading": True
        }
    
    async def _place_real_order(self, signal: Dict[str, Any], qty: int, price: float) -> Dict[str, Any]:
        """Place real order via Zerodha Kite API."""
        try:
            direction = signal["direction"]
            instrument = signal["instrument"]
            
            # Get instrument token
            instrument_token = await self._get_instrument_token(instrument)
            if not instrument_token:
                raise ValueError(f"Instrument not found: {instrument}")
            
            # Place order
            order = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange="NFO",  # Options are on NFO
                tradingsymbol=instrument,
                transaction_type=self.kite.TRANSACTION_TYPE_BUY if direction == "BUY" else self.kite.TRANSACTION_TYPE_SELL,
                quantity=qty,
                product=self.kite.PRODUCT_MIS,
                order_type=self.kite.ORDER_TYPE_MARKET
            )
            
            return {
                "order_id": order.get("order_id"),
                "status": "PENDING",
                "paper_trading": False
            }
        except Exception as e:
            logger.error(f"Error placing real order: {e}")
            raise
    
    async def _get_instrument_token(self, instrument_symbol: str) -> Optional[int]:
        """Get instrument token for options symbol."""
        if not self.kite:
            return None
        
        try:
            instruments = await asyncio.to_thread(self.kite.instruments, "NFO")
            for inst in instruments:
                if inst.get("tradingsymbol") == instrument_symbol:
                    return inst["instrument_token"]
            return None
        except Exception as e:
            logger.error(f"Error getting instrument token: {e}")
            return None


# pandas imported locally where needed

