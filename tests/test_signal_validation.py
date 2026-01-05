"""Tests for signal validation utilities."""

import pytest
from utils.signal_validation import (
    normalize_confidence,
    validate_price_sanity,
    validate_stop_loss_take_profit,
    validate_trade_signal
)


class TestNormalizeConfidence:
    """Test confidence normalization."""
    
    def test_fraction_remains_unchanged(self):
        """Confidence in 0-1 range should remain unchanged."""
        assert normalize_confidence(0.65) == 0.65
        assert normalize_confidence(0.5) == 0.5
        assert normalize_confidence(1.0) == 1.0
        assert normalize_confidence(0.0) == 0.0
    
    def test_percentage_normalized(self):
        """Confidence in 0-100 range should be divided by 100."""
        assert normalize_confidence(65) == 0.65
        assert normalize_confidence(50) == 0.5
        assert normalize_confidence(100) == 1.0
    
    def test_invalid_returns_default(self):
        """Invalid values should return 0.5."""
        assert normalize_confidence("invalid") == 0.5
        assert normalize_confidence(None) == 0.5
    
    def test_out_of_range_clamped(self):
        """Values outside valid ranges should be clamped."""
        result = normalize_confidence(150)
        assert 0 <= result <= 1


class TestValidatePriceSanity:
    """Test price sanity validation."""
    
    def test_price_within_tolerance(self):
        """Prices within tolerance should pass."""
        valid, msg = validate_price_sanity(
            entry_price=90000,
            latest_price=91000,
            tolerance_pct=0.5
        )
        assert valid
        assert "within tolerance" in msg.lower()
    
    def test_price_outside_tolerance(self):
        """Prices outside tolerance should fail."""
        valid, msg = validate_price_sanity(
            entry_price=45000,
            latest_price=90000,
            tolerance_pct=0.40  # 40% tolerance, but diff is 50%
        )
        assert not valid
        assert "differs" in msg.lower()
        assert "40%" in msg  # Should mention tolerance
    
    def test_invalid_price_fails(self):
        """Invalid prices should fail."""
        valid, msg = validate_price_sanity(
            entry_price=0,
            latest_price=90000
        )
        assert not valid
        
        valid, msg = validate_price_sanity(
            entry_price=90000,
            latest_price=0
        )
        assert not valid


class TestValidateStopLossTakeProfit:
    """Test stop loss and take profit validation."""
    
    def test_buy_signal_valid(self):
        """BUY signal with proper SL and TP should pass."""
        valid, msg = validate_stop_loss_take_profit(
            signal="BUY",
            entry_price=45250,
            stop_loss=45100,
            take_profit=45500
        )
        assert valid
    
    def test_buy_signal_invalid_sl(self):
        """BUY signal with SL above entry should fail."""
        valid, msg = validate_stop_loss_take_profit(
            signal="BUY",
            entry_price=45250,
            stop_loss=45300,  # Above entry
            take_profit=45500
        )
        assert not valid
        assert "stop loss" in msg.lower()
        assert "below entry" in msg.lower()
    
    def test_buy_signal_invalid_tp(self):
        """BUY signal with TP below entry should fail."""
        valid, msg = validate_stop_loss_take_profit(
            signal="BUY",
            entry_price=45250,
            stop_loss=45100,
            take_profit=45200  # Below entry
        )
        assert not valid
        assert "take profit" in msg.lower()
        assert "above entry" in msg.lower()
    
    def test_sell_signal_valid(self):
        """SELL signal with proper SL and TP should pass."""
        valid, msg = validate_stop_loss_take_profit(
            signal="SELL",
            entry_price=45250,
            stop_loss=45400,
            take_profit=45000
        )
        assert valid
    
    def test_sell_signal_invalid_sl(self):
        """SELL signal with SL below entry should fail."""
        valid, msg = validate_stop_loss_take_profit(
            signal="SELL",
            entry_price=45250,
            stop_loss=45100,  # Below entry
            take_profit=45000
        )
        assert not valid
        assert "stop loss" in msg.lower()
        assert "above entry" in msg.lower()


class TestValidateTradeSignal:
    """Test comprehensive trade signal validation."""
    
    def test_valid_buy_signal(self):
        """Valid BUY signal should pass all checks."""
        valid, result = validate_trade_signal(
            signal="BUY",
            entry_price=90500,
            stop_loss=90000,
            take_profit=91500,
            confidence=0.65,
            current_market_price=90700,
            tolerance_pct=0.10
        )
        assert valid
        assert result["valid"]
        assert len(result["errors"]) == 0
        assert result["normalized_confidence"] == 0.65
    
    def test_invalid_confidence_generates_warning(self):
        """Very low or high confidence should generate warnings."""
        valid, result = validate_trade_signal(
            signal="BUY",
            entry_price=90500,
            stop_loss=90000,
            take_profit=91500,
            confidence=0.15,  # Very low
            current_market_price=90700
        )
        assert len(result["warnings"]) > 0
        assert "low confidence" in result["warnings"][0].lower()
    
    def test_price_mismatch_generates_error(self):
        """Large price mismatch should generate error."""
        valid, result = validate_trade_signal(
            signal="BUY",
            entry_price=45000,  # Very different from market
            stop_loss=44900,
            take_profit=45500,
            confidence=0.65,
            current_market_price=90000,
            tolerance_pct=0.10
        )
        assert not valid
        assert len(result["errors"]) > 0
        assert any("differs" in err.lower() for err in result["errors"])
    
    def test_invalid_sl_tp_generates_error(self):
        """Invalid SL/TP should generate error."""
        valid, result = validate_trade_signal(
            signal="BUY",
            entry_price=90500,
            stop_loss=90600,  # Above entry (invalid for BUY)
            take_profit=91500,
            confidence=0.65,
            current_market_price=90700
        )
        assert not valid
        assert len(result["errors"]) > 0
        assert any("stop loss" in err.lower() for err in result["errors"])
    
    def test_confidence_normalization(self):
        """Confidence should be normalized in result."""
        # Test with percentage (0-100)
        valid, result = validate_trade_signal(
            signal="BUY",
            entry_price=90500,
            stop_loss=90000,
            take_profit=91500,
            confidence=65,  # Percentage
            current_market_price=90700
        )
        assert result["normalized_confidence"] == 0.65
