"""UI Shell module for dashboard and CLI interactions."""

from .contracts import (
    DecisionDisplay,
    PortfolioSummary,
    MarketOverview,
    UserAction,
    BuyOverride,
    SellOverride,
    StopLossUpdate,
    RiskLimitUpdate,
    UIDataProvider,
    UIDispatcher,
    UINotificationHandler,
)
from .providers import EngineDataProvider, MockEngineInterface as MockEngineForData
from .dispatchers import EngineActionDispatcher, MockEngineInterface as MockEngineForActions
from .api import build_ui_data_provider, build_ui_dispatcher, build_ui_shell

__all__ = [
    # Contracts
    "DecisionDisplay",
    "PortfolioSummary",
    "MarketOverview",
    "UserAction",
    "BuyOverride",
    "SellOverride",
    "StopLossUpdate",
    "RiskLimitUpdate",
    "UIDataProvider",
    "UIDispatcher",
    "UINotificationHandler",

    # Implementations
    "EngineDataProvider",
    "EngineActionDispatcher",
    "MockEngineForData",
    "MockEngineForActions",

    # API Facade
    "build_ui_data_provider",
    "build_ui_dispatcher",
    "build_ui_shell",
]
