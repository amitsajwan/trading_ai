"""Execution adapters for different trading modes (LIVE, PAPER, BACKTEST).

This module implements the execution adapter pattern as specified in the trading system specification.
Each adapter implements the same interface but behaves differently based on the trading mode.
"""

import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json

from engine_module.contracts import TradingDecision
from engine_module.services.position_manager import PositionManager
import redis

logger = logging.getLogger(__name__)

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))


class ExecutionAdapter(ABC):
    """Abstract base class for execution adapters."""

    def __init__(self, mode: str, run_id: Optional[str] = None, redis_client: Optional[redis.Redis] = None):
        self.mode = mode
        self.run_id = run_id
        self.redis_client = redis_client

    @abstractmethod
    async def execute_trading_decision(
        self,
        instrument: str,
        decision: str,
        confidence: float,
        analysis_details: Dict[str, Any],
        position_manager: Optional[PositionManager] = None
    ) -> Optional[Dict[str, Any]]:
        """Execute a trading decision based on the adapter's mode."""
        pass

    def _create_mode_aware_payload(self, instrument: str, timeframe: str = "1min") -> Dict[str, str]:
        """Create mode-aware payload for Redis messages."""
        return {
            "mode": self.mode,
            "run_id": self.run_id or "",
            "instrument": instrument,
            "timeframe": timeframe,
        }


class LiveExecutionAdapter(ExecutionAdapter):
    """Live execution adapter that places real orders via broker API."""

    def __init__(self, mode: str = "LIVE", run_id: Optional[str] = None, redis_client: Optional[redis.Redis] = None):
        super().__init__(mode, run_id, redis_client)

    async def execute_trading_decision(
        self,
        instrument: str,
        decision: str,
        confidence: float,
        analysis_details: Dict[str, Any],
        position_manager: Optional[PositionManager] = None
    ) -> Optional[Dict[str, Any]]:
        """Execute trading decision via live broker API."""
        logger.warning("LIVE MODE: Real order execution not implemented yet")
        logger.info(f"Would execute {decision} for {instrument} with confidence {confidence}")

        # TODO: Implement actual broker API integration
        # This would call the broker API to place real orders

        # For now, return None to indicate no execution
        return None


class PaperExecutionAdapter(ExecutionAdapter):
    """Paper trading adapter that simulates order execution without real orders."""

    def __init__(self, mode: str = "PAPER", run_id: Optional[str] = None, redis_client: Optional[redis.Redis] = None):
        super().__init__(mode, run_id, redis_client)

    async def execute_trading_decision(
        self,
        instrument: str,
        decision: str,
        confidence: float,
        analysis_details: Dict[str, Any],
        position_manager: Optional[PositionManager] = None
    ) -> Optional[Dict[str, Any]]:
        """Simulate trading decision execution for paper trading."""
        logger.info(f"PAPER MODE: Simulating execution of {decision} for {instrument}")

        # Simulate order execution
        current_price = analysis_details.get('current_price', 45000.0)

        # Create simulated execution result
        execution_result = {
            "instrument": instrument,
            "decision": decision,
            "executed_price": current_price,
            "quantity": analysis_details.get('quantity', 1),
            "timestamp": datetime.now(IST).isoformat(),
            "status": "EXECUTED",
            "mode": self.mode,
            "simulated": True
        }

        # Publish execution result to Redis for UI updates
        if self.redis_client:
            try:
                payload = execution_result.copy()
                payload.update(self._create_mode_aware_payload(instrument))
                self.redis_client.publish("engine:execution", json.dumps(payload))
            except Exception as e:
                logger.warning(f"Failed to publish paper execution: {e}")

        logger.info(f"PAPER MODE: Simulated execution completed for {instrument}")
        return execution_result


class BacktestExecutionAdapter(ExecutionAdapter):
    """Backtest execution adapter that simulates full trade lifecycle."""

    def __init__(
        self,
        mode: str = "BACKTEST",
        run_id: Optional[str] = None,
        redis_client: Optional[redis.Redis] = None,
        mongo_client=None
    ):
        super().__init__(mode, run_id, redis_client)
        self.mongo_client = mongo_client
        self.positions: Dict[str, Dict[str, Any]] = {}  # instrument -> position data
        self.equity_curve: List[Dict[str, Any]] = []
        self.trades: List[Dict[str, Any]] = []
        self.starting_balance = Decimal("100000.00")
        self.current_balance = self.starting_balance

        # Backtest-specific parameters
        self.brokerage_per_trade = Decimal("20.00")  # ₹20 per trade
        self.exchange_fees_pct = Decimal("0.0005")  # 0.05% exchange fees

    async def execute_trading_decision(
        self,
        instrument: str,
        decision: str,
        confidence: float,
        analysis_details: Dict[str, Any],
        position_manager: Optional[PositionManager] = None
    ) -> Optional[Dict[str, Any]]:
        """Execute trading decision in backtest simulation."""
        logger.info(f"BACKTEST MODE: Simulating {decision} for {instrument} (run_id: {self.run_id})")

        # Extract trade parameters
        current_price = analysis_details.get('current_price', 45000.0)
        quantity = analysis_details.get('quantity', 1)
        entry_price = analysis_details.get('entry_price', current_price)
        stop_loss = analysis_details.get('stop_loss_price')
        take_profit = analysis_details.get('take_profit_price')

        # Apply slippage (1% for backtesting)
        slippage = Decimal("0.01")  # 1% slippage
        # Ensure numeric types are Decimal-safe
        try:
            entry_price_dec = Decimal(str(entry_price))
        except Exception:
            entry_price_dec = Decimal(str(current_price))

        if decision.upper() == "BUY":
            executed_price = entry_price_dec * (Decimal("1.0") + slippage)
        else:  # SELL
            executed_price = entry_price_dec * (Decimal("1.0") - slippage)

        # Calculate fees
        trade_value = executed_price * Decimal(str(quantity))
        exchange_fees = trade_value * self.exchange_fees_pct
        total_fees = self.brokerage_per_trade + exchange_fees

        # Create trade record
        trade_record = {
            "run_id": self.run_id,
            "instrument": instrument,
            "side": decision.upper(),
            "quantity": quantity,
            "entry_price": float(executed_price),
            "stop_loss": float(stop_loss) if stop_loss else None,
            "take_profit": float(take_profit) if take_profit else None,
            "fees": float(total_fees),
            "timestamp": datetime.now(IST).isoformat(),
            "confidence": confidence,
            "mode": self.mode,
            "simulated": True
        }

        # Update position tracking
        await self._update_position(instrument, trade_record)

        # Record trade
        self.trades.append(trade_record)

        # Persist to MongoDB
        await self._persist_trade(trade_record)

        # Publish execution result to Redis for UI updates
        if self.redis_client:
            try:
                payload = trade_record.copy()
                payload.update(self._create_mode_aware_payload(instrument))
                self.redis_client.publish("engine:execution", json.dumps(payload))
            except Exception as e:
                logger.warning(f"Failed to publish backtest execution: {e}")

        logger.info(f"BACKTEST MODE: Executed {decision} for {instrument} @ {executed_price}")
        return trade_record

    async def _update_position(self, instrument: str, trade: Dict[str, Any]):
        """Update position tracking for backtest."""
        if instrument not in self.positions:
            self.positions[instrument] = {
                "quantity": 0,
                "avg_price": Decimal("0"),
                "total_cost": Decimal("0"),
                "fees": Decimal("0")
            }

        pos = self.positions[instrument]
        quantity = trade["quantity"]
        price = Decimal(str(trade["entry_price"]))
        fees = Decimal(str(trade["fees"]))

        if trade["side"] == "BUY":
            # Add to position
            new_total_cost = pos["total_cost"] + (price * quantity) + fees
            new_total_quantity = pos["quantity"] + quantity
            pos["avg_price"] = new_total_cost / new_total_quantity if new_total_quantity > 0 else Decimal("0")
            pos["total_cost"] = new_total_cost
            pos["quantity"] = new_total_quantity
            pos["fees"] += fees
        else:  # SELL
            if pos["quantity"] >= quantity:
                # Calculate P&L
                realized_pnl = (price - pos["avg_price"]) * quantity - fees

                # Update position
                pos["quantity"] -= quantity
                pos["total_cost"] = pos["avg_price"] * pos["quantity"] if pos["quantity"] > 0 else Decimal("0")
                pos["fees"] += fees

                # Update balance
                self.current_balance += realized_pnl

                # Record realized P&L
                trade["realized_pnl"] = float(realized_pnl)

                # Update equity curve after each trade
                await self._update_equity_curve(trade["timestamp"])
            else:
                logger.warning(f"BACKTEST: Insufficient position for {instrument} sell order")

    async def _update_equity_curve(self, timestamp: str):
        """Update equity curve with current balance."""
        if not self.mongo_client:
            return

        try:
            equity_point = {
                "run_id": self.run_id,
                "timestamp": timestamp,
                "balance": float(self.current_balance),
                "unrealized_pnl": float(self._calculate_unrealized_pnl()),
                "total_equity": float(self.current_balance + self._calculate_unrealized_pnl())
            }

            db = self.mongo_client["zerodha_trading"]
            equity_curve = db["backtest_equity_curve"]

            await equity_curve.insert_one(equity_point)
            logger.debug(f"Updated equity curve: {equity_point}")
        except Exception as e:
            logger.warning(f"Failed to update equity curve: {e}")

    def _calculate_unrealized_pnl(self) -> Decimal:
        """Calculate unrealized P&L from open positions."""
        unrealized = Decimal("0")

        # Note: This would need current market prices to calculate properly
        # For now, return 0 as a placeholder
        # In a full implementation, you'd fetch current prices from Redis

        return unrealized

    async def _persist_trade(self, trade: Dict[str, Any]):
        """Persist trade to MongoDB."""
        if not self.mongo_client:
            return

        try:
            db = self.mongo_client["zerodha_trading"]
            backtest_trades = db["backtest_trades"]

            await backtest_trades.insert_one(trade)
            logger.debug(f"Persisted backtest trade: {trade['instrument']} {trade['side']}")
        except Exception as e:
            logger.warning(f"Failed to persist backtest trade: {e}")

    async def get_backtest_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive backtest performance metrics."""
        if not self.trades:
            return {
                "run_id": self.run_id,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
                "starting_balance": float(self.starting_balance),
                "ending_balance": float(self.starting_balance)
            }

        # Calculate basic metrics
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.get("realized_pnl", 0) > 0)
        losing_trades = total_trades - winning_trades
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        total_pnl = sum(t.get("realized_pnl", 0) for t in self.trades)
        total_return_pct = (total_pnl / float(self.starting_balance)) * 100

        # Calculate profit factor
        gross_profit = sum(t.get("realized_pnl", 0) for t in self.trades if t.get("realized_pnl", 0) > 0)
        gross_loss = abs(sum(t.get("realized_pnl", 0) for t in self.trades if t.get("realized_pnl", 0) < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Calculate average win/loss
        winning_pnls = [t.get("realized_pnl", 0) for t in self.trades if t.get("realized_pnl", 0) > 0]
        losing_pnls = [t.get("realized_pnl", 0) for t in self.trades if t.get("realized_pnl", 0) < 0]

        avg_win = sum(winning_pnls) / len(winning_pnls) if winning_pnls else 0.0
        avg_loss = sum(losing_pnls) / len(losing_pnls) if losing_pnls else 0.0
        largest_win = max(winning_pnls) if winning_pnls else 0.0
        largest_loss = min(losing_pnls) if losing_pnls else 0.0

        # Calculate max drawdown (simplified - would need equity curve data)
        max_drawdown_pct = 0.0  # Placeholder

        # Calculate Sharpe ratio (simplified - would need daily returns)
        sharpe_ratio = 0.0  # Placeholder

        return {
            "run_id": self.run_id,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "total_return_pct": total_return_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "sharpe_ratio": sharpe_ratio,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "largest_win": largest_win,
            "largest_loss": largest_loss,
            "starting_balance": float(self.starting_balance),
            "ending_balance": float(self.current_balance)
        }

    async def finalize_backtest(self):
        """Finalize backtest and persist metrics."""
        if not self.mongo_client:
            return

        try:
            metrics = await self.get_backtest_metrics()
            metrics["completed_at"] = datetime.now(IST).isoformat()

            db = self.mongo_client["zerodha_trading"]
            backtest_runs = db["backtest_runs"]

            await backtest_runs.insert_one(metrics)
            logger.info(f"Finalized backtest run {self.run_id}: {metrics}")
        except Exception as e:
            logger.warning(f"Failed to finalize backtest: {e}")


def create_execution_adapter(
    mode: str,
    run_id: Optional[str] = None,
    redis_client: Optional[redis.Redis] = None,
    mongo_client=None
) -> ExecutionAdapter:
    """Factory function to create the appropriate execution adapter based on mode."""

    if mode == "LIVE":
        return LiveExecutionAdapter(mode, run_id, redis_client)
    elif mode == "PAPER":
        return PaperExecutionAdapter(mode, run_id, redis_client)
    elif mode == "BACKTEST":
        return BacktestExecutionAdapter(mode, run_id, redis_client, mongo_client)
    else:
        raise ValueError(f"Invalid execution mode: {mode}. Must be LIVE, PAPER, or BACKTEST")


__all__ = [
    "ExecutionAdapter",
    "LiveExecutionAdapter",
    "PaperExecutionAdapter",
    "BacktestExecutionAdapter",
    "create_execution_adapter"
]