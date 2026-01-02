"""Execution Agent for order placement and tracking."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from kiteconnect import KiteConnect
from agents.base_agent import BaseAgent
from agents.state import AgentState, SignalType
from config.settings import settings
from mongodb_schema import get_mongo_client, get_collection

logger = logging.getLogger(__name__)


class ExecutionAgent(BaseAgent):
    """Execution agent for order placement via Zerodha Kite API."""
    
    def __init__(self, kite: Optional[KiteConnect] = None, paper_trading: bool = True):
        """Initialize execution agent."""
        super().__init__("execution", self._get_default_prompt())
        self.kite = kite
        self.paper_trading = paper_trading or settings.paper_trading_mode
        
        # MongoDB connection
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.trades_collection = get_collection(self.db, "trades_executed")
    
    def _get_default_prompt(self) -> str:
        """Get default system prompt."""
        instrument_name = settings.instrument_name
        return f"""You are the Execution Agent for a {instrument_name} trading system.
Your role: Place orders via trading API and track execution."""
    
    def _get_instrument_token(self) -> Optional[int]:
        """Get instrument token for configured instrument."""
        if not self.kite:
            return None
        
        try:
            exchange = settings.instrument_exchange
            instruments = self.kite.instruments(exchange)
            for inst in instruments:
                if (inst.get("tradingsymbol") == settings.instrument_symbol or
                    inst.get("name") == settings.instrument_name):
                    return inst["instrument_token"]
        except Exception as e:
            logger.error(f"Error getting instrument token: {e}")
        
        return None
    
    def _place_paper_order(
        self,
        signal: SignalType,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        take_profit: float
    ) -> Dict[str, Any]:
        """Place a paper trade (simulated order)."""
        trade_id = f"PAPER_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        order_result = {
            "order_id": trade_id,
            "filled_price": entry_price,
            "filled_quantity": quantity,
            "execution_timestamp": datetime.now().isoformat(),
            "status": "COMPLETE",
            "paper_trading": True
        }
        
        signal_str = signal.value if hasattr(signal, 'value') else str(signal)
        logger.info(f"Paper trade placed: {signal_str} {quantity} @ {entry_price}")
        
        return order_result
    
    def _place_real_order(
        self,
        signal: SignalType,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        take_profit: float
    ) -> Dict[str, Any]:
        """Place a real order via Zerodha Kite API."""
        if not self.kite:
            raise ValueError("Kite client not initialized")
        
        instrument_token = self._get_instrument_token()
        if not instrument_token:
            raise ValueError(f"Could not find {settings.instrument_name} instrument token")
        
        try:
            # Determine transaction type
            transaction_type = (
                self.kite.TRANSACTION_TYPE_BUY if signal == SignalType.BUY
                else self.kite.TRANSACTION_TYPE_SELL
            )
            
            # Place bracket order (includes SL and target)
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_BO,  # Bracket order
                exchange=self.kite.EXCHANGE_NSE,
                tradingsymbol="NIFTY BANK",
                transaction_type=transaction_type,
                quantity=quantity,
                product=self.kite.PRODUCT_MIS,  # Intraday
                order_type=self.kite.ORDER_TYPE_LIMIT,
                price=entry_price,
                squareoff=take_profit,  # Target price
                stoploss=stop_loss,  # Stop loss price
                trailing_stoploss=0  # No trailing stop
            )
            
            signal_str = signal.value if hasattr(signal, 'value') else str(signal)
            logger.info(f"Order placed: {order_id} - {signal_str} {quantity} @ {entry_price}")
            
            # Check order status
            orders = self.kite.orders()
            order = next((o for o in orders if o["order_id"] == order_id), None)
            
            if order:
                filled_price = order.get("average_price", entry_price)
                filled_quantity = order.get("filled_quantity", 0)
                
                return {
                    "order_id": str(order_id),
                    "filled_price": float(filled_price),
                    "filled_quantity": int(filled_quantity),
                    "execution_timestamp": datetime.now().isoformat(),
                    "status": order.get("status", "PENDING"),
                    "paper_trading": False
                }
            else:
                return {
                    "order_id": str(order_id),
                    "filled_price": entry_price,
                    "filled_quantity": 0,
                    "execution_timestamp": datetime.now().isoformat(),
                    "status": "PENDING",
                    "paper_trading": False
                }
                
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise
    
    def process(self, state: AgentState) -> AgentState:
        """Process order execution."""
        logger.info("Processing order execution...")
        
        try:
            signal = state.final_signal
            quantity = state.position_size
            entry_price = state.entry_price
            stop_loss = state.stop_loss
            take_profit = state.take_profit
            
            # Handle signal (could be enum or string)
            signal_str = signal.value if hasattr(signal, 'value') else str(signal)
            signal_enum = SignalType(signal_str) if isinstance(signal_str, str) else signal
            
            # Only execute if signal is BUY or SELL
            if signal_enum not in [SignalType.BUY, SignalType.SELL]:
                logger.info(f"No execution needed for signal: {signal_str}")
                return state
            
            if quantity <= 0:
                logger.warning("Position size is 0, skipping execution")
                return state
            
            # Place order
            if self.paper_trading:
                order_result = self._place_paper_order(
                    signal_enum, quantity, entry_price, stop_loss, take_profit
                )
            else:
                order_result = self._place_real_order(
                    signal_enum, quantity, entry_price, stop_loss, take_profit
                )
            
            # Update state
            state.order_id = order_result["order_id"]
            state.filled_price = order_result["filled_price"]
            state.filled_quantity = order_result["filled_quantity"]
            state.execution_timestamp = datetime.fromisoformat(order_result["execution_timestamp"])
            
            # Generate trade ID
            state.trade_id = f"TRD_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Store trade in MongoDB
            trade_doc = {
                "trade_id": state.trade_id,
                "order_id": state.order_id,
                "signal": signal_str,
                "quantity": quantity,
                "entry_price": entry_price,
                "filled_price": state.filled_price,
                "filled_quantity": state.filled_quantity,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "entry_timestamp": state.execution_timestamp.isoformat(),
                "status": "OPEN",
                "paper_trading": order_result["paper_trading"],
                "agent_decisions": {
                    "technical": state.technical_analysis,
                    "fundamental": state.fundamental_analysis,
                    "sentiment": state.sentiment_analysis,
                    "macro": state.macro_analysis,
                    "bull": {"thesis": state.bull_thesis, "confidence": state.bull_confidence},
                    "bear": {"thesis": state.bear_thesis, "confidence": state.bear_confidence}
                },
                "portfolio_manager_reasoning": {
                    "final_decision": signal_str,
                    "position_size": quantity
                }
            }
            
            try:
                self.trades_collection.insert_one(trade_doc)
            except Exception as e:
                logger.error(f"Error storing trade in MongoDB: {e}")
            
            explanation = f"Order executed: {signal_str} {quantity} @ {state.filled_price}, "
            explanation += f"order_id={state.order_id}"
            
            self.update_state(state, order_result, explanation)
            
        except Exception as e:
            logger.error(f"Error in order execution: {e}")
            output = {
                "error": str(e),
                "status": "FAILED"
            }
            self.update_state(state, output, f"Error: {e}")
        
        return state

