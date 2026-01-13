"""Spread-Based Options Trading Strategies.

This module provides implementations for multi-leg options strategies:
- Iron Condor
- Credit Spreads (Bull/Bear)
- Debit Spreads (Bull/Bear)
- Spread Builder utilities
- Base strategy framework
"""

from .base_strategy import (
    OptionLeg,
    SpreadMetrics,
    BaseSpreadStrategy,
    OptionType,
    OrderAction
)

from .spread_builder import SpreadBuilder

from .iron_condor import IronCondorStrategy

from .credit_spreads import (
    BullCallSpreadStrategy as BullPutSpreadCreditStrategy,  # Credit: Sell higher put, buy lower put
    BearPutSpreadStrategy as BearCallSpreadCreditStrategy   # Credit: Sell lower call, buy higher call
)

from .debit_spreads import (
    BullCallSpreadStrategy,  # Debit: Buy lower call, sell higher call
    BearPutSpreadStrategy    # Debit: Buy higher put, sell lower put
)

__all__ = [
    # Base classes and dataclasses
    "OptionLeg",
    "SpreadMetrics",
    "BaseSpreadStrategy",
    "OptionType",
    "OrderAction",
    # Utilities
    "SpreadBuilder",
    # Strategies
    "IronCondorStrategy",
    # Debit Spreads
    "BullCallSpreadStrategy",
    "BearPutSpreadStrategy",
    # Credit Spreads
    "BullPutSpreadCreditStrategy",
    "BearCallSpreadCreditStrategy"
]
