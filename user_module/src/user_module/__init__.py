"""User module for account management, portfolios, and trade execution."""

from .contracts import (
    UserAccount,
    AccountBalance,
    Position,
    Trade,
    RiskProfile,
    PortfolioSummary,
    TradeExecutionRequest,
    TradeExecutionResult,
    UserStore,
    PortfolioStore,
    TradeStore,
    RiskManager,
    TradeExecutor,
    PnLAnalytics,
)
from .stores import MongoUserStore, MongoPortfolioStore, MongoTradeStore
from .services import (
    RiskProfileManager,
    PortfolioRiskManager,
    MockTradeExecutor,
    BasicPnLAnalytics,
)
from .api import (
    build_user_store,
    build_portfolio_store,
    build_trade_store,
    build_risk_profile_manager,
    build_portfolio_risk_manager,
    build_trade_executor,
    build_pnl_analytics,
    build_user_module,
    create_user_account,
    execute_user_trade,
)

__all__ = [
    # Contracts
    "UserAccount",
    "AccountBalance",
    "Position",
    "Trade",
    "RiskProfile",
    "PortfolioSummary",
    "TradeExecutionRequest",
    "TradeExecutionResult",
    "UserStore",
    "PortfolioStore",
    "TradeStore",
    "RiskManager",
    "TradeExecutor",
    "PnLAnalytics",

    # Implementations
    "MongoUserStore",
    "MongoPortfolioStore",
    "MongoTradeStore",
    "RiskProfileManager",
    "PortfolioRiskManager",
    "MockTradeExecutor",
    "BasicPnLAnalytics",

    # API
    "build_user_store",
    "build_portfolio_store",
    "build_trade_store",
    "build_risk_profile_manager",
    "build_portfolio_risk_manager",
    "build_trade_executor",
    "build_pnl_analytics",
    "build_user_module",
    "create_user_account",
    "execute_user_trade",
]

