"""Risk management implementation for trading system."""

import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from .contracts import RiskAssessment, RiskLevel, RiskProvider

logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    """Comprehensive risk metrics for a trade."""
    position_size: int
    risk_amount: float
    risk_pct: float
    reward_ratio: float
    win_probability: float
    expected_value: float
    max_loss: float
    max_profit: float
    risk_level: RiskLevel
    risk_checks_passed: bool
    risk_warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'position_size': self.position_size,
            'risk_amount': self.risk_amount,
            'risk_pct': self.risk_pct,
            'reward_ratio': self.reward_ratio,
            'win_probability': self.win_probability,
            'expected_value': self.expected_value,
            'max_loss': self.max_loss,
            'max_profit': self.max_profit,
            'risk_level': self.risk_level.value,
            'risk_checks_passed': self.risk_checks_passed,
            'risk_warnings': self.risk_warnings
        }


@dataclass
class PortfolioState:
    """Current portfolio state."""
    total_value: float
    available_cash: float
    margin_used: float
    open_positions: Dict[str, Dict]
    daily_pnl: float
    daily_pnl_pct: float
    max_daily_loss: float
    max_daily_loss_pct: float
    consecutive_losses: int
    last_trade_time: Optional[datetime]
    is_emergency_stop: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_value': self.total_value,
            'available_cash': self.available_cash,
            'margin_used': self.margin_used,
            'open_positions_count': len(self.open_positions),
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': self.daily_pnl_pct,
            'max_daily_loss': self.max_daily_loss,
            'max_daily_loss_pct': self.max_daily_loss_pct,
            'consecutive_losses': self.consecutive_losses,
            'last_trade_time': self.last_trade_time.isoformat() if self.last_trade_time else None,
            'is_emergency_stop': self.is_emergency_stop
        }


class RiskManager:
    """Comprehensive risk management system."""

    def __init__(self, config: Dict[str, Any] = None, risk_provider: Optional[RiskProvider] = None):
        """Initialize risk manager."""
        self.config = config or self._get_default_config()
        self.risk_provider = risk_provider

        # Portfolio state
        self.portfolio = PortfolioState(
            total_value=self.config['initial_capital'],
            available_cash=self.config['initial_capital'],
            margin_used=0.0,
            open_positions={},
            daily_pnl=0.0,
            daily_pnl_pct=0.0,
            max_daily_loss=0.0,
            max_daily_loss_pct=0.0,
            consecutive_losses=0,
            last_trade_time=None,
            is_emergency_stop=False
        )

        # Daily reset tracking
        self.current_date = datetime.now().date()
        self.daily_reset_task = None

        # Risk monitoring
        self.risk_alerts = []
        self.emergency_stop_reasons = []

        logger.info(f"Risk Manager initialized with ₹{self.config['initial_capital']:,.0f} capital")

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default risk management configuration."""
        return {
            'initial_capital': 100000,
            'max_risk_per_trade_pct': 1.0,
            'max_portfolio_risk_pct': 5.0,
            'max_daily_loss_pct': 3.0,
            'max_consecutive_losses': 5,
            'min_reward_ratio': 1.5,
            'max_position_size_pct': 5.0,
            'margin_requirement_pct': 10.0,
            'max_open_positions': 3,
            'cooldown_after_loss_min': 15,
            'circuit_breaker_loss_pct': 10.0,
            'daily_reset_hour': 9,
        }

    async def assess_trade_risk(self, trade_signal: Dict[str, Any]) -> RiskMetrics:
        """Comprehensive risk assessment for a trade signal."""
        if self.portfolio.is_emergency_stop:
            return RiskMetrics(
                position_size=0,
                risk_amount=0.0,
                risk_pct=0.0,
                reward_ratio=0.0,
                win_probability=0.0,
                expected_value=0.0,
                max_loss=0.0,
                max_profit=0.0,
                risk_level=RiskLevel.CRITICAL,
                risk_checks_passed=False,
                risk_warnings=["Emergency stop activated"]
            )

        warnings = []

        # Check daily limits
        if not self._check_daily_limits():
            warnings.append("Daily loss limit exceeded")

        # Check consecutive losses
        if not self._check_consecutive_losses():
            warnings.append("Too many consecutive losses")

        # Check cooldown period
        if not self._check_cooldown_period():
            warnings.append("In cooldown period after loss")

        # Check portfolio limits
        if not self._check_portfolio_limits():
            warnings.append("Portfolio risk limits exceeded")

        # Calculate position size
        position_size, risk_amount = self._calculate_position_size(trade_signal)

        # Calculate risk metrics
        risk_pct = (risk_amount / self.portfolio.total_value) * 100
        reward_ratio = self._calculate_reward_ratio(trade_signal)

        # Estimate win probability based on confidence and historical data
        win_probability = self._estimate_win_probability(trade_signal.get('confidence', 0.5), risk_pct)

        # Calculate expected value
        expected_value = self._calculate_expected_value(risk_amount, reward_ratio, win_probability)

        # Determine risk level
        risk_level = self._determine_risk_level(risk_pct, reward_ratio, win_probability)

        # Additional checks
        if reward_ratio < self.config['min_reward_ratio']:
            warnings.append(f"Reward ratio {reward_ratio:.1f} below minimum {self.config['min_reward_ratio']}")

        if position_size <= 0:
            warnings.append("Position size calculation resulted in zero")

        # Final risk assessment
        risk_checks_passed = len(warnings) == 0 and not self.portfolio.is_emergency_stop

        return RiskMetrics(
            position_size=position_size,
            risk_amount=risk_amount,
            risk_pct=risk_pct,
            reward_ratio=reward_ratio,
            win_probability=win_probability,
            expected_value=expected_value,
            max_loss=risk_amount,
            max_profit=risk_amount * reward_ratio,
            risk_level=risk_level,
            risk_checks_passed=risk_checks_passed,
            risk_warnings=warnings
        )

    def _calculate_position_size(self, trade_signal: Dict[str, Any]) -> Tuple[int, float]:
        """Calculate optimal position size based on risk management."""
        try:
            entry_price = trade_signal.get('entry_price', 0)
            stop_loss = trade_signal.get('stop_loss', entry_price * 0.98)

            if entry_price <= 0:
                return 0, 0.0

            # Maximum risk per trade
            max_risk = self.portfolio.total_value * (self.config['max_risk_per_trade_pct'] / 100)

            # Calculate stop loss distance
            stop_distance = abs(entry_price - stop_loss)

            if stop_distance <= 0:
                return 0, 0.0

            # Base position size on risk
            position_value = max_risk / (stop_distance / entry_price)
            risk_amount = max_risk

            # Apply position size limits
            max_position_value = self.portfolio.total_value * (self.config['max_position_size_pct'] / 100)
            position_value = min(position_value, max_position_value)

            # Convert to quantity (assuming NIFTY)
            quantity = max(1, int(position_value / entry_price))

            # Check available capital
            required_margin = position_value * (self.config['margin_requirement_pct'] / 100)
            if required_margin > self.portfolio.available_cash:
                # Reduce position size to fit available capital
                available_for_margin = self.portfolio.available_cash / (self.config['margin_requirement_pct'] / 100)
                position_value = min(position_value, available_for_margin)
                quantity = max(1, int(position_value / entry_price))
                risk_amount = stop_distance * entry_price * quantity

            return quantity, risk_amount

        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0, 0.0

    def _calculate_reward_ratio(self, trade_signal: Dict[str, Any]) -> float:
        """Calculate risk-reward ratio."""
        try:
            entry_price = trade_signal.get('entry_price', 0)
            stop_loss = trade_signal.get('stop_loss', entry_price * 0.98)
            take_profit = trade_signal.get('take_profit', entry_price * 1.04)

            if entry_price <= 0:
                return 0.0

            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)

            return reward / risk if risk > 0 else 0.0

        except Exception:
            return 0.0

    def _estimate_win_probability(self, confidence: float, risk_pct: float) -> float:
        """Estimate win probability based on confidence and risk."""
        # Base probability on signal confidence
        base_prob = confidence

        # Adjust for risk level
        if risk_pct > 2.0:
            base_prob *= 0.9  # Reduce probability for high-risk trades
        elif risk_pct < 0.5:
            base_prob *= 1.1  # Increase probability for low-risk trades

        # Cap between 0.1 and 0.9
        return max(0.1, min(0.9, base_prob))

    def _calculate_expected_value(self, risk_amount: float, reward_ratio: float, win_prob: float) -> float:
        """Calculate expected value of the trade."""
        loss_prob = 1 - win_prob
        expected_value = (win_prob * risk_amount * reward_ratio) - (loss_prob * risk_amount)
        return expected_value

    def _determine_risk_level(self, risk_pct: float, reward_ratio: float, win_prob: float) -> RiskLevel:
        """Determine overall risk level."""
        risk_score = 0

        # Risk percentage score
        if risk_pct > 2.0:
            risk_score += 3
        elif risk_pct > 1.0:
            risk_score += 2
        elif risk_pct > 0.5:
            risk_score += 1

        # Reward ratio score (inverse)
        if reward_ratio < 1.5:
            risk_score += 2
        elif reward_ratio < 2.0:
            risk_score += 1

        # Win probability score (inverse)
        if win_prob < 0.4:
            risk_score += 3
        elif win_prob < 0.5:
            risk_score += 2
        elif win_prob < 0.6:
            risk_score += 1

        # Determine level
        if risk_score >= 6:
            return RiskLevel.CRITICAL
        elif risk_score >= 4:
            return RiskLevel.HIGH
        elif risk_score >= 2:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _check_daily_limits(self) -> bool:
        """Check if daily loss limits are exceeded."""
        max_daily_loss = self.portfolio.total_value * (self.config['max_daily_loss_pct'] / 100)
        return abs(self.portfolio.daily_pnl) < max_daily_loss

    def _check_consecutive_losses(self) -> bool:
        """Check consecutive loss limit."""
        return self.portfolio.consecutive_losses < self.config['max_consecutive_losses']

    def _check_cooldown_period(self) -> bool:
        """Check if in cooldown period after a loss."""
        if not self.portfolio.last_trade_time:
            return True

        cooldown_minutes = self.config['cooldown_after_loss_min']
        cooldown_end = self.portfolio.last_trade_time + timedelta(minutes=cooldown_minutes)
        return datetime.now() >= cooldown_end

    def _check_portfolio_limits(self) -> bool:
        """Check portfolio-level risk limits."""
        # Check max open positions
        if len(self.portfolio.open_positions) >= self.config['max_open_positions']:
            return False

        # Check total portfolio risk
        total_risk = sum(pos.get('risk_amount', 0) for pos in self.portfolio.open_positions.values())
        max_portfolio_risk = self.portfolio.total_value * (self.config['max_portfolio_risk_pct'] / 100)

        return total_risk < max_portfolio_risk

    def update_portfolio_state(self, trade_result: Dict[str, Any]):
        """Update portfolio state after a trade."""
        try:
            pnl = trade_result.get('pnl', 0)

            # Update daily P&L
            self.portfolio.daily_pnl += pnl
            self.portfolio.daily_pnl_pct = (self.portfolio.daily_pnl / self.portfolio.total_value) * 100

            # Update consecutive losses
            if pnl < 0:
                self.portfolio.consecutive_losses += 1
            else:
                self.portfolio.consecutive_losses = 0

            # Update max daily loss
            if pnl < 0:
                self.portfolio.max_daily_loss = min(self.portfolio.max_daily_loss, pnl)
                self.portfolio.max_daily_loss_pct = (abs(self.portfolio.max_daily_loss) / self.portfolio.total_value) * 100

            # Update capital
            self.portfolio.total_value += pnl
            self.portfolio.available_cash += pnl

            # Update last trade time
            self.portfolio.last_trade_time = datetime.now()

            # Check for emergency stop
            circuit_breaker_loss = self.portfolio.total_value * (self.config['circuit_breaker_loss_pct'] / 100)
            if abs(self.portfolio.daily_pnl) >= circuit_breaker_loss:
                self.portfolio.is_emergency_stop = True
                self.emergency_stop_reasons.append(f"Circuit breaker triggered: daily loss ₹{abs(self.portfolio.daily_pnl):,.0f}")
                logger.critical(f"🚨 EMERGENCY STOP: {self.emergency_stop_reasons[-1]}")

        except Exception as e:
            logger.error(f"Error updating portfolio state: {e}")

    def add_position(self, position_data: Dict[str, Any]):
        """Add a new position to portfolio."""
        position_id = position_data.get('position_id') or f"pos_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.portfolio.open_positions[position_id] = position_data

    def remove_position(self, position_id: str):
        """Remove a closed position."""
        if position_id in self.portfolio.open_positions:
            del self.portfolio.open_positions[position_id]

    async def start_daily_reset_monitor(self):
        """Start monitoring for daily reset."""
        while True:
            try:
                current_time = datetime.now()

                # Check if it's time for daily reset
                if (current_time.hour == self.config['daily_reset_hour'] and
                    current_time.minute == 0 and
                    current_time.date() != self.current_date):

                    await self._perform_daily_reset()
                    self.current_date = current_time.date()

                # Check every minute
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Error in daily reset monitor: {e}")
                await asyncio.sleep(60)

    async def _perform_daily_reset(self):
        """Perform daily reset of risk limits."""
        logger.info("Performing daily risk reset...")

        # Reset daily P&L
        self.portfolio.daily_pnl = 0.0
        self.portfolio.daily_pnl_pct = 0.0
        self.portfolio.max_daily_loss = 0.0
        self.portfolio.max_daily_loss_pct = 0.0

        # Reset consecutive losses
        self.portfolio.consecutive_losses = 0

        # Clear emergency stop if it was daily limit related
        if "daily loss" in " ".join(self.emergency_stop_reasons).lower():
            self.portfolio.is_emergency_stop = False
            logger.info("Emergency stop cleared after daily reset")

        # Clear old risk alerts (keep last 24 hours)
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.risk_alerts = [
            alert for alert in self.risk_alerts
            if alert['timestamp'] > cutoff_time
        ]

        logger.info("✅ Daily risk reset completed")

    def get_risk_report(self) -> Dict[str, Any]:
        """Generate comprehensive risk report."""
        return {
            'portfolio_state': self.portfolio.to_dict(),
            'risk_config': self.config,
            'risk_alerts': self.risk_alerts[-10:],  # Last 10 alerts
            'emergency_stop_reasons': self.emergency_stop_reasons,
            'risk_limits_status': {
                'daily_loss_ok': self._check_daily_limits(),
                'consecutive_losses_ok': self._check_consecutive_losses(),
                'cooldown_ok': self._check_cooldown_period(),
                'portfolio_limits_ok': self._check_portfolio_limits(),
                'emergency_stop_active': self.portfolio.is_emergency_stop
            }
        }

    async def get_risk_assessment(self) -> RiskAssessment:
        """Get comprehensive risk assessment."""
        can_trade, reason = self.can_trade()

        # Calculate risk score
        risk_score = 0
        warnings = []
        recommendations = []

        # Check various risk factors
        if not self._check_daily_limits():
            risk_score += 3
            warnings.append("Daily loss limit exceeded")
            recommendations.append("Wait for daily reset or reduce position sizes")

        if not self._check_consecutive_losses():
            risk_score += 2
            warnings.append("High consecutive losses")
            recommendations.append("Consider taking a break or reviewing strategy")

        if self.portfolio.is_emergency_stop:
            risk_score += 5
            warnings.append("Emergency stop active")
            recommendations.append("Trading suspended - review risk parameters")

        # Determine risk level
        if risk_score >= 5:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 3:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 1:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        return RiskAssessment(
            can_trade=can_trade,
            risk_level=risk_level,
            risk_score=risk_score,
            warnings=warnings,
            recommendations=recommendations,
            position_limit=self.config['max_open_positions'] - len(self.portfolio.open_positions),
            max_risk_amount=self.portfolio.total_value * (self.config['max_risk_per_trade_pct'] / 100),
            details={
                'portfolio_value': self.portfolio.total_value,
                'available_cash': self.portfolio.available_cash,
                'daily_pnl': self.portfolio.daily_pnl,
                'open_positions': len(self.portfolio.open_positions),
                'consecutive_losses': self.portfolio.consecutive_losses
            }
        )

    def can_trade(self) -> Tuple[bool, str]:
        """Check if trading is allowed."""
        if self.portfolio.is_emergency_stop:
            return False, "Emergency stop is active"

        if not self._check_daily_limits():
            return False, "Daily loss limit exceeded"

        if not self._check_consecutive_losses():
            return False, f"Consecutive losses limit ({self.config['max_consecutive_losses']}) exceeded"

        if not self._check_cooldown_period():
            cooldown_min = self.config['cooldown_after_loss_min']
            return False, f"In cooldown period ({cooldown_min} minutes) after loss"

        if not self._check_portfolio_limits():
            return False, "Portfolio risk limits exceeded"

        return True, "Trading allowed"

