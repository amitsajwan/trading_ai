# Agent Position Awareness - Implementation Summary

## Overview
This document describes the changes made to make agents position-aware, ensuring they consider current user positions when making buy/sell decisions.

## Problem Statement
Previously, agents were making trading decisions without knowledge of:
- Current positions the user is holding
- Whether to add to existing positions or open new ones
- When to close existing positions
- Position limits and risk management

## Changes Made

### 1. Enhanced Orchestrator (`enhanced_orchestrator.py`)

#### Added Position Provider Protocol
- Added `PositionProvider` protocol interface for fetching current positions
- Position provider must implement `get_positions(symbol: Optional[str]) -> List[Dict[str, Any]]`

#### Updated Orchestrator Initialization
- Added optional `position_provider` parameter to `__init__`
- Orchestrator now fetches current positions before running agent analysis

#### Enhanced Context Passing
The orchestrator now passes position information to agents in the analysis context:
```python
analysis_context = {
    'ohlc': market_data,
    'symbol': symbol,
    'current_price': current_price,
    'timestamp': cycle_start,
    'current_positions': current_positions,  # NEW
    'has_long_position': bool,              # NEW
    'has_short_position': bool,             # NEW
    'position_count': int                   # NEW
}
```

#### Position-Aware Decision Logic
The `_aggregate_signals` method now:
- Checks current positions before making decisions
- Enforces position limits (max_positions config)
- Determines position actions:
  - `OPEN_NEW`: Open a new position
  - `ADD_TO_LONG`: Add to existing long position
  - `ADD_TO_SHORT`: Add to existing short position
  - `CLOSE_LONG`: Close existing long position
  - `CLOSE_SHORT`: Close existing short position

#### Position Management in Trading Decisions
- When at position limit, only considers exit signals
- When adding to positions, uses smaller position size (configurable via `add_to_position_pct`)
- When closing positions, uses quantity from existing position
- Includes position action in decision reasoning

### 2. Updated Agents

#### Momentum Agent (`momentum_agent.py`)
- Now checks `has_long_position` and `has_short_position` from context
- When strong momentum detected with existing position:
  - Signals to add to position (lower confidence)
  - Includes "Adding to existing position" in reasoning
- When momentum weakens with existing position:
  - Signals exit (moderate confidence)
  - Includes "Consider exiting position" in reasoning

#### Trend Agent (`trend_agent.py`)
- Position-aware trend following logic
- Adds to positions when trend strengthens
- Signals exit when trend reverses (price crosses slow MA)
- Different confidence levels for new vs. adding to positions

### 3. Enhanced Trading Decision
- Added `position_action` field to `TradingDecision` dataclass
- Position action indicates what to do with the decision:
  - `OPEN_NEW`: Standard new position
  - `ADD_TO_LONG`/`ADD_TO_SHORT`: Add to existing position
  - `CLOSE_LONG`/`CLOSE_SHORT`: Close existing position

### 4. Enhanced API (`enhanced_api.py`)
- Added `position_provider` parameter to `__init__`
- Passes position provider to orchestrator during initialization

## Configuration

New configuration options in orchestrator:
```python
{
    'max_positions': 3,              # Maximum open positions
    'add_to_position_pct': 0.5,      # Size when adding to position (50% of new)
    # ... other existing config
}
```

## Position Provider Interface

To use position awareness, provide a position provider that implements:

```python
class PositionProvider(Protocol):
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get current positions.
        
        Returns list of position dicts with:
        - symbol: str
        - action: str (BUY/SELL)
        - quantity: int
        - entry_price: float
        - current_price: float
        - stop_loss: float
        - take_profit: float
        - status: str (active/closed)
        - position_id: str
        """
```

## Usage Example

```python
from engine_module.enhanced_api import EnhancedTradingAPI
from engine_module.enhanced_orchestrator import PositionProvider

class MyPositionProvider:
    async def get_positions(self, symbol=None):
        # Fetch from your position store
        return active_positions

# Initialize with position provider
api = EnhancedTradingAPI(
    config=config,
    position_provider=MyPositionProvider()
)

await api.initialize()
result = await api.run_trading_cycle("NIFTY50")
```

## Benefits

1. **Position-Aware Decisions**: Agents now know what positions exist and can make informed decisions
2. **Position Management**: System can add to winning positions or exit losing ones
3. **Risk Control**: Enforces position limits and prevents over-trading
4. **Better Context**: Agents have full picture of portfolio state
5. **Flexible Actions**: Supports opening, adding to, and closing positions

## Next Steps

To fully utilize position awareness:
1. Implement a position provider that connects to your position store
2. Update other agents (mean_reversion, volume) to use position context
3. Add position modification logic (update stop-loss, take-profit)
4. Add position monitoring for exit conditions


