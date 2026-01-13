# Spread-Based Options Trading Strategies

This module implements multi-leg options strategies for spread-based trading, moving from naked positions to risk-controlled spreads.

## Overview

The strategies module provides:
- **Base Framework**: Common interfaces and validation for all spread strategies
- **Spread Builder**: Utilities for calculating spread metrics (P&L, Greeks, R:R, PoP)
- **Iron Condor**: 4-leg neutral strategy for ranging markets
- **Credit Spreads**: Premium-receiving strategies (Bull Put, Bear Call)
- **Debit Spreads**: Premium-paying strategies (Bull Call, Bear Put)

## Quick Start

```python
from engine_module.strategies import (
    IronCondorStrategy,
    BullCallSpreadStrategy,
    BearPutSpreadStrategy
)
from market_data import GreeksCalculator

# Initialize strategy
config = {
    'lot_size': 25,  # Bank Nifty
    'min_option_volume': 100,
    'min_option_oi': 500,
    'min_risk_reward': 0.3,
    'min_probability_of_profit': 0.50
}

# Iron Condor for ranging markets
iron_condor = IronCondorStrategy(config)
legs = iron_condor.build_spread(
    spot_price=45000,
    option_chain=chain_data,
    expiry="2026-01-30"
)

if legs:
    metrics = iron_condor.calculate_metrics(legs)
    if iron_condor.validate_spread(legs, metrics):
        print(f"Max Profit: {metrics.max_profit}")
        print(f"Max Loss: {metrics.max_loss}")
        print(f"R:R Ratio: {metrics.risk_reward_ratio}")
        print(f"PoP: {metrics.probability_of_profit}")
```

## Strategies

### Iron Condor

**Best For:** Ranging markets with low volatility  
**Structure:** Sell OTM put spread + Sell OTM call spread  
**Profit:** Net credit received  
**Risk:** Limited to spread width - credit

```python
strategy = IronCondorStrategy({
    'otm_percentage': 0.02,  # 2% OTM for short strikes
    'spread_width': 0.01     # 1% width for spreads
})
```

### Credit Spreads

#### Bull Put Spread
**Best For:** Bullish or neutral-bullish markets  
**Structure:** Sell higher strike put, buy lower strike put  
**Profit:** Net credit received

#### Bear Call Spread
**Best For:** Bearish or neutral-bearish markets  
**Structure:** Sell lower strike call, buy higher strike call  
**Profit:** Net credit received

```python
# Bull Put Spread
bull_put = BullPutSpreadCreditStrategy(config)
legs = bull_put.build_spread(spot_price, option_chain, expiry)
```

### Debit Spreads

#### Bull Call Spread
**Best For:** Bullish markets  
**Structure:** Buy lower strike call, sell higher strike call  
**Profit:** Spread width - net debit

#### Bear Put Spread
**Best For:** Bearish markets  
**Structure:** Buy higher strike put, sell lower strike put  
**Profit:** Spread width - net debit

```python
# Bull Call Spread
bull_call = BullCallSpreadStrategy(config)
legs = bull_call.build_spread(spot_price, option_chain, expiry)
```

## Spread Metrics

All strategies calculate comprehensive metrics:

- **Max Profit/Loss**: Maximum profit and loss potential
- **Breakeven Points**: Price levels where strategy breaks even
- **Net Greeks**: Aggregated delta, gamma, theta, vega, rho
- **Risk/Reward Ratio**: Profit potential vs. risk
- **Probability of Profit**: Estimated PoP (0.0 to 1.0)
- **Margin Required**: Estimated margin requirement

## Validation

All strategies validate:
- **Liquidity**: Minimum volume and open interest requirements
- **Risk/Reward**: Minimum R:R ratio (default: 0.3)
- **Probability of Profit**: Minimum PoP (default: 0.50)
- **Delta Neutrality**: Maximum net delta for neutral strategies (default: 0.2)

## Integration

Strategies integrate with:
- **Market Data Module**: Options chain data with Greeks
- **Risk Module**: Portfolio heat and position sizing
- **Regime Detector**: Strategy selection based on market regime
- **Multi-Timeframe Analyzer**: Confluence signals

## Testing

All strategies have comprehensive unit tests:

```bash
# Run all strategy tests
pytest engine_module/tests/unit/strategies/ -v

# Run specific strategy tests
pytest engine_module/tests/unit/strategies/test_iron_condor.py -v
```

**Test Coverage:** 42 tests, all passing ✅

## Configuration

Default configuration:

```python
config = {
    'lot_size': 25,                    # Lot size (Bank Nifty default)
    'min_option_volume': 100,          # Minimum volume requirement
    'min_option_oi': 500,              # Minimum open interest
    'min_risk_reward': 0.3,            # Minimum R:R ratio
    'min_probability_of_profit': 0.50, # Minimum PoP
    'max_net_delta': 0.2,              # Max net delta for neutrality
    'otm_percentage': 0.02,            # OTM percentage for short strikes
    'spread_width': 0.01               # Spread width as percentage
}
```

## Examples

See test files for detailed examples:
- `engine_module/tests/unit/strategies/test_iron_condor.py`
- `engine_module/tests/unit/strategies/test_credit_spreads.py`
- `engine_module/tests/unit/strategies/test_debit_spreads.py`
