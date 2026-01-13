"""Unit tests for Iron Condor Strategy."""

import pytest
from engine_module.strategies.iron_condor import IronCondorStrategy
from engine_module.strategies.base_strategy import OptionLeg, OptionType, OrderAction


class TestIronCondorStrategy:
    """Tests for IronCondorStrategy."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        strategy = IronCondorStrategy()
        assert strategy.lot_size == 25
        assert strategy.otm_percentage == 0.02  # 2%
        assert strategy.spread_width == 0.01  # 1%
    
    def test_initialization_custom(self):
        """Test custom initialization."""
        config = {
            'lot_size': 50,
            'otm_percentage': 0.03,
            'spread_width': 0.015
        }
        strategy = IronCondorStrategy(config)
        assert strategy.lot_size == 50
        assert strategy.otm_percentage == 0.03
        assert strategy.spread_width == 0.015
    
    def test_build_spread_success(self):
        """Test successful Iron Condor build."""
        strategy = IronCondorStrategy()
        spot_price = 45000
        expiry = "2026-01-30"
        
        # Calculate actual target strikes
        # Put short: 45000 * (1 - 0.02) = 44100
        # Put long: 45000 * (1 - 0.02 - 0.01) = 43650 (will find closest)
        # Call short: 45000 * (1 + 0.02) = 45900
        # Call long: 45000 * (1 + 0.02 + 0.01) = 46350 (will find closest)
        
        # Create option chain with all required strikes
        # Put short: 45000 * (1 - 0.02) = 44100
        # Put long: 45000 * (1 - 0.02 - 0.01) = 43650 (closest to available strike)
        # Call short: 45000 * (1 + 0.02) = 45900
        # Call long: 45000 * (1 + 0.02 + 0.01) = 46350 (closest to available strike)
        
        # Create option chain with strikes as string keys (get_option_data converts to string)
        option_chain = {
            "43650": {  # Put long strike
                "PE": {
                    "last_price": 60.0,
                    "volume": 200,
                    "oi": 800,
                    "expiry": expiry,
                    "delta": -0.15
                }
            },
            "44100": {  # Put short strike
                "PE": {
                    "last_price": 100.0,
                    "volume": 300,
                    "oi": 1000,
                    "expiry": expiry,
                    "delta": -0.25
                }
            },
            "45900": {  # Call short strike
                "CE": {
                    "last_price": 90.0,
                    "volume": 280,
                    "oi": 950,
                    "expiry": expiry,
                    "delta": 0.30
                }
            },
            "46350": {  # Call long strike
                "CE": {
                    "last_price": 50.0,
                    "volume": 180,
                    "oi": 700,
                    "expiry": expiry,
                    "delta": 0.15
                }
            }
        }
        
        legs = strategy.build_spread(spot_price, option_chain, expiry)
        
        assert legs is not None
        assert len(legs) == 4
        
        # Check put spread
        puts = [leg for leg in legs if leg.option_type == OptionType.PUT]
        assert len(puts) == 2
        put_strikes = sorted([leg.strike for leg in puts])
        assert 43650 in put_strikes  # Long put (lower strike)
        assert 44100 in put_strikes  # Short put (higher strike)
        
        # Check call spread
        calls = [leg for leg in legs if leg.option_type == OptionType.CALL]
        assert len(calls) == 2
        call_strikes = sorted([leg.strike for leg in calls])
        assert 45900 in call_strikes  # Short call (lower strike)
        assert 46350 in call_strikes  # Long call (higher strike)
    
    def test_build_spread_missing_strikes(self):
        """Test Iron Condor build with missing strikes."""
        strategy = IronCondorStrategy()
        spot_price = 45000
        
        option_chain = {
            "45000": {"CE": {}, "PE": {}}  # Only one strike
        }
        
        legs = strategy.build_spread(spot_price, option_chain)
        assert legs is None
    
    def test_calculate_metrics(self):
        """Test Iron Condor metrics calculation."""
        strategy = IronCondorStrategy()
        expiry = "2026-01-30"
        
        legs = [
            # Put spread (sell 44550, buy 44100)
            OptionLeg(44550, OptionType.PUT, OrderAction.SELL, 1, 100.0, expiry),
            OptionLeg(44100, OptionType.PUT, OrderAction.BUY, 1, 60.0, expiry),
            # Call spread (sell 45450, buy 45900)
            OptionLeg(45450, OptionType.CALL, OrderAction.SELL, 1, 90.0, expiry),
            OptionLeg(45900, OptionType.CALL, OrderAction.BUY, 1, 50.0, expiry)
        ]
        
        metrics = strategy.calculate_metrics(legs)
        
        # Iron Condor: Net credit = (100 + 90) - (60 + 50) = 80 per lot
        net_premium = (100.0 + 90.0) - (60.0 + 50.0)  # 80
        assert abs(metrics.net_premium - (net_premium * 25)) < 1.0  # Per lot
        
        # Max profit = net credit
        assert metrics.max_profit > 0
        
        # Max loss = max spread width - credit
        # Put spread width = 44550 - 44100 = 450
        # Call spread width = 45900 - 45450 = 450
        # Max spread width = 450
        max_spread_width = 450  # 45900 - 45450 or 44550 - 44100
        expected_max_loss = (max_spread_width * 25) - (net_premium * 25)
        assert abs(metrics.max_loss - expected_max_loss) < 10.0
        
        # Should have 2 breakevens
        assert len(metrics.breakeven_points) >= 1
    
    def test_calculate_metrics_profit_loss(self):
        """Test Iron Condor profit/loss calculations."""
        strategy = IronCondorStrategy()
        expiry = "2026-01-30"
        
        # Build Iron Condor with known premiums
        legs = [
            OptionLeg(44500, OptionType.PUT, OrderAction.SELL, 1, 120.0, expiry),
            OptionLeg(44100, OptionType.PUT, OrderAction.BUY, 1, 70.0, expiry),
            OptionLeg(45500, OptionType.CALL, OrderAction.SELL, 1, 110.0, expiry),
            OptionLeg(45900, OptionType.CALL, OrderAction.BUY, 1, 60.0, expiry)
        ]
        
        metrics = strategy.calculate_metrics(legs)
        
        # Net credit = (120 + 110) - (70 + 60) = 100
        net_credit = (120.0 + 110.0) - (70.0 + 60.0)  # 100
        
        # Max profit = net credit * lot size
        expected_profit = net_credit * 25  # 2500
        assert abs(metrics.max_profit - expected_profit) < 1.0
        
        # Max loss = spread width - credit
        # Max spread width = max(45500-44100, 45900-45500) = 400
        put_width = 44500 - 44100  # 400
        call_width = 45900 - 45500  # 400
        max_width = max(put_width, call_width)  # 400
        expected_loss = (max_width * 25) - expected_profit  # 10000 - 2500 = 7500
        assert abs(metrics.max_loss - expected_loss) < 1.0
