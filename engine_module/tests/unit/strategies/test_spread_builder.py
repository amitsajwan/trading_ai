"""Unit tests for SpreadBuilder utilities."""

import pytest
from engine_module.strategies.spread_builder import SpreadBuilder
from engine_module.strategies.base_strategy import (
    OptionLeg,
    OptionType,
    OrderAction
)


class TestSpreadBuilder:
    """Tests for SpreadBuilder."""
    
    def test_calculate_net_premium_credit(self):
        """Test net premium calculation - credit spread."""
        legs = [
            OptionLeg(45000, OptionType.CALL, OrderAction.SELL, 1, 100.0, "2026-01-30"),
            OptionLeg(45100, OptionType.CALL, OrderAction.BUY, 1, 80.0, "2026-01-30")
        ]
        net_premium = SpreadBuilder._calculate_net_premium(legs)
        assert net_premium == 20.0  # 100 - 80 = 20 (credit)
    
    def test_calculate_net_premium_debit(self):
        """Test net premium calculation - debit spread."""
        legs = [
            OptionLeg(45000, OptionType.CALL, OrderAction.BUY, 1, 100.0, "2026-01-30"),
            OptionLeg(45100, OptionType.CALL, OrderAction.SELL, 1, 80.0, "2026-01-30")
        ]
        net_premium = SpreadBuilder._calculate_net_premium(legs)
        assert net_premium == -20.0  # -100 + 80 = -20 (debit)
    
    def test_calculate_net_greeks(self):
        """Test net Greeks calculation."""
        legs = [
            OptionLeg(45000, OptionType.CALL, OrderAction.BUY, 1, 100.0, "2026-01-30", delta=0.5, gamma=0.01, theta=-5.0, vega=10.0),
            OptionLeg(45100, OptionType.CALL, OrderAction.SELL, 1, 80.0, "2026-01-30", delta=0.3, gamma=0.008, theta=-3.0, vega=8.0)
        ]
        net_delta, net_gamma, net_theta, net_vega, net_rho = SpreadBuilder._calculate_net_greeks(legs)
        
        # Long leg: +0.5 delta, Short leg: -0.3 delta
        assert abs(net_delta - 0.2) < 0.001  # 0.5 - 0.3 = 0.2
        assert abs(net_gamma - 0.002) < 0.001  # 0.01 - 0.008 = 0.002
        assert abs(net_theta - (-2.0)) < 0.001  # -5.0 - (-3.0) = -2.0
    
    def test_calculate_pnl_range_credit(self):
        """Test P&L range calculation - credit spread."""
        legs = [
            OptionLeg(45000, OptionType.CALL, OrderAction.SELL, 1, 100.0, "2026-01-30"),
            OptionLeg(45100, OptionType.CALL, OrderAction.BUY, 1, 80.0, "2026-01-30")
        ]
        net_premium = 20.0
        lot_size = 25
        
        max_profit, max_loss = SpreadBuilder._calculate_pnl_range(legs, net_premium, lot_size)
        
        # Credit spread: max profit = credit, max loss = spread width - credit
        spread_width = (45100 - 45000) * lot_size  # 100 * 25 = 2500
        expected_profit = net_premium * lot_size  # 20 * 25 = 500
        expected_loss = spread_width - expected_profit  # 2500 - 500 = 2000
        
        assert abs(max_profit - expected_profit) < 1.0
        assert abs(max_loss - expected_loss) < 1.0
    
    def test_calculate_pnl_range_debit(self):
        """Test P&L range calculation - debit spread."""
        legs = [
            OptionLeg(45000, OptionType.CALL, OrderAction.BUY, 1, 100.0, "2026-01-30"),
            OptionLeg(45100, OptionType.CALL, OrderAction.SELL, 1, 80.0, "2026-01-30")
        ]
        net_premium = -20.0  # Debit
        lot_size = 25
        
        max_profit, max_loss = SpreadBuilder._calculate_pnl_range(legs, net_premium, lot_size)
        
        # Debit spread: max loss = debit, max profit = spread width - debit
        spread_width = (45100 - 45000) * lot_size  # 2500
        expected_loss = abs(net_premium) * lot_size  # 20 * 25 = 500
        expected_profit = spread_width - expected_loss  # 2500 - 500 = 2000
        
        assert abs(max_loss - expected_loss) < 1.0
        assert abs(max_profit - expected_profit) < 1.0
    
    def test_calculate_breakevens_call_credit(self):
        """Test breakeven calculation - call credit spread."""
        legs = [
            OptionLeg(45000, OptionType.CALL, OrderAction.SELL, 1, 100.0, "2026-01-30"),
            OptionLeg(45100, OptionType.CALL, OrderAction.BUY, 1, 80.0, "2026-01-30")
        ]
        net_premium = 20.0
        breakevens = SpreadBuilder._calculate_breakevens(legs, net_premium)
        
        # Call credit spread: BE = short strike + premium
        expected_be = 45000 + net_premium  # 45020
        assert len(breakevens) > 0
        assert abs(breakevens[0] - expected_be) < 1.0 or any(abs(be - expected_be) < 1.0 for be in breakevens)
    
    def test_calculate_breakevens_put_credit(self):
        """Test breakeven calculation - put credit spread."""
        legs = [
            OptionLeg(44900, OptionType.PUT, OrderAction.SELL, 1, 80.0, "2026-01-30"),
            OptionLeg(44800, OptionType.PUT, OrderAction.BUY, 1, 60.0, "2026-01-30")
        ]
        net_premium = 20.0
        breakevens = SpreadBuilder._calculate_breakevens(legs, net_premium)
        
        # Put credit spread: BE = short strike - premium
        expected_be = 44900 - net_premium  # 44880
        assert len(breakevens) > 0
        assert abs(breakevens[0] - expected_be) < 1.0 or any(abs(be - expected_be) < 1.0 for be in breakevens)
    
    def test_calculate_risk_reward_ratio(self):
        """Test risk/reward ratio calculation."""
        rr = SpreadBuilder._calculate_risk_reward_ratio(500.0, 300.0)
        assert abs(rr - 1.667) < 0.01  # 500/300 = 1.667
    
    def test_calculate_risk_reward_ratio_zero_loss(self):
        """Test risk/reward ratio with zero loss."""
        rr = SpreadBuilder._calculate_risk_reward_ratio(500.0, 0.0)
        assert rr == 0.0
    
    def test_estimate_pop_credit(self):
        """Test probability of profit estimation - credit spread."""
        legs = [
            OptionLeg(45000, OptionType.CALL, OrderAction.SELL, 1, 100.0, "2026-01-30"),
            OptionLeg(45100, OptionType.CALL, OrderAction.BUY, 1, 80.0, "2026-01-30")
        ]
        breakevens = [45200]
        net_delta = 0.1
        
        pop = SpreadBuilder._estimate_pop(legs, breakevens, net_delta)
        
        # Credit spread should have higher PoP (base ~0.65)
        assert 0.0 <= pop <= 1.0
        # With delta adjustment, PoP can vary, but should be reasonable for credit spread
        assert pop >= 0.3  # Credit spreads typically have higher PoP than debit
    
    def test_estimate_pop_debit(self):
        """Test probability of profit estimation - debit spread."""
        legs = [
            OptionLeg(45000, OptionType.CALL, OrderAction.BUY, 1, 100.0, "2026-01-30"),
            OptionLeg(45100, OptionType.CALL, OrderAction.SELL, 1, 80.0, "2026-01-30")
        ]
        breakevens = [45150]
        net_delta = 0.2
        
        pop = SpreadBuilder._estimate_pop(legs, breakevens, net_delta)
        
        # Debit spread should have lower PoP (base ~0.35)
        assert 0.0 <= pop <= 1.0
        assert pop <= 0.6  # Debit spreads typically have <60% PoP
    
    def test_calculate_spread_metrics_complete(self):
        """Test complete spread metrics calculation."""
        legs = [
            OptionLeg(
                45000, OptionType.CALL, OrderAction.SELL, 1, 100.0, "2026-01-30",
                delta=0.5, gamma=0.01, theta=-5.0, vega=10.0
            ),
            OptionLeg(
                45100, OptionType.CALL, OrderAction.BUY, 1, 80.0, "2026-01-30",
                delta=0.3, gamma=0.008, theta=-3.0, vega=8.0
            )
        ]
        
        metrics = SpreadBuilder.calculate_spread_metrics(legs, lot_size=25)
        
        assert metrics.max_profit > 0
        assert metrics.max_loss > 0
        assert metrics.risk_reward_ratio > 0
        assert 0.0 <= metrics.probability_of_profit <= 1.0
        assert metrics.net_delta is not None
        assert metrics.net_theta is not None
        assert metrics.net_vega is not None
        assert len(metrics.breakeven_points) >= 0
