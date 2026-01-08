"""Backtesting engine implementation following modular architecture."""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from pathlib import Path

from engine_module.enhanced_orchestrator import EnhancedTradingOrchestrator

# Import risk module (optional)
try:
    from risk_module.risk_manager import RiskManager, RiskMetrics
    RISK_MODULE_AVAILABLE = True
except ImportError:
    RISK_MODULE_AVAILABLE = False
    RiskManager = None
    RiskMetrics = None

# Performance metrics calculation (inline for now)


@dataclass
class BacktestTrade:
    """Represents a completed backtest trade."""
    entry_time: datetime
    exit_time: datetime
    symbol: str
    side: str  # 'BUY' or 'SELL'
    entry_price: float
    exit_price: float
    quantity: int
    stop_loss: float
    take_profit: float
    exit_reason: str  # 'target', 'stop_loss', 'signal_reversal', 'end_of_data'
    pnl: float
    pnl_pct: float
    holding_period: int  # minutes
    commission: float
    slippage: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'exit_reason': self.exit_reason,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
            'holding_period': self.holding_period,
            'commission': self.commission,
            'slippage': self.slippage
        }


@dataclass
class BacktestResult:
    """Comprehensive backtest results."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    profit_factor: float
    total_pnl: float
    total_pnl_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    expectancy: float
    kelly_criterion: float
    total_commission: float
    total_slippage: float
    avg_holding_period: float
    start_date: datetime
    end_date: datetime
    equity_curve: List[float]
    drawdown_curve: List[float]
    monthly_returns: Dict[str, float]
    trades: List[BacktestTrade]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'summary': {
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
                'win_rate': self.win_rate,
                'avg_win': self.avg_win,
                'avg_loss': self.avg_loss,
                'largest_win': self.largest_win,
                'largest_loss': self.largest_loss,
                'profit_factor': self.profit_factor,
                'total_pnl': self.total_pnl,
                'total_pnl_pct': self.total_pnl_pct,
                'max_drawdown': self.max_drawdown,
                'max_drawdown_pct': self.max_drawdown_pct,
                'sharpe_ratio': self.sharpe_ratio,
                'sortino_ratio': self.sortino_ratio,
                'calmar_ratio': self.calmar_ratio,
                'expectancy': self.expectancy,
                'kelly_criterion': self.kelly_criterion,
                'total_commission': self.total_commission,
                'total_slippage': self.total_slippage,
                'avg_holding_period': self.avg_holding_period,
                'start_date': self.start_date.isoformat(),
                'end_date': self.end_date.isoformat()
            },
            'curves': {
                'equity': self.equity_curve,
                'drawdown': self.drawdown_curve
            },
            'monthly_returns': self.monthly_returns,
            'trades': [trade.to_dict() for trade in self.trades]
        }


class MarketDataProvider:
    """Market data provider for backtesting."""

    def __init__(self, data: pd.DataFrame):
        """Initialize with historical data."""
        self.data = self._prepare_data(data)
        self.current_index = 0

    def _prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare and validate historical data."""
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

        # Check columns
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Convert timestamp
        if 'timestamp' in df.columns:
            df = df.copy()
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)

        # Validate data types
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Remove rows with NaN values
        df = df.dropna()

        # Sort by timestamp
        df = df.sort_index()

        return df

    async def get_ohlc_data(self, symbol: str, periods: int = 100) -> List[Dict[str, Any]]:
        """Get OHLC data for backtesting."""
        if self.current_index < periods:
            # Not enough historical data yet
            return []

        # Get data up to current index
        historical_data = self.data.iloc[max(0, self.current_index - periods):self.current_index + 1]

        # Convert to format expected by agents
        ohlc_list = []
        for idx, row in historical_data.iterrows():
            ohlc_list.append({
                'timestamp': idx.isoformat(),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume'])
            })

        return ohlc_list

    def advance_time(self):
        """Advance to next data point."""
        if self.current_index < len(self.data) - 1:
            self.current_index += 1

    def get_current_bar(self) -> Optional[pd.Series]:
        """Get current bar data."""
        if self.current_index < len(self.data):
            return self.data.iloc[self.current_index]
        return None

    def get_current_time(self) -> Optional[datetime]:
        """Get current timestamp."""
        if self.current_index < len(self.data):
            return self.data.index[self.current_index].to_pydatetime()
        return None

    def is_finished(self) -> bool:
        """Check if backtest is finished."""
        return self.current_index >= len(self.data) - 1


class BacktestEngine:
    """Advanced backtesting engine with realistic market simulation."""

    def __init__(self, initial_capital: float = 100000, config: Dict[str, Any] = None):
        """Initialize backtest engine."""
        self.initial_capital = initial_capital
        self.config = config or self._get_default_config()

        # Trading state
        self.current_capital = initial_capital
        self.open_positions = {}
        self.completed_trades = []
        self.equity_curve = [initial_capital]
        self.drawdown_curve = [0.0]

        # Components
        self.orchestrator = None
        self.risk_manager = None
        self.market_data_provider = None

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default backtesting configuration."""
        return {
            'commission_per_trade': 20,  # ₹20 per trade
            'slippage_pct': 0.05,  # 0.05% slippage
            'cycle_interval_minutes': 15,
            'min_confidence_threshold': 0.6,
            'risk_per_trade_pct': 1.0,
            'position_size_pct': 5.0,
        }

    async def run_backtest(self,
                          historical_data: pd.DataFrame,
                          orchestrator_config: Dict[str, Any] = None) -> BacktestResult:
        """Run backtest on historical data."""
        # Initialize components
        self.market_data_provider = MarketDataProvider(historical_data)

        # Initialize risk manager
        risk_config = {
            'initial_capital': self.initial_capital,
            'max_risk_per_trade_pct': self.config['risk_per_trade_pct'],
            'max_position_size_pct': self.config['position_size_pct'],
            'max_daily_loss_pct': 5.0,  # Relaxed for backtesting
            'max_consecutive_losses': 10,  # Relaxed for backtesting
        }
        self.risk_manager = RiskManager(risk_config)

        # Initialize orchestrator
        orchestrator_config = orchestrator_config or {
            'symbol': 'NIFTY50',
            'min_confidence_threshold': self.config['min_confidence_threshold'],
            'risk_per_trade_pct': self.config['risk_per_trade_pct'],
            'position_size_pct': self.config['position_size_pct'],
            'account_size': self.initial_capital,
        }
        self.orchestrator = EnhancedTradingOrchestrator(
            market_data_provider=self.market_data_provider,
            config=orchestrator_config
        )

        # Run backtest
        start_time = datetime.now()
        cycle_count = 0

        while not self.market_data_provider.is_finished():
            cycle_count += 1

            # Check if we should run a cycle (every 15 minutes of market data)
            current_time = self.market_data_provider.get_current_time()
            if not current_time:
                break

            # Run trading cycle
            context = {'symbol': 'NIFTY50', 'timestamp': current_time}
            result = await self.orchestrator.run_cycle(context)

            # Process trading decision
            if result.decision in ['BUY', 'SELL'] and result.confidence >= self.config['min_confidence_threshold']:
                await self._process_trading_decision(result)

            # Update equity curve
            self.equity_curve.append(self.current_capital)

            # Calculate drawdown
            peak = max(self.equity_curve)
            current_drawdown = (peak - self.current_capital) / peak * 100
            self.drawdown_curve.append(current_drawdown)

            # Advance to next data point
            self.market_data_provider.advance_time()

        # Close any remaining positions
        await self._close_all_positions()

        # Calculate comprehensive results
        result = self._calculate_results(start_time, datetime.now())

        return result

    async def _process_trading_decision(self, decision_result):
        """Process a trading decision from the orchestrator."""
        try:
            # Extract decision details
            decision_details = decision_result.details
            signal_data = {
                'entry_price': decision_details.get('entry_price', 0),
                'stop_loss': decision_details.get('stop_loss', 0),
                'take_profit': decision_details.get('take_profit', 0),
                'confidence': decision_result.confidence
            }

            # Assess risk
            risk_metrics = await self.risk_manager.assess_trade_risk(signal_data)

            if not risk_metrics.risk_checks_passed:
                return  # Risk check failed

            # Open position
            await self._open_position(decision_result, risk_metrics)

        except Exception as e:
            print(f"Error processing trading decision: {e}")

    async def _open_position(self, decision_result, risk_metrics: RiskMetrics):
        """Open a new position."""
        current_bar = self.market_data_provider.get_current_bar()
        if not current_bar:
            return

        current_time = self.market_data_provider.get_current_time()
        decision_details = decision_result.details

        # Apply slippage to entry price
        entry_price = self._apply_slippage(current_bar['close'], decision_result.decision)

        position_id = f"pos_{current_time.strftime('%Y%m%d_%H%M%S')}"

        self.open_positions[position_id] = {
            'id': position_id,
            'symbol': 'NIFTY50',
            'side': decision_result.decision,
            'entry_price': entry_price,
            'quantity': risk_metrics.position_size,
            'stop_loss': decision_details.get('stop_loss', entry_price * 0.98),
            'take_profit': decision_details.get('take_profit', entry_price * 1.04),
            'entry_time': current_time,
            'risk_amount': risk_metrics.risk_amount
        }

        # Deduct commission
        commission = self.config['commission_per_trade']
        self.current_capital -= commission

    async def _close_position(self, position_id: str, exit_price: float, exit_time: datetime, exit_reason: str):
        """Close an open position."""
        if position_id not in self.open_positions:
            return

        position = self.open_positions[position_id]

        # Calculate P&L
        if position['side'] == "BUY":
            pnl = (exit_price - position['entry_price']) * position['quantity']
        else:  # SELL
            pnl = (position['entry_price'] - exit_price) * position['quantity']

        # Deduct commission
        commission = self.config['commission_per_trade']
        pnl -= commission

        # Calculate percentages
        pnl_pct = (pnl / (position['entry_price'] * position['quantity'])) * 100

        # Calculate holding period
        holding_period = int((exit_time - position['entry_time']).total_seconds() / 60)

        # Create trade record
        trade = BacktestTrade(
            entry_time=position['entry_time'],
            exit_time=exit_time,
            symbol=position['symbol'],
            side=position['side'],
            entry_price=position['entry_price'],
            exit_price=exit_price,
            quantity=position['quantity'],
            stop_loss=position['stop_loss'],
            take_profit=position['take_profit'],
            exit_reason=exit_reason,
            pnl=pnl,
            pnl_pct=pnl_pct,
            holding_period=holding_period,
            commission=commission,
            slippage=abs(exit_price - self.market_data_provider.get_current_bar()['close'])
        )

        self.completed_trades.append(trade)
        self.current_capital += pnl

        # Remove position
        del self.open_positions[position_id]

    async def _close_all_positions(self):
        """Close all open positions at end of backtest."""
        current_bar = self.market_data_provider.get_current_bar()
        current_time = self.market_data_provider.get_current_time()

        if current_bar is not None and current_time is not None:
            position_ids = list(self.open_positions.keys())
            for position_id in position_ids:
                exit_price = self._apply_slippage(current_bar['close'], "SELL" if self.open_positions[position_id]['side'] == "BUY" else "BUY")
                await self._close_position(position_id, exit_price, current_time, "end_of_data")

    def _apply_slippage(self, price: float, action: str) -> float:
        """Apply realistic slippage to price."""
        slippage_amount = price * (self.config['slippage_pct'] / 100)

        if action == "BUY":
            return price + slippage_amount  # Pay more for buy
        else:
            return price - slippage_amount  # Get less for sell

    def _calculate_results(self, start_time: datetime, end_time: datetime) -> BacktestResult:
        """Calculate comprehensive backtest results."""
        if not self.completed_trades:
            # No trades - return empty result
            return BacktestResult(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                profit_factor=0.0,
                total_pnl=0.0,
                total_pnl_pct=0.0,
                max_drawdown=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                expectancy=0.0,
                kelly_criterion=0.0,
                total_commission=0.0,
                total_slippage=0.0,
                avg_holding_period=0.0,
                start_date=start_time,
                end_date=end_time,
                equity_curve=self.equity_curve,
                drawdown_curve=self.drawdown_curve,
                monthly_returns={},
                trades=[]
            )

        # Basic trade statistics
        winning_trades = [t for t in self.completed_trades if t.pnl > 0]
        losing_trades = [t for t in self.completed_trades if t.pnl <= 0]

        total_trades = len(self.completed_trades)
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0

        # P&L statistics
        total_pnl = sum(t.pnl for t in self.completed_trades)
        total_pnl_pct = (total_pnl / self.initial_capital) * 100

        avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0

        largest_win = max((t.pnl for t in winning_trades), default=0)
        largest_loss = min((t.pnl for t in losing_trades), default=0)

        # Profit factor
        total_wins = sum(t.pnl for t in winning_trades)
        total_losses = abs(sum(t.pnl for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        # Drawdown analysis
        max_drawdown = max(self.drawdown_curve) if self.drawdown_curve else 0
        max_drawdown_pct = max_drawdown

        # Risk-adjusted returns
        returns = np.diff(self.equity_curve) / np.array(self.equity_curve[:-1])
        returns = returns[returns != 0]  # Remove zero returns

        if len(returns) > 0:
            avg_return = np.mean(returns)
            std_return = np.std(returns)

            # Annualized Sharpe ratio (assuming daily returns, 252 trading days)
            sharpe_ratio = (avg_return / std_return) * np.sqrt(252) if std_return > 0 else 0

            # Sortino ratio (downside deviation)
            downside_returns = returns[returns < 0]
            downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 0.0001
            sortino_ratio = (avg_return / downside_std) * np.sqrt(252) if downside_std > 0 else 0

            # Calmar ratio
            calmar_ratio = (total_pnl_pct / 100) / (max_drawdown_pct / 100) if max_drawdown_pct > 0 else 0
        else:
            sharpe_ratio = 0.0
            sortino_ratio = 0.0
            calmar_ratio = 0.0

        # Expectancy and Kelly
        win_prob = win_rate
        win_amount = avg_win
        loss_amount = abs(avg_loss)
        loss_prob = 1 - win_prob

        expectancy = (win_prob * win_amount) - (loss_prob * loss_amount)

        # Kelly criterion
        if loss_amount > 0:
            kelly_criterion = ((win_prob / loss_prob) - 1) / (win_amount / loss_amount)
            kelly_criterion = max(0, kelly_criterion)  # No short selling
        else:
            kelly_criterion = 0.0

        # Costs
        total_commission = sum(t.commission for t in self.completed_trades)
        total_slippage = sum(t.slippage for t in self.completed_trades)

        # Holding period
        avg_holding_period = sum(t.holding_period for t in self.completed_trades) / total_trades

        # Monthly returns (placeholder)
        monthly_returns = {}

        return BacktestResult(
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            profit_factor=profit_factor,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            expectancy=expectancy,
            kelly_criterion=kelly_criterion,
            total_commission=total_commission,
            total_slippage=total_slippage,
            avg_holding_period=avg_holding_period,
            start_date=start_time,
            end_date=end_time,
            equity_curve=self.equity_curve,
            drawdown_curve=self.drawdown_curve,
            monthly_returns=monthly_returns,
            trades=self.completed_trades
        )

