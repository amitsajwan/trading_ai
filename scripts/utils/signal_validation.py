"""Signal validation utilities to prevent incorrect data in trading signals."""

import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


def normalize_confidence(conf: float) -> float:
    """
    Normalize confidence value to 0-1 range.
    
    If confidence is already in 0-1 range, return as-is.
    If confidence is in 0-100 range, divide by 100.
    
    Args:
        conf: Confidence value (either 0-1 or 0-100)
    
    Returns:
        Normalized confidence in 0-1 range
    """
    try:
        c = float(conf)
    except (TypeError, ValueError):
        logger.warning(f"Invalid confidence value: {conf}, defaulting to 0.5")
        return 0.5
    
    # Already in 0-1 range
    if 0 <= c <= 1:
        return c
    
    # In 0-100 range, normalize
    if 0 <= c <= 100:
        return c / 100.0
    
    # Out of valid range
    logger.warning(f"Confidence value {c} out of valid range, clamping to 0-1")
    return max(0.0, min(1.0, c / 100.0))


def validate_price_sanity(
    entry_price: float,
    latest_price: float,
    tolerance_pct: float = 0.50
) -> Tuple[bool, str]:
    """
    Validate that entry price is reasonably close to latest market price.
    
    Args:
        entry_price: Proposed entry price for trade
        latest_price: Current market price
        tolerance_pct: Maximum allowed deviation (default 50%)
    
    Returns:
        (is_valid, message) tuple
    """
    try:
        e = float(entry_price)
        l = float(latest_price)
    except (TypeError, ValueError) as ex:
        return False, f"Price parse error: {ex}"
    
    if l <= 0:
        return False, "Latest market price unavailable or invalid"
    
    if e <= 0:
        return False, "Entry price invalid (must be > 0)"
    
    diff_pct = abs(e - l) / l
    
    if diff_pct > tolerance_pct:
        return False, (
            f"Entry price {e:,.2f} differs from market price {l:,.2f} "
            f"by {diff_pct*100:.1f}% (exceeds {tolerance_pct*100:.0f}% tolerance)"
        )
    
    return True, "Price within tolerance"


def validate_stop_loss_take_profit(
    signal: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float
) -> Tuple[bool, str]:
    """
    Validate that stop loss and take profit are logical for the signal direction.
    
    For BUY: stop_loss < entry_price < take_profit
    For SELL: stop_loss > entry_price > take_profit
    
    Args:
        signal: Trade signal (BUY or SELL)
        entry_price: Entry price
        stop_loss: Stop loss price
        take_profit: Take profit price
    
    Returns:
        (is_valid, message) tuple
    """
    try:
        e = float(entry_price)
        sl = float(stop_loss)
        tp = float(take_profit)
    except (TypeError, ValueError) as ex:
        return False, f"Price parse error: {ex}"
    
    if signal == "BUY":
        if sl >= e:
            return False, f"BUY signal: stop loss ({sl:,.2f}) must be below entry ({e:,.2f})"
        if tp <= e:
            return False, f"BUY signal: take profit ({tp:,.2f}) must be above entry ({e:,.2f})"
    elif signal == "SELL":
        if sl <= e:
            return False, f"SELL signal: stop loss ({sl:,.2f}) must be above entry ({e:,.2f})"
        if tp >= e:
            return False, f"SELL signal: take profit ({tp:,.2f}) must be below entry ({e:,.2f})"
    
    return True, "Stop loss and take profit are valid"


def validate_trade_signal(
    signal: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    confidence: float,
    current_market_price: float = None,
    tolerance_pct: float = 0.50
) -> Tuple[bool, Dict[str, Any]]:
    """
    Comprehensive validation of a trading signal.
    
    Args:
        signal: Trade signal (BUY/SELL/HOLD)
        entry_price: Entry price
        stop_loss: Stop loss price
        take_profit: Take profit price
        confidence: Confidence level (0-1 or 0-100)
        current_market_price: Current market price (for sanity check)
        tolerance_pct: Price deviation tolerance
    
    Returns:
        (is_valid, validation_result) where validation_result contains:
        - valid: bool
        - errors: list of error messages
        - warnings: list of warning messages
        - normalized_confidence: normalized confidence (0-1)
    """
    errors = []
    warnings = []
    
    # Normalize confidence
    normalized_conf = normalize_confidence(confidence)
    
    # Validate confidence is reasonable (warn if <20% or >95%)
    if normalized_conf < 0.20:
        warnings.append(f"Very low confidence: {normalized_conf*100:.1f}%")
    elif normalized_conf > 0.95:
        warnings.append(f"Unusually high confidence: {normalized_conf*100:.1f}%")
    
    # Validate stop loss and take profit logic
    if signal in ["BUY", "SELL"]:
        sl_tp_valid, sl_tp_msg = validate_stop_loss_take_profit(
            signal, entry_price, stop_loss, take_profit
        )
        if not sl_tp_valid:
            errors.append(sl_tp_msg)
    
    # Validate price sanity if market price provided
    if current_market_price and signal in ["BUY", "SELL"]:
        price_valid, price_msg = validate_price_sanity(
            entry_price, current_market_price, tolerance_pct
        )
        if not price_valid:
            errors.append(price_msg)
    
    is_valid = len(errors) == 0
    
    return is_valid, {
        "valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "normalized_confidence": normalized_conf
    }

