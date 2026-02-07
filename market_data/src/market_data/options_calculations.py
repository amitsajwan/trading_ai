"""Options calculations including implied volatility, Greeks, and pricing models.

This module provides mathematical calculations for options analysis including:
- Implied volatility calculation using Newton-Raphson method
- Black-Scholes option pricing
- Options Greeks (Delta, Gamma, Theta, Vega, Rho)
"""

import math
from typing import Optional, Tuple
from datetime import datetime, date

try:
    from scipy.stats import norm
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("WARNING: scipy not available - options calculations will be disabled")

import numpy as np


def black_scholes_price(S: float, K: float, T: float, r: float, sigma: float,
                        option_type: str = 'call') -> float:
    """Calculate Black-Scholes option price.

    Args:
        S: Underlying price
        K: Strike price
        T: Time to expiration (years)
        r: Risk-free rate
        sigma: Volatility
        option_type: 'call' or 'put'

    Returns:
        Option price
    """
    if not SCIPY_AVAILABLE:
        # Fallback to intrinsic value when scipy not available
        if T <= 0:
            # Option expired
            if option_type.lower() == 'call':
                return max(S - K, 0)
            else:
                return max(K - S, 0)
        else:
            # Simple approximation for non-expired options
            if option_type.lower() == 'call':
                return max(S - K, 0) * 0.1  # Rough approximation
            else:
                return max(K - S, 0) * 0.1

    if T <= 0:
        # Option expired
        if option_type.lower() == 'call':
            return max(S - K, 0)
        else:
            return max(K - S, 0)

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type.lower() == 'call':
        price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:  # put
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    return price


def calculate_implied_volatility(market_price: float, S: float, K: float, T: float,
                                r: float = 0.06, option_type: str = 'call',
                                max_iterations: int = 100, tolerance: float = 1e-5) -> Optional[float]:
    """Calculate implied volatility using Newton-Raphson method.

    Args:
        market_price: Observed market price of the option
        S: Underlying price
        K: Strike price
        T: Time to expiration (years)
        r: Risk-free rate (default 6%)
        option_type: 'call' or 'put'
        max_iterations: Maximum iterations for convergence
        tolerance: Convergence tolerance

    Returns:
        Implied volatility or None if calculation fails
    """
    if T <= 0 or market_price <= 0 or S <= 0 or K <= 0:
        return None

    # Initial guess for volatility (20% is reasonable starting point)
    sigma = 0.20

    for _ in range(max_iterations):
        try:
            # Calculate option price with current sigma
            price = black_scholes_price(S, K, T, r, sigma, option_type)

            # Calculate vega (derivative of price w.r.t. volatility)
            d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            vega = S * norm.pdf(d1) * math.sqrt(T)

            if abs(vega) < 1e-8:  # Avoid division by zero
                break

            # Newton-Raphson update
            price_diff = price - market_price
            sigma_new = sigma - price_diff / vega

            # Check convergence
            if abs(sigma_new - sigma) < tolerance:
                return max(0, sigma_new)  # Ensure non-negative

            sigma = sigma_new

            # Prevent unrealistic values
            if sigma < 0.001 or sigma > 5.0:  # 0.1% to 500%
                break

        except (ValueError, ZeroDivisionError, OverflowError):
            break

    return None


def calculate_option_greeks(S: float, K: float, T: float, r: float, sigma: float,
                           option_type: str = 'call') -> dict:
    """Calculate option Greeks using Black-Scholes model.

    Args:
        S: Underlying price
        K: Strike price
        T: Time to expiration (years)
        r: Risk-free rate
        sigma: Volatility
        option_type: 'call' or 'put'

    Returns:
        Dictionary with Greeks: delta, gamma, theta, vega, rho
    """
    if not SCIPY_AVAILABLE or T <= 0 or sigma <= 0:
        return {
            'delta': None,
            'gamma': None,
            'theta': None,
            'vega': None,
            'rho': None
        }

    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        # Delta
        if option_type.lower() == 'call':
            delta = norm.cdf(d1)
        else:
            delta = -norm.cdf(-d1)

        # Gamma (same for calls and puts)
        gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))

        # Theta
        if option_type.lower() == 'call':
            theta = (-S * norm.pdf(d1) * sigma / (2 * math.sqrt(T))
                    - r * K * math.exp(-r * T) * norm.cdf(d2))
        else:
            theta = (-S * norm.pdf(d1) * sigma / (2 * math.sqrt(T))
                    + r * K * math.exp(-r * T) * norm.cdf(-d2))

        # Vega (same for calls and puts)
        vega = S * norm.pdf(d1) * math.sqrt(T) / 100  # Usually quoted per 1% change

        # Rho
        if option_type.lower() == 'call':
            rho = K * T * math.exp(-r * T) * norm.cdf(d2) / 100  # Per 1% change in r
        else:
            rho = -K * T * math.exp(-r * T) * norm.cdf(-d2) / 100

        return {
            'delta': round(delta, 4),
            'gamma': round(gamma, 6),
            'theta': round(theta, 4),
            'vega': round(vega, 4),
            'rho': round(rho, 4)
        }

    except (ValueError, ZeroDivisionError, OverflowError):
        return {
            'delta': None,
            'gamma': None,
            'theta': None,
            'vega': None,
            'rho': None
        }


def time_to_expiry(expiry_date: str, current_date: Optional[str] = None) -> float:
    """Calculate time to expiry in years.

    Args:
        expiry_date: Expiry date in 'YYYY-MM-DD' format
        current_date: Current date (defaults to today)

    Returns:
        Time to expiry in years
    """
    try:
        if current_date:
            current = date.fromisoformat(current_date)
        else:
            current = date.today()

        expiry = date.fromisoformat(expiry_date)
        days_diff = (expiry - current).days

        # Trading days approximation (252 trading days per year)
        trading_days = max(0, days_diff * 252 / 365)
        return trading_days / 252  # Convert to years

    except (ValueError, TypeError):
        return 0.0


def estimate_risk_free_rate() -> float:
    """Estimate risk-free rate based on current market conditions.

    For now, returns a reasonable default. In production, this should
    come from treasury yields or similar instruments.

    Returns:
        Risk-free rate (annual)
    """
    # Default to 6% for Indian markets (can be made dynamic)
    return 0.06


def calculate_option_metrics(market_price: float, S: float, K: float, T: float,
                           option_type: str = 'call', r: Optional[float] = None,
                           mode: str = 'LIVE', data_timestamp: Optional[str] = None) -> dict:
    """Calculate comprehensive option metrics including IV and Greeks with mode awareness.

    Args:
        market_price: Observed market price
        S: Underlying price
        K: Strike price
        T: Time to expiration (years)
        option_type: 'call' or 'put'
        r: Risk-free rate (optional, defaults to estimated)
        mode: Execution mode ('LIVE', 'HISTORICAL', 'BACKTEST')
        data_timestamp: Timestamp of the data (for historical context)

    Returns:
        Dictionary with IV, Greeks, and other metrics
    """
    if r is None:
        r = estimate_risk_free_rate()

    # For very old historical data, IV calculations may not be reliable
    is_historical_data = mode == 'HISTORICAL'
    if is_historical_data and data_timestamp:
        try:
            from datetime import datetime, timedelta
            data_age_days = (datetime.now() - datetime.fromisoformat(data_timestamp.replace('Z', '+00:00'))).days
            # For data older than 30 days, IV calculations become less reliable
            if data_age_days > 30:
                return {
                    'implied_volatility': None,
                    'delta': None,
                    'gamma': None,
                    'theta': None,
                    'vega': None,
                    'rho': None,
                    'theoretical_price': None,
                    'intrinsic_value': None,
                    'extrinsic_value': None,
                    'calculation_note': f'Historical data ({data_age_days} days old) - IV calculation unreliable'
                }
        except (ValueError, AttributeError):
            pass  # Continue with calculation if timestamp parsing fails

    # Calculate implied volatility
    iv = calculate_implied_volatility(market_price, S, K, T, r, option_type)

    if iv is None:
        note = 'IV calculation failed - option may be deep ITM/OTM or data issues'
        if is_historical_data:
            note += f' ({mode} mode)'
        return {
            'implied_volatility': None,
            'delta': None,
            'gamma': None,
            'theta': None,
            'vega': None,
            'rho': None,
            'theoretical_price': None,
            'intrinsic_value': None,
            'extrinsic_value': None,
            'calculation_note': note
        }

    # For historical data, add a note about potential inaccuracies
    calculation_note = None
    if is_historical_data:
        calculation_note = f'Calculated using historical data ({mode} mode) - current market conditions may differ'

    # Calculate Greeks
    greeks = calculate_option_greeks(S, K, T, r, iv, option_type)

    # Calculate theoretical price
    theoretical_price = black_scholes_price(S, K, T, r, iv, option_type)

    # Calculate intrinsic and extrinsic value
    if option_type.lower() == 'call':
        intrinsic_value = max(S - K, 0)
    else:
        intrinsic_value = max(K - S, 0)

    extrinsic_value = max(market_price - intrinsic_value, 0)

    result = {
        'implied_volatility': round(iv * 100, 2),  # Convert to percentage
        'delta': greeks['delta'],
        'gamma': greeks['gamma'],
        'theta': greeks['theta'],
        'vega': greeks['vega'],
        'rho': greeks['rho'],
        'theoretical_price': round(theoretical_price, 2),
        'intrinsic_value': round(intrinsic_value, 2),
        'extrinsic_value': round(extrinsic_value, 2)
    }

    if calculation_note:
        result['calculation_note'] = calculation_note

    return result