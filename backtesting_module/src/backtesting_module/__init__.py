"""Backtesting module for trading strategy validation.

Provides historical backtesting capabilities with realistic
market simulation, performance metrics, and risk analysis.
"""

from .backtest_engine import BacktestEngine, BacktestResult, BacktestTrade

__all__ = [
    'BacktestEngine',
    'BacktestResult',
    'BacktestTrade'
]

