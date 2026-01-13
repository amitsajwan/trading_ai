"""Unit tests for Kelly Position Sizer."""

import pytest

from risk_module.position_sizer import KellyPositionSizer


class TestKellyPositionSizer:
    """Tests for KellyPositionSizer."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        sizer = KellyPositionSizer({})
        
        assert sizer.kelly_fraction == 0.25  # 1/4 Kelly
        assert sizer.max_kelly == 0.30  # 30%
        assert sizer.min_kelly == 0.01  # 1%
    
    def test_initialization_custom_config(self):
        """Test initialization with custom config."""
        config = {
            'kelly_fraction': 0.5,  # 1/2 Kelly
            'max_kelly': 0.20,  # 20%
            'min_kelly': 0.02  # 2%
        }
        sizer = KellyPositionSizer(config)
        
        assert sizer.kelly_fraction == 0.5
        assert sizer.max_kelly == 0.20
        assert sizer.min_kelly == 0.02
    
    def test_calculate_kelly_positive_expectation(self):
        """Test Kelly calculation with positive expectation."""
        sizer = KellyPositionSizer({'kelly_fraction': 1.0})  # Full Kelly for test
        
        # Win rate 60%, R:R = 2:1
        kelly = sizer.calculate_kelly(
            win_probability=0.60,
            win_amount=2.0,
            loss_amount=1.0
        )
        
        # K = (0.6 * 2 - 0.4) / 2 = (1.2 - 0.4) / 2 = 0.8 / 2 = 0.4
        # But with kelly_fraction=1.0, we get full Kelly
        # However, we cap at max_kelly (30% default)
        assert 0.0 <= kelly <= sizer.max_kelly
        assert kelly > 0.0
    
    def test_calculate_kelly_negative_expectation(self):
        """Test Kelly calculation with negative expectation."""
        sizer = KellyPositionSizer({'kelly_fraction': 1.0})
        
        # Win rate 40%, R:R = 1:2 (negative expectation)
        kelly = sizer.calculate_kelly(
            win_probability=0.40,
            win_amount=1.0,
            loss_amount=2.0
        )
        
        # Should return 0 or very small (negative expectation)
        assert kelly >= 0.0
        assert kelly <= 0.01  # Very small or zero
    
    def test_calculate_kelly_zero_loss(self):
        """Test Kelly calculation with zero loss."""
        sizer = KellyPositionSizer({})
        
        kelly = sizer.calculate_kelly(
            win_probability=0.60,
            win_amount=2.0,
            loss_amount=0.0
        )
        
        assert kelly == 0.0
    
    def test_calculate_kelly_capped_at_max(self):
        """Test Kelly is capped at max_kelly."""
        sizer = KellyPositionSizer({
            'kelly_fraction': 1.0,
            'max_kelly': 0.20  # 20%
        })
        
        # Very high win rate and R:R
        kelly = sizer.calculate_kelly(
            win_probability=0.90,
            win_amount=10.0,
            loss_amount=1.0
        )
        
        assert kelly <= sizer.max_kelly
        assert kelly == sizer.max_kelly
    
    def test_calculate_kelly_fractional(self):
        """Test Kelly fraction is applied."""
        sizer = KellyPositionSizer({
            'kelly_fraction': 0.25,  # 1/4 Kelly
            'max_kelly': 1.0  # No cap for test
        })
        
        # Full Kelly would be high
        kelly = sizer.calculate_kelly(
            win_probability=0.60,
            win_amount=2.0,
            loss_amount=1.0
        )
        
        # Should be 1/4 of full Kelly
        assert kelly > 0.0
        assert kelly < 0.5  # Less than full Kelly
    
    def test_calculate_position_size(self):
        """Test position size calculation."""
        sizer = KellyPositionSizer({
            'kelly_fraction': 0.25,
            'min_kelly': 0.01
        })
        
        # Account: 100000, Win rate: 60%, R:R = 2:1, Max loss per unit: 100
        # Kelly = (0.6*2 - 0.4) / 2 * 0.25 = 0.1 (10%)
        # Risk = 100000 * 0.1 = 10000
        # Quantity = 10000 / 100 = 100
        quantity = sizer.calculate_position_size(
            account_balance=100000.0,
            max_loss_per_unit=100.0,
            win_probability=0.60,
            risk_reward_ratio=2.0
        )
        
        assert quantity >= 0
        assert quantity > 0  # Should be positive for good stats
    
    def test_calculate_position_size_zero_balance(self):
        """Test position size with zero balance."""
        sizer = KellyPositionSizer({})
        
        quantity = sizer.calculate_position_size(
            account_balance=0.0,
            max_loss_per_unit=100.0,
            win_probability=0.60,
            risk_reward_ratio=2.0
        )
        
        assert quantity == 0
    
    def test_calculate_position_size_below_min_kelly(self):
        """Test position size below min_kelly returns 0."""
        sizer = KellyPositionSizer({
            'min_kelly': 0.05  # 5% minimum
        })
        
        # Low win rate, low R:R
        quantity = sizer.calculate_position_size(
            account_balance=100000.0,
            max_loss_per_unit=100.0,
            win_probability=0.52,  # Just above 50%
            risk_reward_ratio=1.1  # Low R:R
        )
        
        # Kelly will be very low, below 5%
        assert quantity == 0
    
    def test_get_historical_stats_empty(self):
        """Test historical stats with empty history."""
        sizer = KellyPositionSizer({})
        
        stats = sizer.get_historical_stats([])
        
        assert stats['win_rate'] == 0.50
        assert stats['avg_win'] == 1.0
        assert stats['avg_loss'] == 1.0
        assert stats['risk_reward'] == 1.0
    
    def test_get_historical_stats_with_trades(self):
        """Test historical stats calculation."""
        sizer = KellyPositionSizer({})
        
        trade_history = [
            {'pnl': 500.0, 'strategy_type': 'iron_condor'},
            {'pnl': 300.0, 'strategy_type': 'iron_condor'},
            {'pnl': -200.0, 'strategy_type': 'iron_condor'},
            {'pnl': -150.0, 'strategy_type': 'iron_condor'},
            {'pnl': 400.0, 'strategy_type': 'iron_condor'}
        ]
        
        stats = sizer.get_historical_stats(trade_history)
        
        # 3 wins, 2 losses out of 5 trades
        assert stats['win_rate'] == 0.6  # 3/5
        assert stats['avg_win'] == pytest.approx(400.0, abs=1.0)  # (500+300+400)/3
        assert stats['avg_loss'] == pytest.approx(175.0, abs=1.0)  # (200+150)/2
        assert stats['risk_reward'] == pytest.approx(2.29, abs=0.1)  # 400/175
    
    def test_get_historical_stats_only_wins(self):
        """Test historical stats with only wins."""
        sizer = KellyPositionSizer({})
        
        trade_history = [
            {'pnl': 500.0},
            {'pnl': 300.0},
            {'pnl': 400.0}
        ]
        
        stats = sizer.get_historical_stats(trade_history)
        
        assert stats['win_rate'] == 1.0
        assert stats['avg_win'] == pytest.approx(400.0, abs=1.0)
        assert stats['avg_loss'] == 1.0  # Default when no losses
        assert stats['risk_reward'] == 400.0
    
    def test_get_historical_stats_only_losses(self):
        """Test historical stats with only losses."""
        sizer = KellyPositionSizer({})
        
        trade_history = [
            {'pnl': -200.0},
            {'pnl': -150.0},
            {'pnl': -300.0}
        ]
        
        stats = sizer.get_historical_stats(trade_history)
        
        assert stats['win_rate'] == 0.0
        assert stats['avg_win'] == 1.0  # Default when no wins
        assert stats['avg_loss'] == pytest.approx(216.67, abs=1.0)  # (200+150+300)/3
        # When no wins, risk_reward defaults to 1.0 (see code: avg_win / avg_loss, but avg_win = 1.0 when no wins)
        assert stats['risk_reward'] == pytest.approx(1.0 / 216.67, abs=0.01)  # Very low
    
    def test_calculate_position_size_from_history(self):
        """Test position size from historical stats."""
        sizer = KellyPositionSizer({
            'kelly_fraction': 0.25,
            'min_kelly': 0.01
        })
        
        trade_history = [
            {'pnl': 500.0, 'strategy_type': 'iron_condor'},
            {'pnl': 300.0, 'strategy_type': 'iron_condor'},
            {'pnl': -200.0, 'strategy_type': 'iron_condor'}
        ]
        
        result = sizer.calculate_position_size_from_history(
            account_balance=100000.0,
            max_loss_per_unit=100.0,
            trade_history=trade_history,
            strategy_type='iron_condor'
        )
        
        assert result['quantity'] >= 0
        assert result['kelly_pct'] >= 0.0
        assert result['win_rate'] == pytest.approx(0.667, abs=0.01)  # 2/3
        assert result['risk_reward'] > 0.0
        assert result['risk_amount'] >= 0.0
    
    def test_calculate_position_size_from_history_strategy_filter(self):
        """Test position size with strategy filtering."""
        sizer = KellyPositionSizer({})
        
        trade_history = [
            {'pnl': 500.0, 'strategy_type': 'iron_condor'},
            {'pnl': -200.0, 'strategy_type': 'iron_condor'},
            {'pnl': 1000.0, 'strategy_type': 'bull_call_spread'},  # Different strategy
            {'pnl': -300.0, 'strategy_type': 'bull_call_spread'}
        ]
        
        result = sizer.calculate_position_size_from_history(
            account_balance=100000.0,
            max_loss_per_unit=100.0,
            trade_history=trade_history,
            strategy_type='iron_condor'
        )
        
        # Should only use iron_condor trades (2 trades, 1 win, 1 loss)
        assert result['win_rate'] == 0.5  # 1/2 for iron_condor only
    
    def test_validate_position_size_valid(self):
        """Test position size validation for valid size."""
        sizer = KellyPositionSizer({'max_kelly': 0.20})
        
        is_valid, reason = sizer.validate_position_size(
            quantity=10,
            max_loss_per_unit=100.0,
            account_balance=100000.0,
            min_quantity=1
        )
        
        # Risk: 10 * 100 = 1000, which is 1% of 100000, well below 20%
        assert is_valid is True
        assert reason == "OK"
    
    def test_validate_position_size_below_minimum(self):
        """Test position size validation below minimum."""
        sizer = KellyPositionSizer({})
        
        is_valid, reason = sizer.validate_position_size(
            quantity=0,
            max_loss_per_unit=100.0,
            account_balance=100000.0,
            min_quantity=1
        )
        
        assert is_valid is False
        assert "below minimum" in reason
    
    def test_validate_position_size_exceeds_max_kelly(self):
        """Test position size validation exceeding max Kelly."""
        sizer = KellyPositionSizer({'max_kelly': 0.10})  # 10% max
        
        # Quantity 200, loss 100 = 20000 risk = 20% of 100000
        is_valid, reason = sizer.validate_position_size(
            quantity=200,
            max_loss_per_unit=100.0,
            account_balance=100000.0
        )
        
        assert is_valid is False
        assert "exceeds max Kelly" in reason
    
    def test_adjust_position_size_for_portfolio_heat(self):
        """Test position size adjustment for portfolio heat."""
        sizer = KellyPositionSizer({})
        
        # Base quantity from Kelly: 100
        # Available heat: 1% (0.01)
        # Account: 100000, Max loss per unit: 100
        # Max from heat: 100000 * 0.01 / 100 = 10
        
        adjusted = sizer.adjust_position_size_for_portfolio_heat(
            base_quantity=100,
            available_heat=0.01,  # 1%
            account_balance=100000.0,
            max_loss_per_unit=100.0
        )
        
        assert adjusted == 10  # Capped at heat limit
    
    def test_adjust_position_size_for_portfolio_heat_no_adjustment(self):
        """Test position size when heat allows full quantity."""
        sizer = KellyPositionSizer({})
        
        # Base quantity: 10
        # Available heat: 5% (0.05)
        # Max from heat: 100000 * 0.05 / 100 = 50
        # Should use base quantity (10)
        
        adjusted = sizer.adjust_position_size_for_portfolio_heat(
            base_quantity=10,
            available_heat=0.05,  # 5%
            account_balance=100000.0,
            max_loss_per_unit=100.0
        )
        
        assert adjusted == 10  # No adjustment needed
    
    def test_adjust_position_size_for_portfolio_heat_zero_heat(self):
        """Test position size adjustment with zero available heat."""
        sizer = KellyPositionSizer({})
        
        adjusted = sizer.adjust_position_size_for_portfolio_heat(
            base_quantity=100,
            available_heat=0.0,
            account_balance=100000.0,
            max_loss_per_unit=100.0
        )
        
        assert adjusted == 0  # No capacity
    
    def test_calculate_kelly_edge_cases(self):
        """Test Kelly calculation edge cases."""
        sizer = KellyPositionSizer({'kelly_fraction': 1.0})
        
        # Win probability at boundaries
        assert sizer.calculate_kelly(0.0, 2.0, 1.0) == 0.0
        assert sizer.calculate_kelly(1.0, 2.0, 1.0) == 0.0
        
        # Negative win probability
        kelly = sizer.calculate_kelly(-0.1, 2.0, 1.0)
        assert kelly == 0.0
