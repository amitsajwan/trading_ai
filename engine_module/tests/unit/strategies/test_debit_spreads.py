"""Unit tests for Debit Spread Strategies."""

import pytest
from engine_module.strategies.debit_spreads import (
    BullCallSpreadStrategy,
    BearPutSpreadStrategy
)
from engine_module.strategies.base_strategy import OptionLeg, OptionType, OrderAction


class TestBullCallSpreadStrategy:
    """Tests for Bull Call Spread (Debit)."""
    
    def test_build_spread_success(self):
        """Test successful Bull Call Spread build."""
        strategy = BullCallSpreadStrategy()
        spot_price = 45000
        expiry = "2026-01-30"
        
        # Bull Call Spread: Buy lower strike call, sell higher strike call
        # Call long: 45000 * (1 - 0.005) = 44775 (ATM/slightly ITM)
        # Call short: 45000 * (1 + 0.02) = 45900 (2% OTM)
        
        # Option chain keys must be strings (get_option_data converts to string)
        option_chain = {
            "44775": {  # Lower strike (long call) - ATM/slightly ITM
                "CE": {
                    "last_price": 120.0,
                    "volume": 250,
                    "oi": 1000,
                    "expiry": expiry
                }
            },
            "45900": {  # Higher strike (short call) - 2% OTM
                "CE": {
                    "last_price": 60.0,
                    "volume": 150,
                    "oi": 700,
                    "expiry": expiry
                }
            }
        }
        
        legs = strategy.build_spread(spot_price, option_chain, expiry)
        
        assert legs is not None
        assert len(legs) == 2
        
        calls = [leg for leg in legs if leg.option_type == OptionType.CALL]
        assert len(calls) == 2
        
        long_call = [leg for leg in calls if leg.action == OrderAction.BUY][0]
        short_call = [leg for leg in calls if leg.action == OrderAction.SELL][0]
        
        # Long strike should be lower than short strike (both calls)
        assert long_call.strike < short_call.strike
    
    def test_calculate_metrics(self):
        """Test Bull Call Spread metrics."""
        strategy = BullCallSpreadStrategy()
        expiry = "2026-01-30"
        
        # Debit spread: Buy 44775 @ 120, Sell 45900 @ 60
        legs = [
            OptionLeg(44775, OptionType.CALL, OrderAction.BUY, 1, 120.0, expiry),
            OptionLeg(45900, OptionType.CALL, OrderAction.SELL, 1, 60.0, expiry)
        ]
        
        metrics = strategy.calculate_metrics(legs)
        
        # Net debit = 120 - 60 = 60
        net_debit = 60.0
        assert abs(metrics.net_premium - (-net_debit * 25)) < 1.0  # Negative for debit
        
        # Max loss = net debit
        assert abs(metrics.max_loss - (net_debit * 25)) < 1.0  # 1500
        
        # Max profit = spread width - debit = (45900 - 44775) * 25 - 1500 = 27125
        spread_width = (45900 - 44775) * 25  # 28125
        expected_profit = spread_width - (net_debit * 25)  # 28125 - 1500 = 26625
        assert abs(metrics.max_profit - expected_profit) < 10.0  # Allow tolerance


class TestBearPutSpreadStrategy:
    """Tests for Bear Put Spread (Debit)."""
    
    def test_build_spread_success(self):
        """Test successful Bear Put Spread build."""
        strategy = BearPutSpreadStrategy()
        spot_price = 45000
        expiry = "2026-01-30"
        
        # Bear Put Spread: Buy higher strike put, sell lower strike put
        # Put long: 45000 * (1 + 0.005) = 45225 (ATM/slightly ITM)
        # Put short: 45000 * (1 - 0.02) = 44100 (2% OTM)
        
        # Option chain keys must be strings (get_option_data converts to string)
        option_chain = {
            "45225": {  # Higher strike (long put) - ATM/slightly ITM
                "PE": {
                    "last_price": 110.0,
                    "volume": 220,
                    "oi": 900,
                    "expiry": expiry
                }
            },
            "44100": {  # Lower strike (short put) - 2% OTM
                "PE": {
                    "last_price": 55.0,
                    "volume": 130,
                    "oi": 650,
                    "expiry": expiry
                }
            }
        }
        
        legs = strategy.build_spread(spot_price, option_chain, expiry)
        
        assert legs is not None
        assert len(legs) == 2
        
        puts = [leg for leg in legs if leg.option_type == OptionType.PUT]
        assert len(puts) == 2
        
        long_put = [leg for leg in puts if leg.action == OrderAction.BUY][0]
        short_put = [leg for leg in puts if leg.action == OrderAction.SELL][0]
        
        # Long strike should be higher than short strike (both puts)
        assert long_put.strike > short_put.strike
    
    def test_calculate_metrics(self):
        """Test Bear Put Spread metrics."""
        strategy = BearPutSpreadStrategy()
        expiry = "2026-01-30"
        
        # Debit spread: Buy 45225 @ 110, Sell 44100 @ 55
        legs = [
            OptionLeg(45225, OptionType.PUT, OrderAction.BUY, 1, 110.0, expiry),
            OptionLeg(44100, OptionType.PUT, OrderAction.SELL, 1, 55.0, expiry)
        ]
        
        metrics = strategy.calculate_metrics(legs)
        
        # Net debit = 110 - 55 = 55
        net_debit = 55.0
        assert abs(metrics.net_premium - (-net_debit * 25)) < 1.0  # Negative for debit
        
        # Max loss = net debit
        assert abs(metrics.max_loss - (net_debit * 25)) < 1.0  # 1375
        
        # Max profit = spread width - debit = (45225 - 44100) * 25 - 1375 = 26700
        spread_width = (45225 - 44100) * 25  # 28125
        expected_profit = spread_width - (net_debit * 25)  # 28125 - 1375 = 26750
        assert abs(metrics.max_profit - expected_profit) < 10.0  # Allow tolerance
