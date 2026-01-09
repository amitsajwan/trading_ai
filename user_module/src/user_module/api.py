"""User module API facade with factory functions."""

from typing import Optional, Any
from datetime import datetime

from .contracts import (
    UserAccount, TradeExecutionRequest, TradeExecutionResult
)
from .stores import MongoUserStore, MongoPortfolioStore, MongoTradeStore
from .services import (
    RiskProfileManager, PortfolioRiskManager, MockTradeExecutor, BasicPnLAnalytics
)


def build_user_store(mongo_client) -> MongoUserStore:
    """Build user store for account management.

    Args:
        mongo_client: MongoDB client instance

    Returns:
        MongoUserStore instance for user account operations

    Example:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017")
        user_store = build_user_store(client)
    """
    return MongoUserStore(mongo_client)


def build_portfolio_store(mongo_client) -> MongoPortfolioStore:
    """Build portfolio store for position management.

    Args:
        mongo_client: MongoDB client instance

    Returns:
        MongoPortfolioStore instance for portfolio operations

    Example:
        portfolio_store = build_portfolio_store(client)
        positions = await portfolio_store.get_user_positions("user123")
    """
    return MongoPortfolioStore(mongo_client)


def build_trade_store(mongo_client) -> MongoTradeStore:
    """Build trade store for trade history.

    Args:
        mongo_client: MongoDB client instance

    Returns:
        MongoTradeStore instance for trade operations

    Example:
        trade_store = build_trade_store(client)
        trades = await trade_store.get_user_trades("user123", limit=50)
    """
    return MongoTradeStore(mongo_client)


def build_risk_profile_manager(user_store: MongoUserStore) -> RiskProfileManager:
    """Build risk profile manager.

    Args:
        user_store: User store instance

    Returns:
        RiskProfileManager instance for risk calculations

    Example:
        risk_manager = build_risk_profile_manager(user_store)
        position_size = await risk_manager.calculate_position_size(
            "user123", "BANKNIFTY", Decimal("45000"), Decimal("44500"), Decimal("100000")
        )
    """
    return RiskProfileManager(user_store)


def build_portfolio_risk_manager(user_store: MongoUserStore,
                               portfolio_store: MongoPortfolioStore,
                               risk_profile_manager: RiskProfileManager) -> PortfolioRiskManager:
    """Build portfolio risk manager.

    Args:
        user_store: User store instance
        portfolio_store: Portfolio store instance
        risk_profile_manager: Risk profile manager instance

    Returns:
        PortfolioRiskManager instance for risk validation

    Example:
        risk_mgr = build_portfolio_risk_manager(user_store, portfolio_store, risk_profile_mgr)
        validation = await risk_mgr.validate_trade_risk("user123", trade_request)
        if validation["approved"]:
            # Execute trade
            pass
    """
    return PortfolioRiskManager(user_store, portfolio_store, risk_profile_manager)


def build_trade_executor() -> MockTradeExecutor:
    """Build trade executor (currently mock implementation).

    Returns:
        MockTradeExecutor instance for trade execution

    Note:
        This is currently a mock implementation for testing.
        Production would integrate with Kite Connect or other brokers.

    Example:
        executor = build_trade_executor()
        result = await executor.execute_trade(trade_request)
        if result.success:
            print(f"Trade executed at {result.executed_price}")
    """
    return MockTradeExecutor()


def build_pnl_analytics(trade_store: MongoTradeStore,
                       portfolio_store: MongoPortfolioStore) -> BasicPnLAnalytics:
    """Build P&L analytics service.

    Args:
        trade_store: Trade store instance
        portfolio_store: Portfolio store instance

    Returns:
        BasicPnLAnalytics instance for performance calculations

    Example:
        analytics = build_pnl_analytics(trade_store, portfolio_store)
        realized_pnl = await analytics.calculate_realized_pnl("user123", start_date, end_date)
        stats = await analytics.get_trade_statistics("user123")
    """
    return BasicPnLAnalytics(trade_store, portfolio_store)


def build_user_module(mongo_client) -> dict:
    """Build complete user module with all components.

    Args:
        mongo_client: MongoDB client instance

    Returns:
        Dict containing all user module components:
        {
            "user_store": MongoUserStore,
            "portfolio_store": MongoPortfolioStore,
            "trade_store": MongoTradeStore,
            "risk_profile_manager": RiskProfileManager,
            "portfolio_risk_manager": PortfolioRiskManager,
            "trade_executor": MockTradeExecutor,
            "pnl_analytics": BasicPnLAnalytics
        }

    Example:
        components = build_user_module(client)
        user_store = components["user_store"]
        risk_manager = components["portfolio_risk_manager"]
    """
    # Build stores
    user_store = build_user_store(mongo_client)
    portfolio_store = build_portfolio_store(mongo_client)
    trade_store = build_trade_store(mongo_client)

    # Build services
    risk_profile_manager = build_risk_profile_manager(user_store)
    portfolio_risk_manager = build_portfolio_risk_manager(
        user_store, portfolio_store, risk_profile_manager
    )
    trade_executor = build_trade_executor()
    pnl_analytics = build_pnl_analytics(trade_store, portfolio_store)

    return {
        "user_store": user_store,
        "portfolio_store": portfolio_store,
        "trade_store": trade_store,
        "risk_profile_manager": risk_profile_manager,
        "portfolio_risk_manager": portfolio_risk_manager,
        "trade_executor": trade_executor,
        "pnl_analytics": pnl_analytics
    }


# Convenience functions for common operations

async def create_user_account(mongo_client, email: str, full_name: str,
                            risk_profile: str = "moderate") -> Optional[str]:
    """Create a new user account and return user ID.

    Args:
        mongo_client: MongoDB client
        email: User email
        full_name: User full name
        risk_profile: Risk profile ("conservative", "moderate", "aggressive")

    Returns:
        User ID if created successfully, None otherwise
    """
    try:
        user_store = build_user_store(mongo_client)
        user_id = f"user_{email.replace('@', '_').replace('.', '_')}"

        user = UserAccount(
            user_id=user_id,
            email=email,
            full_name=full_name,
            created_at=datetime.utcnow(),
            risk_profile=risk_profile
        )

        success = await user_store.create_user(user)
        return user_id if success else None

    except Exception as e:
        print(f"Failed to create user account: {e}")
        return None


async def execute_user_trade(mongo_client, user_id: str,
                           instrument: str, side: str, quantity: int,
                           order_type: str = "MARKET", price: Optional[float] = None,
                           stop_loss: Optional[float] = None,
                           take_profit: Optional[float] = None,
                           # Options-specific fields
                           strike_price: Optional[float] = None,
                           expiry_date: Optional[datetime] = None,
                           option_type: Optional[str] = None,
                           # Optional originating signal id
                           signal_id: Optional[str] = None) -> TradeExecutionResult:
    """Execute a trade for a user with risk management.
    
    Supports Spot, Futures, and Options trading.

    Args:
        mongo_client: MongoDB client
        user_id: User ID
        instrument: Trading instrument (e.g., "BANKNIFTY")
        side: "BUY" or "SELL"
        quantity: Number of shares/contracts/lots
        order_type: "MARKET" or "LIMIT"
        price: Price for LIMIT orders
        stop_loss: Stop loss price
        take_profit: Take profit price
        strike_price: Strike price for Options (required for Options)
        expiry_date: Expiry date for Options/Futures (required for Options)
        option_type: "CE" or "PE" for Options (required for Options)

    Returns:
        TradeExecutionResult with execution details
    """
    try:
        # Build components
        components = build_user_module(mongo_client)
        risk_manager = components["portfolio_risk_manager"]
        trade_executor = components["trade_executor"]

        # Create trade request with Options support
        trade_request = TradeExecutionRequest(
            user_id=user_id,
            instrument=instrument,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=Decimal(str(price)) if price else None,
            stop_loss_price=Decimal(str(stop_loss)) if stop_loss else None,
            take_profit_price=Decimal(str(take_profit)) if take_profit else None,
            # Options fields
            strike_price=Decimal(str(strike_price)) if strike_price else None,
            expiry_date=expiry_date,
            option_type=option_type
        )

        # Validate risk
        risk_validation = await risk_manager.validate_trade_risk(user_id, trade_request)
        if not risk_validation["approved"]:
            return TradeExecutionResult(
                success=False,
                message=f"Risk validation failed: {', '.join(risk_validation['reasons'])}",
                error_code="RISK_VALIDATION_FAILED"
            )

        # Execute trade
        result = await trade_executor.execute_trade(trade_request)

        # Record trade if successful
        if result.success:
            trade_record = Trade(
                user_id=user_id,
                trade_id=result.trade_id or f"trade_{user_id}_{datetime.utcnow().timestamp()}",
                order_id=result.order_id or f"order_{user_id}_{datetime.utcnow().timestamp()}",
                instrument=instrument,
                side=side,
                quantity=quantity,
                price=result.executed_price or Decimal("0"),
                order_type=order_type,
                timestamp=datetime.utcnow(),
                status="EXECUTED",
                broker_fees=Decimal("0"),  # Would calculate based on broker
                exchange_fees=Decimal("0"),  # Would calculate based on exchange
                signal_id=signal_id
            )

            trade_store = components["trade_store"]
            await trade_store.record_trade(trade_record)

        return result

    except Exception as e:
        print(f"Failed to execute trade: {e}")
        return TradeExecutionResult(
            success=False,
            message=f"Trade execution failed: {str(e)}",
            error_code="EXECUTION_ERROR"
        )


__all__ = [
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

