"""MongoDB-based stores for user data persistence."""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from decimal import Decimal

from .contracts import (
    UserAccount, AccountBalance, Position, Trade, PortfolioSummary,
    UserStore, PortfolioStore, TradeStore
)

logger = logging.getLogger(__name__)


class MongoUserStore(UserStore):
    """MongoDB implementation of UserStore."""

    def __init__(self, mongo_client):
        self.db = mongo_client.zerodha_trading
        self.users_collection = self.db.users
        self.balances_collection = self.db.user_balances

    async def create_user(self, user: UserAccount) -> bool:
        """Create new user account."""
        try:
            user_dict = {
                "_id": user.user_id,
                "email": user.email,
                "full_name": user.full_name,
                "created_at": user.created_at,
                "is_active": user.is_active,
                "risk_profile": user.risk_profile,
                "max_daily_loss_pct": user.max_daily_loss_pct,
                "max_position_size_pct": user.max_position_size_pct,
                "preferences": user.preferences or {}
            }

            result = await self.users_collection.insert_one(user_dict)

            # Initialize balance
            balance = AccountBalance(
                user_id=user.user_id,
                cash_balance=Decimal("100000.00"),  # Default starting balance
                margin_available=Decimal("50000.00"),
                margin_used=Decimal("0.00"),
                total_equity=Decimal("100000.00"),
                day_pnl=Decimal("0.00"),
                total_pnl=Decimal("0.00"),
                last_updated=datetime.utcnow()
            )
            await self.update_balance(user.user_id, balance)

            return result.acknowledged
        except Exception as e:
            logger.error(f"Failed to create user {user.user_id}: {e}")
            return False

    async def get_user(self, user_id: str) -> Optional[UserAccount]:
        """Get user account by ID."""
        try:
            user_doc = await self.users_collection.find_one({"_id": user_id})
            if not user_doc:
                return None

            return UserAccount(
                user_id=user_doc["_id"],
                email=user_doc["email"],
                full_name=user_doc["full_name"],
                created_at=user_doc["created_at"],
                is_active=user_doc.get("is_active", True),
                risk_profile=user_doc.get("risk_profile", "moderate"),
                max_daily_loss_pct=user_doc.get("max_daily_loss_pct", 5.0),
                max_position_size_pct=user_doc.get("max_position_size_pct", 10.0),
                preferences=user_doc.get("preferences", {})
            )
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None

    async def update_user(self, user: UserAccount) -> bool:
        """Update user account."""
        try:
            user_dict = {
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "risk_profile": user.risk_profile,
                "max_daily_loss_pct": user.max_daily_loss_pct,
                "max_position_size_pct": user.max_position_size_pct,
                "preferences": user.preferences or {}
            }

            result = await self.users_collection.update_one(
                {"_id": user.user_id},
                {"$set": user_dict}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update user {user.user_id}: {e}")
            return False

    async def get_user_balance(self, user_id: str) -> Optional[AccountBalance]:
        """Get user account balance."""
        try:
            balance_doc = await self.balances_collection.find_one({"user_id": user_id})
            if not balance_doc:
                return None

            return AccountBalance(
                user_id=balance_doc["user_id"],
                cash_balance=Decimal(str(balance_doc["cash_balance"])),
                margin_available=Decimal(str(balance_doc["margin_available"])),
                margin_used=Decimal(str(balance_doc["margin_used"])),
                total_equity=Decimal(str(balance_doc["total_equity"])),
                day_pnl=Decimal(str(balance_doc["day_pnl"])),
                total_pnl=Decimal(str(balance_doc["total_pnl"])),
                last_updated=balance_doc["last_updated"]
            )
        except Exception as e:
            logger.error(f"Failed to get balance for user {user_id}: {e}")
            return None

    async def update_balance(self, user_id: str, balance: AccountBalance) -> bool:
        """Update user account balance."""
        try:
            balance_dict = {
                "user_id": user_id,
                "cash_balance": float(balance.cash_balance),
                "margin_available": float(balance.margin_available),
                "margin_used": float(balance.margin_used),
                "total_equity": float(balance.total_equity),
                "day_pnl": float(balance.day_pnl),
                "total_pnl": float(balance.total_pnl),
                "last_updated": balance.last_updated
            }

            result = await self.balances_collection.replace_one(
                {"user_id": user_id},
                balance_dict,
                upsert=True
            )
            return result.acknowledged
        except Exception as e:
            logger.error(f"Failed to update balance for user {user_id}: {e}")
            return False


class MongoPortfolioStore(PortfolioStore):
    """MongoDB implementation of PortfolioStore."""

    def __init__(self, mongo_client):
        self.db = mongo_client.zerodha_trading
        self.positions_collection = self.db.positions

    async def add_position(self, position: Position) -> bool:
        """Add or update position."""
        try:
            position_dict = {
                "user_id": position.user_id,
                "instrument": position.instrument,
                "instrument_type": position.instrument_type,
                "quantity": position.quantity,
                "average_price": float(position.average_price),
                "current_price": float(position.current_price) if position.current_price else None,
                "market_value": float(position.market_value) if position.market_value else None,
                "unrealized_pnl": float(position.unrealized_pnl) if position.unrealized_pnl else None,
                "realized_pnl": float(position.realized_pnl),
                "last_updated": position.last_updated,
                "strike_price": float(position.strike_price) if position.strike_price else None,
                "expiry_date": position.expiry_date,
                "option_type": position.option_type
            }

            result = await self.positions_collection.replace_one(
                {"user_id": position.user_id, "instrument": position.instrument},
                position_dict,
                upsert=True
            )
            return result.acknowledged
        except Exception as e:
            logger.error(f"Failed to add position for user {position.user_id}: {e}")
            return False

    async def get_position(self, user_id: str, instrument: str) -> Optional[Position]:
        """Get position for user and instrument."""
        try:
            pos_doc = await self.positions_collection.find_one({
                "user_id": user_id,
                "instrument": instrument
            })
            if not pos_doc:
                return None

            return Position(
                user_id=pos_doc["user_id"],
                instrument=pos_doc["instrument"],
                instrument_type=pos_doc["instrument_type"],
                quantity=pos_doc["quantity"],
                average_price=Decimal(str(pos_doc["average_price"])),
                current_price=Decimal(str(pos_doc["current_price"])) if pos_doc.get("current_price") else None,
                market_value=Decimal(str(pos_doc["market_value"])) if pos_doc.get("market_value") else None,
                unrealized_pnl=Decimal(str(pos_doc["unrealized_pnl"])) if pos_doc.get("unrealized_pnl") else None,
                realized_pnl=Decimal(str(pos_doc["realized_pnl"])),
                last_updated=pos_doc["last_updated"],
                strike_price=Decimal(str(pos_doc["strike_price"])) if pos_doc.get("strike_price") else None,
                expiry_date=pos_doc.get("expiry_date"),
                option_type=pos_doc.get("option_type")
            )
        except Exception as e:
            logger.error(f"Failed to get position for user {user_id}, instrument {instrument}: {e}")
            return None

    async def get_user_positions(self, user_id: str) -> List[Position]:
        """Get all positions for user."""
        try:
            positions = []
            async for pos_doc in self.positions_collection.find({"user_id": user_id}):
                position = Position(
                    user_id=pos_doc["user_id"],
                    instrument=pos_doc["instrument"],
                    instrument_type=pos_doc["instrument_type"],
                    quantity=pos_doc["quantity"],
                    average_price=Decimal(str(pos_doc["average_price"])),
                    current_price=Decimal(str(pos_doc["current_price"])) if pos_doc.get("current_price") else None,
                    market_value=Decimal(str(pos_doc["market_value"])) if pos_doc.get("market_value") else None,
                    unrealized_pnl=Decimal(str(pos_doc["unrealized_pnl"])) if pos_doc.get("unrealized_pnl") else None,
                    realized_pnl=Decimal(str(pos_doc["realized_pnl"])),
                    last_updated=pos_doc["last_updated"],
                    strike_price=Decimal(str(pos_doc["strike_price"])) if pos_doc.get("strike_price") else None,
                    expiry_date=pos_doc.get("expiry_date"),
                    option_type=pos_doc.get("option_type")
                )
                positions.append(position)

            return positions
        except Exception as e:
            logger.error(f"Failed to get positions for user {user_id}: {e}")
            return []

    async def update_position(self, position: Position) -> bool:
        """Update existing position."""
        return await self.add_position(position)

    async def close_position(self, user_id: str, instrument: str) -> bool:
        """Close position (set quantity to 0)."""
        try:
            # Get current position
            position = await self.get_position(user_id, instrument)
            if not position:
                return True  # Position already closed

            # Set quantity to 0 and update timestamps
            position.quantity = 0
            position.last_updated = datetime.utcnow()

            return await self.update_position(position)
        except Exception as e:
            logger.error(f"Failed to close position for user {user_id}, instrument {instrument}: {e}")
            return False

    async def get_portfolio_summary(self, user_id: str) -> PortfolioSummary:
        """Get portfolio summary for user."""
        try:
            positions = await self.get_user_positions(user_id)

            total_value = Decimal("0")
            winning_positions = 0
            losing_positions = 0

            for position in positions:
                if position.market_value:
                    total_value += position.market_value
                if position.unrealized_pnl:
                    if position.unrealized_pnl > 0:
                        winning_positions += 1
                    elif position.unrealized_pnl < 0:
                        losing_positions += 1

            # This would need to be enhanced with actual balance data
            # For now, return basic summary
            return PortfolioSummary(
                user_id=user_id,
                total_value=total_value,
                cash_balance=Decimal("0"),  # Would need balance integration
                margin_available=Decimal("0"),
                day_pnl=Decimal("0"),
                total_pnl=Decimal("0"),
                positions_count=len(positions),
                winning_positions=winning_positions,
                losing_positions=losing_positions,
                risk_exposure_pct=0.0,  # Would need risk calculation
                last_updated=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Failed to get portfolio summary for user {user_id}: {e}")
            return PortfolioSummary(
                user_id=user_id,
                total_value=Decimal("0"),
                cash_balance=Decimal("0"),
                margin_available=Decimal("0"),
                day_pnl=Decimal("0"),
                total_pnl=Decimal("0"),
                positions_count=0,
                winning_positions=0,
                losing_positions=0,
                risk_exposure_pct=0.0,
                last_updated=datetime.utcnow()
            )


class MongoTradeStore(TradeStore):
    """MongoDB implementation of TradeStore."""

    def __init__(self, mongo_client):
        self.db = mongo_client.zerodha_trading
        self.trades_collection = self.db.trades

    async def record_trade(self, trade: Trade) -> bool:
        """Record executed trade."""
        try:
            trade_dict = {
                "_id": trade.trade_id,
                "user_id": trade.user_id,
                "order_id": trade.order_id,
                "instrument": trade.instrument,
                "side": trade.side,
                "quantity": trade.quantity,
                "price": float(trade.price),
                "order_type": trade.order_type,
                "timestamp": trade.timestamp.isoformat() if hasattr(trade.timestamp, 'isoformat') else str(trade.timestamp),
                "status": trade.status,
                "broker_fees": float(trade.broker_fees),
                "exchange_fees": float(trade.exchange_fees),
                "strike_price": float(trade.strike_price) if trade.strike_price else None,
                "expiry_date": trade.expiry_date.isoformat() if trade.expiry_date and hasattr(trade.expiry_date, 'isoformat') else trade.expiry_date,
                "option_type": trade.option_type,
                "stop_loss_price": float(trade.stop_loss_price) if trade.stop_loss_price else None,
                "take_profit_price": float(trade.take_profit_price) if trade.take_profit_price else None,
                "risk_amount": float(trade.risk_amount) if trade.risk_amount else None
            }

            result = await self.trades_collection.insert_one(trade_dict)
            return result.acknowledged
        except Exception as e:
            logger.error(f"Failed to record trade {trade.trade_id}: {e}")
            return False

    async def get_trade(self, trade_id: str) -> Optional[Trade]:
        """Get trade by ID."""
        try:
            trade_doc = await self.trades_collection.find_one({"_id": trade_id})
            if not trade_doc:
                return None

            return Trade(
                user_id=trade_doc["user_id"],
                trade_id=trade_doc["_id"],
                order_id=trade_doc["order_id"],
                instrument=trade_doc["instrument"],
                side=trade_doc["side"],
                quantity=trade_doc["quantity"],
                price=Decimal(str(trade_doc["price"])),
                order_type=trade_doc["order_type"],
                timestamp=trade_doc["timestamp"],
                status=trade_doc["status"],
                broker_fees=Decimal(str(trade_doc["broker_fees"])),
                exchange_fees=Decimal(str(trade_doc["exchange_fees"])),
                strike_price=Decimal(str(trade_doc["strike_price"])) if trade_doc.get("strike_price") else None,
                expiry_date=trade_doc.get("expiry_date"),
                option_type=trade_doc.get("option_type"),
                stop_loss_price=Decimal(str(trade_doc["stop_loss_price"])) if trade_doc.get("stop_loss_price") else None,
                take_profit_price=Decimal(str(trade_doc["take_profit_price"])) if trade_doc.get("take_profit_price") else None,
                risk_amount=Decimal(str(trade_doc["risk_amount"])) if trade_doc.get("risk_amount") else None
            )
        except Exception as e:
            logger.error(f"Failed to get trade {trade_id}: {e}")
            return None

    async def get_user_trades(self, user_id: str, limit: int = 100) -> List[Trade]:
        """Get recent trades for user."""
        try:
            trades = []
            async for trade_doc in self.trades_collection.find(
                {"user_id": user_id}
            ).sort("timestamp", -1).limit(limit):

                trade = Trade(
                    user_id=trade_doc["user_id"],
                    trade_id=trade_doc["_id"],
                    order_id=trade_doc["order_id"],
                    instrument=trade_doc["instrument"],
                    side=trade_doc["side"],
                    quantity=trade_doc["quantity"],
                    price=Decimal(str(trade_doc["price"])),
                    order_type=trade_doc["order_type"],
                    timestamp=trade_doc["timestamp"],
                    status=trade_doc["status"],
                    broker_fees=Decimal(str(trade_doc["broker_fees"])),
                    exchange_fees=Decimal(str(trade_doc["exchange_fees"])),
                    strike_price=Decimal(str(trade_doc["strike_price"])) if trade_doc.get("strike_price") else None,
                    expiry_date=trade_doc.get("expiry_date"),
                    option_type=trade_doc.get("option_type"),
                    stop_loss_price=Decimal(str(trade_doc["stop_loss_price"])) if trade_doc.get("stop_loss_price") else None,
                    take_profit_price=Decimal(str(trade_doc["take_profit_price"])) if trade_doc.get("take_profit_price") else None,
                    risk_amount=Decimal(str(trade_doc["risk_amount"])) if trade_doc.get("risk_amount") else None
                )
                trades.append(trade)

            return trades
        except Exception as e:
            logger.error(f"Failed to get trades for user {user_id}: {e}")
            return []

    async def get_trades_by_instrument(self, user_id: str, instrument: str) -> List[Trade]:
        """Get trades for specific instrument."""
        try:
            trades = []
            async for trade_doc in self.trades_collection.find({
                "user_id": user_id,
                "instrument": instrument
            }).sort("timestamp", -1):

                trade = await self._doc_to_trade(trade_doc)
                trades.append(trade)

            return trades
        except Exception as e:
            logger.error(f"Failed to get trades for user {user_id}, instrument {instrument}: {e}")
            return []

    async def get_trades_in_date_range(self, user_id: str, start_date: datetime,
                                     end_date: datetime) -> List[Trade]:
        """Get trades within date range."""
        try:
            trades = []
            async for trade_doc in self.trades_collection.find({
                "user_id": user_id,
                "timestamp": {"$gte": start_date, "$lte": end_date}
            }).sort("timestamp", -1):

                trade = await self._doc_to_trade(trade_doc)
                trades.append(trade)

            return trades
        except Exception as e:
            logger.error(f"Failed to get trades for user {user_id} in date range: {e}")
            return []

    async def _doc_to_trade(self, trade_doc) -> Trade:
        """Convert MongoDB document to Trade object."""
        return Trade(
            user_id=trade_doc["user_id"],
            trade_id=trade_doc["_id"],
            order_id=trade_doc["order_id"],
            instrument=trade_doc["instrument"],
            side=trade_doc["side"],
            quantity=trade_doc["quantity"],
            price=Decimal(str(trade_doc["price"])),
            order_type=trade_doc["order_type"],
            timestamp=trade_doc["timestamp"],
            status=trade_doc["status"],
            broker_fees=Decimal(str(trade_doc["broker_fees"])),
            exchange_fees=Decimal(str(trade_doc["exchange_fees"])),
            strike_price=Decimal(str(trade_doc["strike_price"])) if trade_doc.get("strike_price") else None,
            expiry_date=trade_doc.get("expiry_date"),
            option_type=trade_doc.get("option_type"),
            stop_loss_price=Decimal(str(trade_doc["stop_loss_price"])) if trade_doc.get("stop_loss_price") else None,
            take_profit_price=Decimal(str(trade_doc["take_profit_price"])) if trade_doc.get("take_profit_price") else None,
            risk_amount=Decimal(str(trade_doc["risk_amount"])) if trade_doc.get("risk_amount") else None
        )


__all__ = [
    "MongoUserStore",
    "MongoPortfolioStore",
    "MongoTradeStore",
]

