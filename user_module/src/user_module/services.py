"""User module services for risk management and trade execution."""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from decimal import Decimal

from .contracts import (
    TradeExecutionRequest, TradeExecutionResult, RiskManager, TradeExecutor,
    PnLAnalytics, UserAccount, Position, Trade
)
from .stores import UserStore, PortfolioStore, TradeStore

logger = logging.getLogger(__name__)


class RiskProfileManager:
    """Manages user risk profiles and position sizing."""

    def __init__(self, user_store: UserStore):
        self.user_store = user_store

        # Risk profile configurations
        self.risk_profiles = {
            "conservative": {
                "max_daily_loss_pct": 2.0,
                "max_position_size_pct": 5.0,
                "max_sector_exposure_pct": 20.0,
                "max_single_stock_pct": 2.0,
                "max_options_exposure_pct": 10.0,
                "required_risk_reward_ratio": 1.5,
                "max_open_positions": 5,
                "max_leverage": 1.0,
                "stop_loss_required": True,
                "diversification_required": True
            },
            "moderate": {
                "max_daily_loss_pct": 5.0,
                "max_position_size_pct": 10.0,
                "max_sector_exposure_pct": 30.0,
                "max_single_stock_pct": 5.0,
                "max_options_exposure_pct": 20.0,
                "required_risk_reward_ratio": 2.0,
                "max_open_positions": 10,
                "max_leverage": 2.0,
                "stop_loss_required": True,
                "diversification_required": False
            },
            "aggressive": {
                "max_daily_loss_pct": 10.0,
                "max_position_size_pct": 20.0,
                "max_sector_exposure_pct": 50.0,
                "max_single_stock_pct": 10.0,
                "max_options_exposure_pct": 40.0,
                "required_risk_reward_ratio": 3.0,
                "max_open_positions": 20,
                "max_leverage": 5.0,
                "stop_loss_required": False,
                "diversification_required": False
            }
        }

    def get_risk_profile(self, profile_name: str) -> Dict[str, Any]:
        """Get risk profile configuration."""
        return self.risk_profiles.get(profile_name, self.risk_profiles["moderate"])

    async def calculate_position_size(self, user_id: str, instrument: str,
                                    entry_price: Decimal, stop_loss_price: Optional[Decimal],
                                    account_balance: Decimal) -> int:
        """Calculate position size based on user risk profile."""
        try:
            user = await self.user_store.get_user(user_id)
            if not user:
                return 0

            risk_profile = self.get_risk_profile(user.risk_profile)

            # Maximum position size as percentage of account
            max_position_value = account_balance * Decimal(str(risk_profile["max_position_size_pct"] / 100))

            if stop_loss_price:
                # Calculate risk per share
                risk_per_share = abs(entry_price - stop_loss_price)
                if risk_per_share > 0:
                    # Risk no more than 1% of account per position
                    max_risk_per_position = account_balance * Decimal("0.01")
                    position_size = int(max_risk_per_position / risk_per_share)

                    # Cap at maximum position size limit
                    max_shares = int(max_position_value / entry_price)
                    position_size = min(position_size, max_shares)

                    return max(1, position_size)

            # No stop loss - use conservative sizing
            return max(1, int(max_position_value / entry_price))

        except Exception as e:
            logger.error(f"Failed to calculate position size for user {user_id}: {e}")
            return 1  # Minimum position size


class PortfolioRiskManager(RiskManager):
    """Risk management for portfolio and position validation."""

    def __init__(self, user_store: UserStore, portfolio_store: PortfolioStore,
                 risk_profile_manager: RiskProfileManager):
        self.user_store = user_store
        self.portfolio_store = portfolio_store
        self.risk_manager = risk_profile_manager

    async def validate_trade_risk(self, user_id: str, trade_request: TradeExecutionRequest) -> Dict[str, Any]:
        """Validate if trade meets risk criteria."""
        try:
            user = await self.user_store.get_user(user_id)
            if not user:
                return {"approved": False, "reasons": ["User not found"]}

            balance = await self.user_store.get_user_balance(user_id)
            if not balance:
                return {"approved": False, "reasons": ["Account balance not found"]}

            reasons = []
            risk_profile = self.risk_manager.get_risk_profile(user.risk_profile)

            # Check daily loss limit
            if balance.day_pnl < -balance.total_equity * Decimal(str(risk_profile["max_daily_loss_pct"] / 100)):
                reasons.append("Daily loss limit exceeded")

            # Check position count limit
            positions = await self.portfolio_store.get_user_positions(user_id)
            if len(positions) >= risk_profile["max_open_positions"]:
                reasons.append("Maximum open positions limit reached")

            # Check position size limit
            if trade_request.quantity > 0:
                position_value = trade_request.price * trade_request.quantity
                max_position_value = balance.total_equity * Decimal(str(risk_profile["max_position_size_pct"] / 100))
                if position_value > max_position_value:
                    reasons.append("Position size exceeds limit")

            # Check stop loss requirement
            if risk_profile["stop_loss_required"] and not trade_request.stop_loss_price:
                reasons.append("Stop loss required for risk profile")

            # Check risk-reward ratio
            if (trade_request.stop_loss_price and trade_request.take_profit_price):
                risk = abs(trade_request.price - trade_request.stop_loss_price)
                reward = abs(trade_request.take_profit_price - trade_request.price)
                if reward / risk < risk_profile["required_risk_reward_ratio"]:
                    reasons.append("Risk-reward ratio too low")

            return {
                "approved": len(reasons) == 0,
                "reasons": reasons
            }

        except Exception as e:
            logger.error(f"Failed to validate trade risk for user {user_id}: {e}")
            return {"approved": False, "reasons": ["Risk validation failed"]}

    async def calculate_position_size(self, user_id: str, instrument: str,
                                    risk_amount: Decimal, stop_loss_price: Decimal) -> int:
        """Calculate position size based on risk management rules."""
        try:
            user = await self.user_store.get_user(user_id)
            balance = await self.user_store.get_user_balance(user_id)

            if not user or not balance:
                return 0

            entry_price = stop_loss_price + (risk_amount / Decimal("1"))  # Simplified
            return await self.risk_manager.calculate_position_size(
                user_id, instrument, entry_price, stop_loss_price, balance.total_equity
            )

        except Exception as e:
            logger.error(f"Failed to calculate position size for user {user_id}: {e}")
            return 0

    async def check_portfolio_risk_limits(self, user_id: str) -> Dict[str, Any]:
        """Check if portfolio meets risk limits."""
        try:
            user = await self.user_store.get_user(user_id)
            positions = await self.portfolio_store.get_user_positions(user_id)
            balance = await self.user_store.get_user_balance(user_id)

            if not user or not balance:
                return {"compliant": False, "violations": ["User or balance data missing"]}

            violations = []
            risk_profile = self.risk_manager.get_risk_profile(user.risk_profile)

            # Check daily loss limit
            daily_loss_pct = abs(balance.day_pnl / balance.total_equity) * 100
            if daily_loss_pct > risk_profile["max_daily_loss_pct"]:
                violations.append(f"Daily loss {daily_loss_pct:.1f}% exceeds limit {risk_profile['max_daily_loss_pct']}%")

            # Check position count
            if len(positions) > risk_profile["max_open_positions"]:
                violations.append(f"Open positions {len(positions)} exceeds limit {risk_profile['max_open_positions']}")

            # Check concentration risk
            total_exposure = sum((p.market_value or 0) for p in positions)
            for position in positions:
                if position.market_value and total_exposure > 0:
                    exposure_pct = (position.market_value / total_exposure) * 100
                    if exposure_pct > risk_profile["max_single_stock_pct"]:
                        violations.append(f"Position {position.instrument} exposure {exposure_pct:.1f}% exceeds limit")

            return {
                "compliant": len(violations) == 0,
                "violations": violations
            }

        except Exception as e:
            logger.error(f"Failed to check portfolio risk limits for user {user_id}: {e}")
            return {"compliant": False, "violations": ["Risk check failed"]}


class MockTradeExecutor(TradeExecutor):
    """Mock trade executor for testing and development."""

    def __init__(self):
        self.executed_trades = []
        self.pending_orders = {}

    async def execute_trade(self, trade_request: TradeExecutionRequest) -> TradeExecutionResult:
        """Mock trade execution - simulates successful execution."""
        try:
            # Simulate execution delay
            import asyncio
            await asyncio.sleep(0.1)

            # Generate mock execution
            executed_price = trade_request.price or Decimal("45000.00")  # Mock NIFTY price
            trade_id = f"trade_{trade_request.user_id}_{datetime.utcnow().timestamp()}"
            order_id = f"order_{trade_request.user_id}_{datetime.utcnow().timestamp()}"

            # Record the execution
            self.executed_trades.append({
                "trade_id": trade_id,
                "request": trade_request,
                "executed_price": executed_price,
                "timestamp": datetime.utcnow()
            })

            logger.info(f"Mock executed trade: {trade_request.side} {trade_request.quantity} {trade_request.instrument} @ {executed_price}")

            return TradeExecutionResult(
                success=True,
                trade_id=trade_id,
                order_id=order_id,
                executed_price=executed_price,
                executed_quantity=trade_request.quantity,
                message="Trade executed successfully (mock)"
            )

        except Exception as e:
            logger.error(f"Mock trade execution failed: {e}")
            return TradeExecutionResult(
                success=False,
                message=f"Trade execution failed: {str(e)}",
                error_code="EXECUTION_FAILED"
            )

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get status of pending order."""
        if order_id in self.pending_orders:
            return self.pending_orders[order_id]
        return {"status": "unknown", "message": "Order not found"}

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel pending order."""
        if order_id in self.pending_orders:
            self.pending_orders[order_id]["status"] = "cancelled"
            return True
        return False


class BasicPnLAnalytics(PnLAnalytics):
    """Basic P&L analytics implementation."""

    def __init__(self, trade_store: TradeStore, portfolio_store: PortfolioStore):
        self.trade_store = trade_store
        self.portfolio_store = portfolio_store

    async def calculate_realized_pnl(self, user_id: str, start_date: datetime,
                                   end_date: datetime) -> Decimal:
        """Calculate realized P&L for date range."""
        try:
            trades = await self.trade_store.get_trades_in_date_range(user_id, start_date, end_date)

            total_pnl = Decimal("0")
            position_tracker = {}  # instrument -> position info

            for trade in trades:
                if trade.status != "EXECUTED":
                    continue

                instrument = trade.instrument
                if instrument not in position_tracker:
                    position_tracker[instrument] = {"quantity": 0, "cost": Decimal("0")}

                pos = position_tracker[instrument]

                if trade.side == "BUY":
                    # Add to position
                    total_cost = pos["cost"] + (trade.price * trade.quantity)
                    total_quantity = pos["quantity"] + trade.quantity
                    pos["cost"] = total_cost
                    pos["quantity"] = total_quantity
                else:  # SELL
                    if pos["quantity"] > 0:
                        # Calculate realized P&L
                        avg_cost = pos["cost"] / pos["quantity"]
                        realized = (trade.price - avg_cost) * min(trade.quantity, pos["quantity"])
                        total_pnl += realized

                        # Update position
                        pos["quantity"] -= trade.quantity
                        pos["cost"] = avg_cost * pos["quantity"] if pos["quantity"] > 0 else Decimal("0")

            return total_pnl

        except Exception as e:
            logger.error(f"Failed to calculate realized P&L for user {user_id}: {e}")
            return Decimal("0")

    async def calculate_unrealized_pnl(self, user_id: str) -> Decimal:
        """Calculate unrealized P&L from current positions."""
        try:
            positions = await self.portfolio_store.get_user_positions(user_id)

            total_unrealized = Decimal("0")
            for position in positions:
                if position.unrealized_pnl:
                    total_unrealized += position.unrealized_pnl

            return total_unrealized

        except Exception as e:
            logger.error(f"Failed to calculate unrealized P&L for user {user_id}: {e}")
            return Decimal("0")

    async def get_performance_metrics(self, user_id: str, timeframe: str = "1M") -> Dict[str, Any]:
        """Get performance metrics."""
        try:
            # This is a simplified implementation
            # Real implementation would calculate Sharpe ratio, win rate, etc.
            return {
                "total_return_pct": 0.0,
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
                "max_drawdown_pct": 0.0,
                "volatility": 0.0,
                "timeframe": timeframe
            }
        except Exception as e:
            logger.error(f"Failed to get performance metrics for user {user_id}: {e}")
            return {}

    async def get_trade_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get trading statistics."""
        try:
            trades = await self.trade_store.get_user_trades(user_id, limit=1000)

            if not trades:
                return {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate": 0.0,
                    "avg_profit": 0.0,
                    "avg_loss": 0.0,
                    "profit_factor": 0.0
                }

            # This is a simplified calculation
            # Real implementation would properly calculate P&L per trade
            return {
                "total_trades": len(trades),
                "winning_trades": 0,  # Would need P&L calculation
                "losing_trades": 0,
                "win_rate": 0.0,
                "avg_profit": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0
            }

        except Exception as e:
            logger.error(f"Failed to get trade statistics for user {user_id}: {e}")
            return {}


__all__ = [
    "RiskProfileManager",
    "PortfolioRiskManager",
    "MockTradeExecutor",
    "BasicPnLAnalytics",
]
