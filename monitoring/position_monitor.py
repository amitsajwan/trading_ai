"""Continuous position monitoring service for auto-exit on SL/target."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from kiteconnect import KiteConnect
from data.market_memory import MarketMemory
from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings
from monitoring.alerts import AlertSystem
from utils.paper_trading import PaperTrading

logger = logging.getLogger(__name__)


class PositionMonitor:
    """Continuous position monitoring service that checks open positions and auto-exits on SL/target."""
    
    def __init__(self, kite: Optional[KiteConnect] = None, market_memory: Optional[MarketMemory] = None, 
                 paper_trading: Optional[PaperTrading] = None):
        """Initialize position monitor."""
        self.kite = kite
        self.market_memory = market_memory
        self.paper_trading = paper_trading
        self.running = False
        self.check_interval = 0.1  # 100ms
        
        # MongoDB connection
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.trades_collection = get_collection(self.db, "trades_executed")
        
        # Alert system
        self.alert_system = AlertSystem()
        
        # Track positions being monitored
        self.monitored_positions: Dict[str, Dict[str, Any]] = {}
    
    async def start(self):
        """Start the position monitoring loop."""
        if self.running:
            logger.warning("Position monitor already running")
            return
        
        self.running = True
        logger.info("Starting position monitoring service...")
        
        try:
            while self.running:
                await self._monitor_positions()
                await asyncio.sleep(self.check_interval)
        except asyncio.CancelledError:
            logger.info("Position monitoring cancelled")
        except Exception as e:
            logger.error(f"Error in position monitoring loop: {e}", exc_info=True)
        finally:
            self.running = False
    
    def stop(self):
        """Stop the position monitoring loop."""
        self.running = False
        logger.info("Position monitoring stopped")
    
    async def _monitor_positions(self):
        """Monitor all open positions."""
        try:
            # Get open positions from MongoDB
            open_positions = list(self.trades_collection.find({
                "status": "OPEN"
            }))
            
            if not open_positions:
                return
            
            # Get current price
            current_price = None
            if self.market_memory:
                current_price = self.market_memory.get_current_price("BANKNIFTY")
            
            if not current_price:
                # Try to get from Kite if available
                if self.kite:
                    try:
                        # Get instrument LTP
                        instrument_token = self._get_instrument_token()
                        if instrument_token:
                            ltp_data = self.kite.ltp([f"{settings.instrument_exchange}:{settings.instrument_symbol}"])
                            if ltp_data:
                                current_price = list(ltp_data.values())[0].get("last_price")
                    except Exception as e:
                        logger.warning(f"Could not get current price from Kite: {e}")
            
            if not current_price:
                logger.warning("Could not get current price, skipping position check")
                return
            
            # Check each open position
            for position in open_positions:
                await self._check_position(position, current_price)
                
        except Exception as e:
            logger.error(f"Error monitoring positions: {e}", exc_info=True)
    
    async def _check_position(self, position: Dict[str, Any], current_price: float):
        """Check a single position for SL/target hit."""
        trade_id = position.get("trade_id")
        signal = position.get("signal")
        entry_price = position.get("entry_price") or position.get("filled_price")
        stop_loss = position.get("stop_loss")
        take_profit = position.get("take_profit")
        paper_trading = position.get("paper_trading", False)
        
        if not all([trade_id, signal, entry_price, stop_loss, take_profit]):
            logger.warning(f"Incomplete position data for {trade_id}")
            return
        
        # Check if SL or target hit
        should_exit = False
        exit_reason = None
        exit_price = current_price
        
        if signal == "BUY":
            if current_price <= stop_loss:
                should_exit = True
                exit_reason = "STOP_LOSS"
                exit_price = stop_loss  # Use SL price for better execution
            elif current_price >= take_profit:
                should_exit = True
                exit_reason = "TAKE_PROFIT"
                exit_price = take_profit  # Use target price
        elif signal == "SELL":
            if current_price >= stop_loss:
                should_exit = True
                exit_reason = "STOP_LOSS"
                exit_price = stop_loss
            elif current_price <= take_profit:
                should_exit = True
                exit_reason = "TAKE_PROFIT"
                exit_price = take_profit
        
        if should_exit:
            await self._exit_position(position, exit_price, exit_reason, paper_trading)
    
    async def _exit_position(self, position: Dict[str, Any], exit_price: float, 
                            reason: str, paper_trading: bool):
        """Exit a position."""
        trade_id = position.get("trade_id")
        signal = position.get("signal")
        quantity = position.get("quantity") or position.get("filled_quantity")
        entry_price = position.get("entry_price") or position.get("filled_price")
        
        logger.info(f"Exiting position {trade_id}: {reason} @ {exit_price}")
        
        try:
            # Calculate P&L
            if signal == "BUY":
                pnl = (exit_price - entry_price) * quantity
            else:  # SELL
                pnl = (entry_price - exit_price) * quantity
            
            pnl_percent = (pnl / (entry_price * quantity)) * 100 if entry_price and quantity else 0
            
            # Handle exit based on trading mode
            if paper_trading and self.paper_trading:
                # Paper trading exit
                result = self.paper_trading.close_position(trade_id, exit_price, reason)
                if result.get("status") == "NOT_FOUND":
                    # Position not in memory, update MongoDB directly
                    logger.info(f"Position {trade_id} not in memory, updating MongoDB directly")
                    self.trades_collection.update_one(
                        {"trade_id": trade_id},
                        {"$set": {
                            "exit_price": exit_price,
                            "exit_timestamp": datetime.now().isoformat(),
                            "status": "CLOSED",
                            "exit_reason": reason,
                            "pnl": pnl,
                            "pnl_percent": pnl_percent
                        }}
                    )
                elif result.get("status") != "CLOSED":
                    logger.warning(f"Failed to close paper position {trade_id}: {result}")
                    return
            elif self.kite:
                # Live trading exit - place market order
                try:
                    transaction_type = (
                        self.kite.TRANSACTION_TYPE_SELL if signal == "BUY"
                        else self.kite.TRANSACTION_TYPE_BUY
                    )
                    
                    order_id = self.kite.place_order(
                        variety=self.kite.VARIETY_REGULAR,
                        exchange=settings.instrument_exchange,
                        tradingsymbol=settings.instrument_symbol,
                        transaction_type=transaction_type,
                        quantity=quantity,
                        product=self.kite.PRODUCT_MIS,
                        order_type=self.kite.ORDER_TYPE_MARKET
                    )
                    
                    logger.info(f"Exit order placed: {order_id} for {trade_id}")
                except Exception as e:
                    logger.error(f"Error placing exit order for {trade_id}: {e}")
                    # Still update MongoDB with exit price
            
            # Update MongoDB
            update_doc = {
                "status": "CLOSED",
                "exit_price": exit_price,
                "exit_timestamp": datetime.now().isoformat(),
                "pnl": pnl,
                "pnl_percent": pnl_percent,
                "exit_reason": reason
            }
            
            self.trades_collection.update_one(
                {"trade_id": trade_id},
                {"$set": update_doc}
            )
            
            # Send alert
            await self.alert_system.send_slack_alert(
                f"Position closed: {trade_id} | {reason} | P&L: ₹{pnl:.2f} ({pnl_percent:.2f}%)",
                "INFO"
            )
            
            logger.info(f"Position {trade_id} closed: P&L={pnl:.2f}, reason={reason}")
            
        except Exception as e:
            logger.error(f"Error exiting position {trade_id}: {e}", exc_info=True)
    
    def _get_instrument_token(self) -> Optional[int]:
        """Get instrument token for configured symbol."""
        if not self.kite:
            return None
        
        try:
            instruments = self.kite.instruments(settings.instrument_exchange)
            for inst in instruments:
                if inst["tradingsymbol"] == settings.instrument_symbol:
                    return inst["instrument_token"]
        except Exception as e:
            logger.error(f"Error getting instrument token: {e}")
        
        return None
    
    def add_position_to_monitor(self, trade_id: str, position_data: Dict[str, Any]):
        """Add a position to monitoring list."""
        self.monitored_positions[trade_id] = position_data
    
    def remove_position_from_monitor(self, trade_id: str):
        """Remove a position from monitoring list."""
        if trade_id in self.monitored_positions:
            del self.monitored_positions[trade_id]

