"""Public API factory for engine_module.

This is the stable import surface for the main application.
"""
from typing import Any, Optional

from .contracts import Orchestrator
from .orchestrator_stub import TradingOrchestrator
from .redis_providers import (
    build_redis_market_data_provider,
    build_redis_technical_data_provider,
    build_redis_options_data_provider,
    build_redis_news_data_provider,
    build_redis_fundamental_data_provider,
    build_redis_macro_data_provider
)


def build_orchestrator(
    llm_client,
    market_store=None,  # Made optional since we use Redis directly
    options_data=None,  # Made optional since we use Redis directly
    news_service=None,
    technical_data_provider=None,
    macro_data_provider=None,  # MacroData provider for economic indicators
    redis_client=None,  # New parameter for direct Redis access
    signal_monitor=None,  # SignalMonitor instance for conditional signals
    mongo_db=None,  # MongoDB database instance for signal persistence
    agents=None,  # List of analysis agents
    context=None,  # TradingContext with mode, run_id, instrument
) -> Orchestrator:
    """Build TradingOrchestrator with injected dependencies.

    Args:
        llm_client: LLMClient instance (from genai_module.api)
        market_store: MarketStore instance (from market_data.api) - optional if redis_client provided
        options_data: OptionsData instance (from market_data.api) - optional if redis_client provided
        news_service: NewsService instance (from news_module.api) - optional
        technical_data_provider: TechnicalDataProvider instance - optional if redis_client provided
        macro_data_provider: MacroData provider for economic indicators - optional
        redis_client: Redis client for direct data access (preferred for performance)
        signal_monitor: SignalMonitor instance for conditional signals
        mongo_db: MongoDB database instance for signal persistence
        agents: List of analysis agents
        context: TradingContext with mode, run_id, and instrument information

    Returns:
        Orchestrator instance

    Example:
        import redis
        from genai_module.api import build_llm_client
        from news_module.api import build_news_service
        from engine_module.api import build_orchestrator
        from engine_module.enhanced_orchestrator import TradingContext

        # Build dependencies
        llm = build_llm_client(legacy_manager)
        news = build_news_service(mongo_collection)
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)

        # Build orchestrator with direct Redis access
        context = TradingContext(instrument="BANKNIFTY", mode="BACKTEST", run_id="bt_2026-01-07")
        orchestrator = build_orchestrator(
            llm_client=llm,
            news_service=news,
            redis_client=r,
            context=context
        )

        # Run trading cycle
        result = await orchestrator.run_cycle({"market_hours": True})
        print(result.decision, result.confidence)
    """
    # If redis_client is provided, use Redis-based providers for better performance
    if redis_client is not None:
        market_data_provider = build_redis_market_data_provider(redis_client)
        technical_provider = build_redis_technical_data_provider(redis_client)
        options_provider = build_redis_options_data_provider(redis_client)
        news_provider = build_redis_news_data_provider(redis_client)
        fundamental_provider = build_redis_fundamental_data_provider(redis_client)
        macro_provider = build_redis_macro_data_provider(redis_client)
    else:
        # Fallback to API-based providers (legacy)
        market_data_provider = market_store
        technical_provider = technical_data_provider
        options_provider = options_data
        news_provider = None
        fundamental_provider = None
        macro_provider = macro_data_provider

    # Import execution adapters and enhanced orchestrator for mode-aware execution
    from .execution_adapters import create_execution_adapter
    from .enhanced_orchestrator import EnhancedTradingOrchestrator, TradingContext

    # Use provided context or create default
    if context is None:
        context = TradingContext(
            instrument="BANKNIFTY",
            mode="LIVE",
            run_id=None
        )

    # Extract values from context for backward compatibility
    mode = context.mode
    run_id = context.run_id
    instrument = context.instrument

    # Create mode-aware execution adapter
    #
    # NOTE:
    # - create_execution_adapter signature is (mode, run_id, redis_client, mongo_client)
    # - api_service passes mongo_db as a *Database* (mongo_client[db_name]), so for adapters
    #   we pass mongo_db.client as mongo_client where available.
    mongo_client = None
    try:
        mongo_client = mongo_db.client if mongo_db is not None and hasattr(mongo_db, "client") else mongo_db
    except Exception:
        mongo_client = mongo_db

    execution_adapter = create_execution_adapter(mode, run_id, redis_client, mongo_client)

    # Use EnhancedTradingOrchestrator for all modes (has judge + structured signals + invalidation)
    # All modes now follow the same judge-driven, signal-based execution pattern
    return EnhancedTradingOrchestrator(
        agents=agents,
        context=context,
        llm_client=llm_client,
        market_data_provider=market_data_provider,
        options_data_provider=options_provider,
        news_data_provider=news_provider,
        technical_data_provider=technical_provider,
        fundamental_data_provider=fundamental_provider,
        macro_data_provider=macro_provider,
        signal_monitor=signal_monitor,
        mongo_db=mongo_db,
        execution_adapter=execution_adapter,
        redis_client=redis_client
    )

