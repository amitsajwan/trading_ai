"""Position management service - handles live position tracking and lifecycle."""

import logging
from typing import Dict, Any, List, Optional, Protocol, runtime_checkable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_DOWN

# Import risk module
try:
    from risk_module.risk_manager import RiskManager, RiskMetrics
    RISK_MODULE_AVAILABLE = True
except ImportError:
    RISK_MODULE_AVAILABLE = False
    RiskManager = None
    RiskMetrics = None

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a trading position."""
    position_id: str
    symbol: str
    action: str  # BUY or SELL
    quantity: int
    entry_price: float
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: str = "active"  # active, closed, pending
    entry_timestamp: datetime = field(default_factory=datetime.now)
    last_update: datetime = field(default_factory=datetime.now)
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    commission: float = 0.0
    tags: List[str] = field(default_factory=list)

    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized profit/loss."""
        if self.status != "active":
            return 0.0

        if self.action == "BUY":
            return (self.current_price - self.entry_price) * self.quantity
        else:  # SELL
            return (self.entry_price - self.current_price) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        """Calculate unrealized profit/loss percentage."""
        if self.status != "active" or self.entry_price == 0:
            return 0.0
        return (self.unrealized_pnl / (self.entry_price * self.quantity)) * 100

    @property
    def market_value(self) -> float:
        """Current market value of position."""
        return self.current_price * self.quantity

    @property
    def risk_amount(self) -> float:
        """Risk amount based on stop loss."""
        if not self.stop_loss:
            return 0.0
        if self.action == "BUY":
            return (self.entry_price - self.stop_loss) * self.quantity
        else:
            return (self.stop_loss - self.entry_price) * self.quantity

    def update_price(self, new_price: float):
        """Update current price and check for stop/target hits."""
        self.current_price = new_price
        self.last_update = datetime.now()

        # Check stop loss
        if self.stop_loss:
            if self.action == "BUY" and new_price <= self.stop_loss:
                self.close_position(new_price, "STOP_LOSS")
            elif self.action == "SELL" and new_price >= self.stop_loss:
                self.close_position(new_price, "STOP_LOSS")

        # Check take profit
        if self.take_profit:
            if self.action == "BUY" and new_price >= self.take_profit:
                self.close_position(new_price, "TAKE_PROFIT")
            elif self.action == "SELL" and new_price <= self.take_profit:
                self.close_position(new_price, "TAKE_PROFIT")

    def close_position(self, exit_price: float, reason: str = "MANUAL"):
        """Close the position."""
        self.exit_price = exit_price
        self.exit_timestamp = datetime.now()
        self.status = "closed"
        self.tags.append(f"exit_reason:{reason}")
        logger.info(f"Closed position {self.position_id}: {reason} at {exit_price}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'action': self.action,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'status': self.status,
            'entry_timestamp': self.entry_timestamp.isoformat(),
            'last_update': self.last_update.isoformat(),
            'exit_price': self.exit_price,
            'exit_timestamp': self.exit_timestamp.isoformat() if self.exit_timestamp else None,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_pct': self.unrealized_pnl_pct,
            'market_value': self.market_value,
            'risk_amount': self.risk_amount,
            'commission': self.commission,
            'tags': self.tags
        }


@dataclass
class Portfolio:
    """Represents the current portfolio state."""
    positions: Dict[str, Position] = field(default_factory=dict)
    total_equity: float = 100000.0  # Starting capital
    available_cash: float = 100000.0
    total_risk_exposure: float = 0.0
    daily_pnl: float = 0.0
    total_pnl: float = 0.0

    @property
    def active_positions(self) -> List[Position]:
        """Get all active positions."""
        return [pos for pos in self.positions.values() if pos.status == "active"]

    @property
    def total_portfolio_value(self) -> float:
        """Total portfolio value including cash and positions."""
        position_value = sum(pos.market_value for pos in self.active_positions)
        return self.available_cash + position_value

    @property
    def total_unrealized_pnl(self) -> float:
        """Total unrealized P&L across all positions."""
        return sum(pos.unrealized_pnl for pos in self.active_positions)

    def update_position_prices(self, symbol: str, new_price: float):
        """Update prices for all positions of a symbol."""
        for position in self.positions.values():
            if position.symbol == symbol and position.status == "active":
                position.update_price(new_price)

    def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        """Get all positions for a specific symbol."""
        return [pos for pos in self.positions.values() if pos.symbol == symbol]


@runtime_checkable
class OrderExecutionProvider(Protocol):
    """Protocol for order execution callbacks."""
    async def execute_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an order and return result."""
        ...


class PositionManager:
    """Manages live trading positions and portfolio state."""

    def __init__(self,
                 initial_equity: float = 100000.0,
                 max_positions: int = 5,
                 max_risk_per_trade_pct: float = 1.0,
                 max_total_risk_pct: float = 5.0):
        """Initialize position manager.

        Args:
            initial_equity: Starting account equity
            max_positions: Maximum number of concurrent positions
            max_risk_per_trade_pct: Max risk per trade as % of equity
            max_total_risk_pct: Max total portfolio risk exposure
        """
        self.portfolio = Portfolio()
        self.portfolio.total_equity = initial_equity
        self.portfolio.available_cash = initial_equity

        self.max_positions = max_positions
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_total_risk_pct = max_total_risk_pct

        self.order_execution_provider: Optional[OrderExecutionProvider] = None
        self._position_counter = 0

        # Initialize risk manager if available
        self.risk_manager = None
        if RISK_MODULE_AVAILABLE:
            risk_config = {
                'initial_capital': initial_equity,
                'max_risk_per_trade_pct': max_risk_per_trade_pct,
                'max_portfolio_risk_pct': max_total_risk_pct,
                'max_position_size_pct': 5.0,  # 5% max position size
                'max_open_positions': max_positions,
                'max_daily_loss_pct': 3.0,  # 3% max daily loss
                'max_consecutive_losses': 5,  # Max consecutive losses
                'min_reward_ratio': 1.5,  # Minimum reward-to-risk ratio
                'margin_requirement_pct': 10.0,  # Margin requirement
                'cooldown_after_loss_min': 15,  # Cooldown after loss
                'circuit_breaker_loss_pct': 10.0,  # Circuit breaker threshold
                'daily_reset_hour': 9,  # Daily reset hour
            }
            self.risk_manager = RiskManager(risk_config)
            logger.info("RiskManager integrated with PositionManager")
        else:
            logger.warning("Risk module not available - using basic risk checks only")

        logger.info(f"PositionManager initialized with {initial_equity} equity")

    def set_order_execution_provider(self, provider: OrderExecutionProvider):
        """Set the order execution provider."""
        self.order_execution_provider = provider

    async def open_position(self,
                          symbol: str,
                          action: str,
                          quantity: int,
                          entry_price: float,
                          stop_loss: Optional[float] = None,
                          take_profit: Optional[float] = None,
                          tags: List[str] = None) -> Optional[Position]:
        """Open a new position.

        Args:
            symbol: Trading symbol
            action: BUY or SELL
            quantity: Position size
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            tags: Optional tags for tracking

        Returns:
            Position object if successful, None if rejected
        """
        # Use comprehensive risk assessment if available
        if self.risk_manager:
            trade_signal = {
                'entry_price': entry_price,
                'stop_loss': stop_loss or (entry_price * 0.98 if action == 'BUY' else entry_price * 1.02),
                'take_profit': take_profit or (entry_price * 1.04 if action == 'BUY' else entry_price * 0.96),
                'confidence': 0.7  # Default confidence, could be passed from orchestrator
            }

            try:
                risk_metrics = await self.risk_manager.assess_trade_risk(trade_signal)

                # Check if trade passes risk assessment
                if not risk_metrics.risk_checks_passed:
                    logger.warning(f"Trade rejected by risk assessment: {risk_metrics.risk_warnings}")
                    return None

                # Use risk-calculated position size instead of provided quantity
                if risk_metrics.position_size > 0:
                    quantity = risk_metrics.position_size
                    logger.info(f"Risk-adjusted position size: {quantity} (was {quantity})")

                # Log risk assessment results
                logger.info(f"Risk assessment passed: Level={risk_metrics.risk_level.value}, "
                          f"Risk={risk_metrics.risk_pct:.1f}%, Reward={risk_metrics.reward_ratio:.1f}")

            except Exception as e:
                logger.error(f"Risk assessment failed: {e}")
                # Fall back to basic checks if risk assessment fails
                pass

        # Basic risk checks (fallback or when risk module not available)
        # Validate position limits
        if len(self.portfolio.active_positions) >= self.max_positions:
            logger.warning(f"Position limit reached ({self.max_positions})")
            return None

        # Calculate risk amount
        risk_amount = 0.0
        if stop_loss:
            if action == "BUY":
                risk_amount = (entry_price - stop_loss) * quantity
            else:
                risk_amount = (stop_loss - entry_price) * quantity

        # Check risk limits
        max_risk_per_trade = self.portfolio.total_equity * (self.max_risk_per_trade_pct / 100)
        if risk_amount > max_risk_per_trade:
            logger.warning(f"Risk per trade limit exceeded: {risk_amount} > {max_risk_per_trade}")
            return None

        # Check total risk exposure
        new_total_risk = self.portfolio.total_risk_exposure + risk_amount
        max_total_risk = self.portfolio.total_equity * (self.max_total_risk_pct / 100)
        if new_total_risk > max_total_risk:
            logger.warning(f"Total risk limit exceeded: {new_total_risk} > {max_total_risk}")
            return None

        # Check available cash (simplified - in real trading, use margin calculations)
        position_value = entry_price * quantity
        if position_value > self.portfolio.available_cash:
            logger.warning(f"Insufficient cash: {position_value} > {self.portfolio.available_cash}")
            return None

        # Create position
        self._position_counter += 1
        position_id = f"POS_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._position_counter}"

        position = Position(
            position_id=position_id,
            symbol=symbol,
            action=action,
            quantity=quantity,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            tags=tags or []
        )

        # Add to portfolio
        self.portfolio.positions[position_id] = position
        self.portfolio.available_cash -= position_value
        self.portfolio.total_risk_exposure += risk_amount

        logger.info(f"Opened position {position_id}: {action} {quantity} {symbol} @ {entry_price}")
        return position

    async def close_position(self, position_id: str, exit_price: float, reason: str = "MANUAL") -> bool:
        """Close an existing position.

        Args:
            position_id: Position to close
            exit_price: Exit price
            reason: Reason for closing

        Returns:
            True if successful, False otherwise
        """
        if position_id not in self.portfolio.positions:
            logger.warning(f"Position {position_id} not found")
            return False

        position = self.portfolio.positions[position_id]
        if position.status != "active":
            logger.warning(f"Position {position_id} is not active")
            return False

        # Close position
        position.close_position(exit_price, reason)

        # Update portfolio
        realized_pnl = position.unrealized_pnl
        self.portfolio.daily_pnl += realized_pnl
        self.portfolio.total_pnl += realized_pnl
        self.portfolio.total_equity += realized_pnl
        self.portfolio.available_cash += position.market_value  # Return margin/cash
        self.portfolio.total_risk_exposure -= position.risk_amount

        logger.info(f"Closed position {position_id}: Realized P&L {realized_pnl:.2f}")
        return True

    async def update_market_prices(self, price_updates: Dict[str, float]):
        """Update market prices for all positions.

        Args:
            price_updates: Dict of symbol -> price mappings
        """
        for symbol, price in price_updates.items():
            self.portfolio.update_position_prices(symbol, price)

        # Check for any auto-closed positions and update portfolio
        for position in list(self.portfolio.positions.values()):
            if position.status == "closed" and position.exit_timestamp:
                # Position was auto-closed, update portfolio metrics
                if position not in self.portfolio.active_positions:  # Already processed
                    continue

                realized_pnl = position.unrealized_pnl
                self.portfolio.daily_pnl += realized_pnl
                self.portfolio.total_pnl += realized_pnl
                self.portfolio.total_equity += realized_pnl
                self.portfolio.available_cash += position.market_value
                self.portfolio.total_risk_exposure -= position.risk_amount

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get comprehensive portfolio summary."""
        active_positions = self.portfolio.active_positions

        return {
            'total_equity': self.portfolio.total_equity,
            'available_cash': self.portfolio.available_cash,
            'total_portfolio_value': self.portfolio.total_portfolio_value,
            'total_unrealized_pnl': self.portfolio.total_unrealized_pnl,
            'daily_pnl': self.portfolio.daily_pnl,
            'total_pnl': self.portfolio.total_pnl,
            'total_risk_exposure': self.portfolio.total_risk_exposure,
            'active_positions_count': len(active_positions),
            'max_positions': self.max_positions,
            'positions': [pos.to_dict() for pos in active_positions]
        }

    def get_positions_for_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """Get all positions for a specific symbol."""
        positions = self.portfolio.get_positions_by_symbol(symbol)
        return [pos.to_dict() for pos in positions]

    def get_position_by_id(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Get position details by ID."""
        position = self.portfolio.positions.get(position_id)
        return position.to_dict() if position else None

    async def execute_trading_decision(self, instrument: str, decision: str, confidence: float, analysis_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute a trading decision from the orchestrator.

        Args:
            instrument: Trading instrument/symbol
            decision: Trading decision (BUY, SELL, HOLD)
            confidence: Confidence score (0-1)
            analysis_details: Detailed analysis results

        Returns:
            Execution result or None if failed
        """
        symbol = instrument  # Use instrument as symbol
        quantity = analysis_details.get('quantity', 1)  # Default quantity
        entry_price = analysis_details.get('entry_price', 0)
        stop_loss = analysis_details.get('stop_loss')
        take_profit = analysis_details.get('take_profit')

        if decision in ['BUY', 'SELL']:
            # Open new position
            position = await self.open_position(
                symbol=symbol,
                action=decision,
                quantity=quantity,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                tags=['orchestrator_decision', f'confidence_{confidence:.2f}']
            )

            if position:
                return {
                    'status': 'EXECUTED',
                    'position_id': position.position_id,
                    'action': 'OPEN',
                    'symbol': symbol,
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'confidence': confidence
                }

        elif action in ['CLOSE_LONG', 'CLOSE_SHORT']:
            # Close existing position
            # Find the position to close based on symbol and action
            positions = self.portfolio.get_positions_by_symbol(symbol)
            target_action = 'BUY' if action == 'CLOSE_LONG' else 'SELL'

            for pos in positions:
                if pos.action == target_action and pos.status == 'active':
                    success = await self.close_position(
                        pos.position_id,
                        entry_price,  # Use current price as exit price
                        'ORCHESTRATOR_CLOSE'
                    )
                    if success:
                        return {
                            'status': 'EXECUTED',
                            'position_id': pos.position_id,
                            'action': 'CLOSE',
                            'symbol': symbol,
                            'exit_price': entry_price
                        }
                    break

        return {
            'status': 'FAILED',
            'reason': f'Unable to execute {decision} for {symbol}'
        }