"""Unit tests for Portfolio Heat Manager."""

import pytest
from datetime import datetime, timedelta

from risk_module.portfolio_heat import PortfolioHeatManager, PositionRisk


class TestPortfolioHeatManager:
    """Tests for PortfolioHeatManager."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        manager = PortfolioHeatManager({})
        
        assert manager.max_portfolio_heat == 0.02  # 2%
        assert manager.max_position_heat == 0.01  # 1%
        assert manager.max_daily_loss == 0.05  # 5%
        assert manager.max_weekly_loss == 0.10  # 10%
        assert manager.account_balance == 100000.0
    
    def test_initialization_custom_config(self):
        """Test initialization with custom config."""
        config = {
            'max_portfolio_heat': 0.03,
            'max_position_heat': 0.015,
            'max_daily_loss': 0.06,
            'max_weekly_loss': 0.12,
            'account_balance': 200000.0
        }
        manager = PortfolioHeatManager(config)
        
        assert manager.max_portfolio_heat == 0.03
        assert manager.max_position_heat == 0.015
        assert manager.max_daily_loss == 0.06
        assert manager.max_weekly_loss == 0.12
        assert manager.account_balance == 200000.0
    
    def test_can_open_position_success(self):
        """Test can_open_position returns True for valid position."""
        manager = PortfolioHeatManager({'account_balance': 100000.0})
        
        position_risk = 500.0  # 0.5% of balance
        current_positions = []
        
        can_open, reason = manager.can_open_position(
            position_risk, current_positions, daily_pnl=0.0, weekly_pnl=0.0
        )
        
        assert can_open is True
        assert reason == "OK"
    
    def test_can_open_position_exceeds_position_heat(self):
        """Test can_open_position rejects position exceeding position heat."""
        manager = PortfolioHeatManager({
            'account_balance': 100000.0,
            'max_position_heat': 0.01  # 1%
        })
        
        position_risk = 2000.0  # 2% of balance, exceeds 1% limit
        current_positions = []
        
        can_open, reason = manager.can_open_position(
            position_risk, current_positions, daily_pnl=0.0, weekly_pnl=0.0
        )
        
        assert can_open is False
        assert "exceeds limit" in reason
        assert "Position heat" in reason
    
    def test_can_open_position_exceeds_portfolio_heat(self):
        """Test can_open_position rejects position exceeding portfolio heat."""
        manager = PortfolioHeatManager({
            'account_balance': 100000.0,
            'max_portfolio_heat': 0.02  # 2%
        })
        
        # Existing position with 1.5% heat
        existing_position = PositionRisk(
            position_id="1",
            instrument="BANKNIFTY",
            strategy_type="iron_condor",
            max_loss=1500.0,
            current_pnl=100.0,
            heat_percentage=0.015,
            entry_price=45000.0,
            current_price=45100.0,
            quantity=25,
            entry_time=datetime.now()
        )
        
        position_risk = 1000.0  # Would add 1% heat, total 2.5% > 2%
        current_positions = [existing_position]
        
        can_open, reason = manager.can_open_position(
            position_risk, current_positions, daily_pnl=0.0, weekly_pnl=0.0
        )
        
        assert can_open is False
        assert "Total portfolio heat" in reason
    
    def test_can_open_position_daily_loss_limit(self):
        """Test can_open_position respects daily loss limit."""
        manager = PortfolioHeatManager({
            'account_balance': 100000.0,
            'max_daily_loss': 0.05  # 5%
        })
        
        daily_pnl = -6000.0  # -6% loss, exceeds 5% limit
        position_risk = 500.0
        current_positions = []
        
        can_open, reason = manager.can_open_position(
            position_risk, current_positions, daily_pnl=daily_pnl, weekly_pnl=0.0
        )
        
        assert can_open is False
        assert "Daily loss limit" in reason
    
    def test_can_open_position_weekly_loss_limit(self):
        """Test can_open_position respects weekly loss limit."""
        manager = PortfolioHeatManager({
            'account_balance': 100000.0,
            'max_weekly_loss': 0.10  # 10%
        })
        
        weekly_pnl = -12000.0  # -12% loss, exceeds 10% limit
        position_risk = 500.0
        current_positions = []
        
        can_open, reason = manager.can_open_position(
            position_risk, current_positions, daily_pnl=0.0, weekly_pnl=weekly_pnl
        )
        
        assert can_open is False
        assert "Weekly loss limit" in reason
    
    def test_calculate_optimal_quantity_no_capacity(self):
        """Test calculate_optimal_quantity returns 0 when no capacity."""
        manager = PortfolioHeatManager({
            'account_balance': 100000.0,
            'max_portfolio_heat': 0.02  # 2%
        })
        
        # Portfolio already at max heat
        existing_position = PositionRisk(
            position_id="1",
            instrument="BANKNIFTY",
            strategy_type="iron_condor",
            max_loss=2000.0,  # 2% heat
            current_pnl=0.0,
            heat_percentage=0.02,
            entry_price=45000.0,
            current_price=45000.0,
            quantity=25,
            entry_time=datetime.now()
        )
        
        quantity = manager.calculate_optimal_quantity(
            max_loss_per_unit=100.0,
            current_positions=[existing_position]
        )
        
        assert quantity == 0
    
    def test_calculate_optimal_quantity_with_capacity(self):
        """Test calculate_optimal_quantity calculates correct quantity."""
        manager = PortfolioHeatManager({
            'account_balance': 100000.0,
            'max_portfolio_heat': 0.02,  # 2%
            'max_position_heat': 0.01  # 1%
        })
        
        # Existing position with 0.5% heat
        existing_position = PositionRisk(
            position_id="1",
            instrument="BANKNIFTY",
            strategy_type="iron_condor",
            max_loss=500.0,  # 0.5% heat
            current_pnl=0.0,
            heat_percentage=0.005,
            entry_price=45000.0,
            current_price=45000.0,
            quantity=25,
            entry_time=datetime.now()
        )
        
        # Available heat: 2% - 0.5% = 1.5%, capped at 1% position heat
        # Max risk: 100000 * 0.01 = 1000
        # Quantity: 1000 / 100 = 10
        max_loss_per_unit = 100.0
        
        quantity = manager.calculate_optimal_quantity(
            max_loss_per_unit,
            current_positions=[existing_position]
        )
        
        assert quantity == 10
    
    def test_calculate_optimal_quantity_zero_loss_per_unit(self):
        """Test calculate_optimal_quantity handles zero max_loss_per_unit."""
        manager = PortfolioHeatManager({'account_balance': 100000.0})
        
        quantity = manager.calculate_optimal_quantity(
            max_loss_per_unit=0.0,
            current_positions=[]
        )
        
        assert quantity == 0
    
    def test_update_position(self):
        """Test update_position updates position metrics."""
        manager = PortfolioHeatManager({'account_balance': 100000.0})
        
        position = PositionRisk(
            position_id="1",
            instrument="BANKNIFTY",
            strategy_type="iron_condor",
            max_loss=1000.0,
            current_pnl=0.0,
            heat_percentage=0.01,
            entry_price=45000.0,
            current_price=45000.0,
            quantity=25,
            entry_time=datetime.now()
        )
        
        current_price = 45200.0  # +200 points
        manager.update_position(position, current_price)
        
        assert position.current_price == current_price
        assert position.current_pnl == 200.0 * 25  # 5000
        assert position.heat_percentage == 0.01  # Based on max_loss, not P&L
    
    def test_close_position(self):
        """Test close_position closes position and updates tracking."""
        manager = PortfolioHeatManager({'account_balance': 100000.0})
        
        entry_time = datetime.now() - timedelta(hours=2)
        position = PositionRisk(
            position_id="1",
            instrument="BANKNIFTY",
            strategy_type="iron_condor",
            max_loss=1000.0,
            current_pnl=0.0,
            heat_percentage=0.01,
            entry_price=45000.0,
            current_price=45000.0,
            quantity=25,
            entry_time=entry_time
        )
        
        exit_price = 45200.0
        manager.close_position(position, exit_price)
        
        assert position.status == "closed"
        assert position.current_price == exit_price
        assert position.current_pnl == 200.0 * 25
    
    def test_get_portfolio_summary(self):
        """Test get_portfolio_summary returns correct metrics."""
        manager = PortfolioHeatManager({
            'account_balance': 100000.0,
            'max_portfolio_heat': 0.02
        })
        
        positions = [
            PositionRisk(
                position_id="1",
                instrument="BANKNIFTY",
                strategy_type="iron_condor",
                max_loss=1000.0,
                current_pnl=500.0,
                heat_percentage=0.01,
                entry_price=45000.0,
                current_price=45200.0,
                quantity=25,
                entry_time=datetime.now()
            ),
            PositionRisk(
                position_id="2",
                instrument="NIFTY",
                strategy_type="bull_call_spread",
                max_loss=500.0,
                current_pnl=-200.0,
                heat_percentage=0.005,
                entry_price=20000.0,
                current_price=19920.0,
                quantity=50,
                entry_time=datetime.now(),
                status="active"
            ),
            PositionRisk(
                position_id="3",
                instrument="BANKNIFTY",
                strategy_type="iron_condor",
                max_loss=2000.0,
                current_pnl=0.0,
                heat_percentage=0.02,
                entry_price=45000.0,
                current_price=45000.0,
                quantity=25,
                entry_time=datetime.now(),
                status="closed"
            )
        ]
        
        summary = manager.get_portfolio_summary(positions)
        
        assert summary['account_balance'] == 100000.0
        assert summary['active_positions'] == 2  # Only active positions
        assert summary['total_portfolio_heat'] == 0.015  # 1% + 0.5%
        assert summary['max_portfolio_heat'] == 0.02
        assert abs(summary['available_heat'] - 0.005) < 0.0001  # 2% - 1.5% (floating point)
        assert summary['total_max_loss'] == 1500.0  # 1000 + 500
        assert summary['total_current_pnl'] == 300.0  # 500 - 200
    
    def test_get_heat_utilization(self):
        """Test get_heat_utilization breakdown."""
        manager = PortfolioHeatManager({
            'account_balance': 100000.0,
            'max_portfolio_heat': 0.02
        })
        
        positions = [
            PositionRisk(
                position_id="1",
                instrument="BANKNIFTY",
                strategy_type="iron_condor",
                max_loss=1000.0,
                current_pnl=0.0,
                heat_percentage=0.01,
                entry_price=45000.0,
                current_price=45000.0,
                quantity=25,
                entry_time=datetime.now()
            ),
            PositionRisk(
                position_id="2",
                instrument="BANKNIFTY",
                strategy_type="bull_call_spread",
                max_loss=500.0,
                current_pnl=0.0,
                heat_percentage=0.005,
                entry_price=45000.0,
                current_price=45000.0,
                quantity=25,
                entry_time=datetime.now()
            )
        ]
        
        utilization = manager.get_heat_utilization(positions)
        
        assert utilization['total_heat'] == 0.015
        assert utilization['max_portfolio_heat'] == 0.02
        assert utilization['utilization_pct'] == 75.0  # 1.5% / 2% * 100
        assert utilization['by_strategy']['iron_condor'] == 0.01
        assert utilization['by_strategy']['bull_call_spread'] == 0.005
        assert utilization['by_instrument']['BANKNIFTY'] == 0.015
    
    def test_update_account_balance(self):
        """Test update_account_balance updates balance."""
        manager = PortfolioHeatManager({'account_balance': 100000.0})
        
        manager.update_account_balance(150000.0)
        
        assert manager.account_balance == 150000.0
    
    def test_reset_daily_pnl(self):
        """Test reset_daily_pnl resets daily tracking."""
        manager = PortfolioHeatManager({'account_balance': 100000.0})
        manager.daily_pnl = -5000.0
        
        manager.reset_daily_pnl()
        
        assert manager.daily_pnl == 0.0
        assert manager.last_reset_date == datetime.now().date()
    
    def test_reset_weekly_pnl(self):
        """Test reset_weekly_pnl resets weekly tracking."""
        manager = PortfolioHeatManager({'account_balance': 100000.0})
        manager.weekly_pnl = -10000.0
        
        manager.reset_weekly_pnl()
        
        assert manager.weekly_pnl == 0.0
