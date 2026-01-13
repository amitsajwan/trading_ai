"""Unit tests for BaseSpreadStrategy and related classes."""

import pytest
from typing import Dict, List, Optional
from engine_module.strategies.base_strategy import (
    OptionLeg,
    SpreadMetrics,
    BaseSpreadStrategy,
    OptionType,
    OrderAction
)


class TestOptionLeg:
    """Tests for OptionLeg dataclass."""
    
    def test_option_leg_creation(self):
        """Test OptionLeg creation with all fields."""
        leg = OptionLeg(
            strike=45000,
            option_type=OptionType.CALL,
            action=OrderAction.BUY,
            quantity=1,
            premium=100.0,
            expiry="2026-01-30",
            delta=0.5,
            gamma=0.01,
            theta=-5.0,
            vega=10.0,
            rho=2.0,
            iv=0.20,
            volume=1000,
            oi=5000
        )
        
        assert leg.strike == 45000
        assert leg.option_type == OptionType.CALL
        assert leg.action == OrderAction.BUY
        assert leg.quantity == 1
        assert leg.premium == 100.0
        assert leg.expiry == "2026-01-30"
        assert leg.delta == 0.5
        assert leg.iv == 0.20
    
    def test_option_leg_to_dict(self):
        """Test OptionLeg serialization."""
        leg = OptionLeg(
            strike=45000,
            option_type=OptionType.PUT,
            action=OrderAction.SELL,
            quantity=2,
            premium=80.0,
            expiry="2026-01-30"
        )
        
        leg_dict = leg.to_dict()
        assert leg_dict['strike'] == 45000
        assert leg_dict['option_type'] == 'PE'
        assert leg_dict['action'] == 'SELL'
        assert leg_dict['quantity'] == 2
        assert leg_dict['premium'] == 80.0


class TestSpreadMetrics:
    """Tests for SpreadMetrics dataclass."""
    
    def test_spread_metrics_creation(self):
        """Test SpreadMetrics creation."""
        metrics = SpreadMetrics(
            max_profit=5000.0,
            max_loss=3000.0,
            breakeven_points=[44800, 45200],
            net_premium=100.0,
            margin_required=2500.0,
            risk_reward_ratio=1.67,
            probability_of_profit=0.65,
            net_delta=0.1,
            net_gamma=0.05,
            net_theta=-10.0,
            net_vega=5.0,
            net_rho=1.0
        )
        
        assert metrics.max_profit == 5000.0
        assert metrics.max_loss == 3000.0
        assert len(metrics.breakeven_points) == 2
        assert metrics.risk_reward_ratio == 1.67
        assert metrics.probability_of_profit == 0.65
    
    def test_spread_metrics_to_dict(self):
        """Test SpreadMetrics serialization."""
        metrics = SpreadMetrics(
            max_profit=5000.0,
            max_loss=3000.0,
            breakeven_points=[44800, 45200]
        )
        
        metrics_dict = metrics.to_dict()
        assert metrics_dict['max_profit'] == 5000.0
        assert metrics_dict['max_loss'] == 3000.0
        assert len(metrics_dict['breakeven_points']) == 2


class MockSpreadStrategy(BaseSpreadStrategy):
    """Mock strategy for testing BaseSpreadStrategy."""
    
    def build_spread(self, spot_price: float, option_chain: Dict, expiry: Optional[str] = None):
        """Mock build_spread implementation."""
        return None
    
    def calculate_metrics(self, legs: List[OptionLeg]) -> SpreadMetrics:
        """Mock calculate_metrics implementation."""
        return SpreadMetrics(max_profit=0.0, max_loss=0.0)


class TestBaseSpreadStrategy:
    """Tests for BaseSpreadStrategy."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        strategy = MockSpreadStrategy()
        assert strategy.lot_size == 25
        assert strategy.min_option_volume == 100
        assert strategy.min_option_oi == 500
        assert strategy.min_risk_reward == 0.3
        assert strategy.min_probability_of_profit == 0.50
    
    def test_initialization_custom(self):
        """Test custom initialization."""
        config = {
            'lot_size': 50,
            'min_option_volume': 200,
            'min_option_oi': 1000,
            'min_risk_reward': 0.5,
            'min_probability_of_profit': 0.60
        }
        strategy = MockSpreadStrategy(config)
        assert strategy.lot_size == 50
        assert strategy.min_option_volume == 200
        assert strategy.min_option_oi == 1000
    
    def test_validate_liquidity_pass(self):
        """Test liquidity validation - passes."""
        strategy = MockSpreadStrategy()
        leg = OptionLeg(
            strike=45000,
            option_type=OptionType.CALL,
            action=OrderAction.BUY,
            quantity=1,
            premium=100.0,
            expiry="2026-01-30"
        )
        option_data = {
            'volume': 150,
            'oi': 800,
            'last_price': 100.0
        }
        assert strategy.validate_liquidity(leg, option_data) is True
    
    def test_validate_liquidity_fail_volume(self):
        """Test liquidity validation - fails volume check."""
        strategy = MockSpreadStrategy()
        leg = OptionLeg(
            strike=45000,
            option_type=OptionType.CALL,
            action=OrderAction.BUY,
            quantity=1,
            premium=100.0,
            expiry="2026-01-30"
        )
        option_data = {
            'volume': 50,  # Below minimum
            'oi': 800,
            'last_price': 100.0
        }
        assert strategy.validate_liquidity(leg, option_data) is False
    
    def test_validate_liquidity_fail_oi(self):
        """Test liquidity validation - fails OI check."""
        strategy = MockSpreadStrategy()
        leg = OptionLeg(
            strike=45000,
            option_type=OptionType.CALL,
            action=OrderAction.BUY,
            quantity=1,
            premium=100.0,
            expiry="2026-01-30"
        )
        option_data = {
            'volume': 150,
            'oi': 300,  # Below minimum
            'last_price': 100.0
        }
        assert strategy.validate_liquidity(leg, option_data) is False
    
    def test_validate_spread_pass(self):
        """Test spread validation - passes all criteria."""
        strategy = MockSpreadStrategy()
        legs = []
        metrics = SpreadMetrics(
            max_profit=5000.0,
            max_loss=3000.0,
            risk_reward_ratio=1.67,
            probability_of_profit=0.65,
            net_delta=0.1
        )
        assert strategy.validate_spread(legs, metrics) is True
    
    def test_validate_spread_fail_rr(self):
        """Test spread validation - fails risk/reward check."""
        strategy = MockSpreadStrategy()
        legs = []
        metrics = SpreadMetrics(
            max_profit=500.0,
            max_loss=3000.0,
            risk_reward_ratio=0.17,  # Below minimum 0.3
            probability_of_profit=0.65,
            net_delta=0.1
        )
        assert strategy.validate_spread(legs, metrics) is False
    
    def test_validate_spread_fail_pop(self):
        """Test spread validation - fails PoP check."""
        strategy = MockSpreadStrategy()
        legs = []
        metrics = SpreadMetrics(
            max_profit=5000.0,
            max_loss=3000.0,
            risk_reward_ratio=1.67,
            probability_of_profit=0.40,  # Below minimum 0.50
            net_delta=0.1
        )
        assert strategy.validate_spread(legs, metrics) is False
    
    def test_validate_spread_fail_delta(self):
        """Test spread validation - fails delta neutrality check."""
        strategy = MockSpreadStrategy()
        legs = []
        metrics = SpreadMetrics(
            max_profit=5000.0,
            max_loss=3000.0,
            risk_reward_ratio=1.67,
            probability_of_profit=0.65,
            net_delta=0.3  # Above maximum 0.2
        )
        assert strategy.validate_spread(legs, metrics) is False
    
    def test_find_strike(self):
        """Test finding closest strike."""
        strategy = MockSpreadStrategy()
        option_chain = {
            "44800": {"CE": {}, "PE": {}},
            "44900": {"CE": {}, "PE": {}},
            "45000": {"CE": {}, "PE": {}},
            "45100": {"CE": {}, "PE": {}},
            "45200": {"CE": {}, "PE": {}}
        }
        
        # Find closest to target
        # 44950 - 45000 = 50, 44950 - 44900 = 50 (equidistant)
        # min() picks first in case of tie, so it depends on iteration order
        # Just verify it returns one of the closest strikes
        strike = strategy.find_strike(44950, option_chain)
        assert strike in [44900, 45000]  # Either is valid (equidistant)
        
        # Test with value closer to lower strike
        strike = strategy.find_strike(44910, option_chain)
        assert strike == 44900  # Closest (44910 - 44900 = 10 < 44910 - 45000 = 90)
        
        # Exact match
        strike = strategy.find_strike(45000, option_chain)
        assert strike == 45000
    
    def test_get_option_data(self):
        """Test getting option data for strike and type."""
        strategy = MockSpreadStrategy()
        option_chain = {
            "45000": {
                "CE": {
                    "last_price": 100.0,
                    "delta": 0.5
                },
                "PE": {
                    "last_price": 80.0,
                    "delta": -0.5
                }
            }
        }
        
        # Get call data
        call_data = strategy.get_option_data(45000, OptionType.CALL, option_chain)
        assert call_data is not None
        assert call_data['last_price'] == 100.0
        assert call_data['delta'] == 0.5
        
        # Get put data
        put_data = strategy.get_option_data(45000, OptionType.PUT, option_chain)
        assert put_data is not None
        assert put_data['last_price'] == 80.0
        assert put_data['delta'] == -0.5
        
        # Non-existent strike
        data = strategy.get_option_data(46000, OptionType.CALL, option_chain)
        assert data is None
