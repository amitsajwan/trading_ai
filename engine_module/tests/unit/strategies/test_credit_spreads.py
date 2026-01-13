"""Unit tests for Credit Spread Strategies."""

import pytest
from engine_module.strategies.credit_spreads import (
    BullCallSpreadStrategy as BullPutSpreadCreditStrategy,
    BearPutSpreadStrategy as BearCallSpreadCreditStrategy
)
from engine_module.strategies.base_strategy import OptionLeg, OptionType, OrderAction


class TestBullPutSpreadCreditStrategy:
    """Tests for Bull Put Spread (Credit)."""
    
    def test_build_spread_success(self):
        """Test successful Bull Put Spread build."""
        strategy = BullPutSpreadCreditStrategy()
        spot_price = 45000
        expiry = "2026-01-30"
        
        # Bull Put Spread: Sell higher strike put, buy lower strike put
        # Put short: 45000 * (1 - 0.01) = 44550
        # Put long: 45000 * (1 - 0.01 - 0.005) = 44325 (will find closest)
        # Need strikes where short > long (for puts, higher strike = less OTM)
        # Use strikes that are properly separated
        option_chain = {
            "44300": {  # Lower strike (long put) - closest to 44325 target, must be < 44550
                "PE": {
                    "last_price": 50.0,
                    "volume": 150,
                    "oi": 600,
                    "expiry": expiry
                }
            },
            "44550": {  # Higher strike (short put) - 1% OTM = 44550
                "PE": {
                    "last_price": 100.0,
                    "volume": 200,
                    "oi": 800,
                    "expiry": expiry
                }
            }
        }
        
        legs = strategy.build_spread(spot_price, option_chain, expiry)
        
        assert legs is not None
        assert len(legs) == 2
        
        puts = [leg for leg in legs if leg.option_type == OptionType.PUT]
        assert len(puts) == 2
        
        short_put = [leg for leg in puts if leg.action == OrderAction.SELL][0]
        long_put = [leg for leg in puts if leg.action == OrderAction.BUY][0]
        
        # Short strike should be higher than long strike (both puts)
        assert short_put.strike > long_put.strike
        assert short_put.strike == 44550
        assert long_put.strike == 44300
    
    def test_build_spread_insufficient_liquidity(self):
        """Test Bull Put Spread with insufficient liquidity."""
        strategy = BullPutSpreadCreditStrategy({'min_option_volume': 500})
        spot_price = 45000
        
        option_chain = {
            "44300": {
                "PE": {
                    "last_price": 50.0,
                    "volume": 50,  # Below minimum
                    "oi": 600
                }
            },
            "44550": {
                "PE": {
                    "last_price": 100.0,
                    "volume": 200,
                    "oi": 800
                }
            }
        }
        
        legs = strategy.build_spread(spot_price, option_chain)
        assert legs is None
    
    def test_calculate_metrics(self):
        """Test Bull Put Spread metrics."""
        strategy = BullPutSpreadCreditStrategy()
        expiry = "2026-01-30"
        
        # Credit spread: Sell 44550 @ 100, Buy 44300 @ 50
        legs = [
            OptionLeg(44550, OptionType.PUT, OrderAction.SELL, 1, 100.0, expiry),
            OptionLeg(44300, OptionType.PUT, OrderAction.BUY, 1, 50.0, expiry)
        ]
        
        metrics = strategy.calculate_metrics(legs)
        
        # Net credit = 100 - 50 = 50
        net_credit = 50.0
        assert abs(metrics.net_premium - (net_credit * 25)) < 1.0
        
        # Max profit = net credit
        assert abs(metrics.max_profit - (net_credit * 25)) < 1.0
        
        # Max loss = spread width - credit = (44550 - 44300) * 25 - 2500 = 3750
        spread_width = (44550 - 44300) * 25  # 6250
        expected_loss = spread_width - (net_credit * 25)  # 6250 - 2500 = 3750
        assert abs(metrics.max_loss - expected_loss) < 1.0


class TestBearCallSpreadCreditStrategy:
    """Tests for Bear Call Spread (Credit)."""
    
    def test_build_spread_success(self):
        """Test successful Bear Call Spread build."""
        strategy = BearCallSpreadCreditStrategy()
        spot_price = 45000
        expiry = "2026-01-30"
        
        # Bear Call Spread: Sell lower strike call, buy higher strike call
        # Call short: 45000 * (1 + 0.01) = 45450
        # Call long: 45000 * (1 + 0.01 + 0.005) = 45675 (will find closest)
        # Need strikes where short < long (for calls, lower strike = less OTM)
        # Use strikes that are properly separated
        option_chain = {
            "45450": {  # Lower strike (short call) - 1% OTM = 45450
                "CE": {
                    "last_price": 90.0,
                    "volume": 180,
                    "oi": 750,
                    "expiry": expiry
                }
            },
            "45700": {  # Higher strike (long call) - closest to 45675 target, must be > 45450
                "CE": {
                    "last_price": 50.0,
                    "volume": 120,
                    "oi": 500,
                    "expiry": expiry
                }
            }
        }
        
        legs = strategy.build_spread(spot_price, option_chain, expiry)
        
        assert legs is not None
        assert len(legs) == 2
        
        calls = [leg for leg in legs if leg.option_type == OptionType.CALL]
        assert len(calls) == 2
        
        short_call = [leg for leg in calls if leg.action == OrderAction.SELL][0]
        long_call = [leg for leg in calls if leg.action == OrderAction.BUY][0]
        
        # Short strike should be lower than long strike (both calls)
        assert short_call.strike < long_call.strike
        assert short_call.strike == 45450
        assert long_call.strike in [45700, 45675, 45600]  # Closest to calculated target (45675), must be > 45450
    
    def test_calculate_metrics(self):
        """Test Bear Call Spread metrics."""
        strategy = BearCallSpreadCreditStrategy()
        expiry = "2026-01-30"
        
        # Credit spread: Sell 45450 @ 90, Buy 45700 @ 50
        legs = [
            OptionLeg(45450, OptionType.CALL, OrderAction.SELL, 1, 90.0, expiry),
            OptionLeg(45700, OptionType.CALL, OrderAction.BUY, 1, 50.0, expiry)
        ]
        
        metrics = strategy.calculate_metrics(legs)
        
        # Net credit = 90 - 50 = 40
        net_credit = 40.0
        assert abs(metrics.net_premium - (net_credit * 25)) < 1.0
        
        # Max profit = net credit
        assert abs(metrics.max_profit - (net_credit * 25)) < 1.0
        
        # Max loss = spread width - credit = (45700 - 45450) * 25 - 1000 = 5250
        spread_width = (45700 - 45450) * 25  # 6250
        expected_loss = spread_width - (net_credit * 25)  # 6250 - 1000 = 5250
        assert abs(metrics.max_loss - expected_loss) < 1.0
