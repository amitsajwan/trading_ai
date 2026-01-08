"""Public API factory for engine_module.

This is the stable import surface for the main application.
"""
from typing import Any, Optional

from .contracts import Orchestrator
from .orchestrator_stub import TradingOrchestrator
from .redis_providers import (
    build_redis_market_data_provider,
    build_redis_technical_data_provider,
    build_redis_options_data_provider
)


def build_orchestrator(
    llm_client,
    market_store=None,  # Made optional since we use Redis directly
    options_data=None,  # Made optional since we use Redis directly
    news_service=None,
    technical_data_provider=None,
    redis_client=None,  # New parameter for direct Redis access
    **kwargs: Any
) -> Orchestrator:
    """Build TradingOrchestrator with injected dependencies.

    Args:
        llm_client: LLMClient instance (from genai_module.api)
        market_store: MarketStore instance (from market_data.api) - optional if redis_client provided
        options_data: OptionsData instance (from market_data.api) - optional if redis_client provided
        news_service: NewsService instance (from news_module.api) - optional
        technical_data_provider: TechnicalDataProvider instance - optional if redis_client provided
        redis_client: Redis client for direct data access (preferred for performance)
        **kwargs: Additional config (e.g., instrument, timeframe)

    Returns:
        Orchestrator instance

    Example:
        import redis
        from genai_module.api import build_llm_client
        from news_module.api import build_news_service
        from engine_module.api import build_orchestrator

        # Build dependencies
        llm = build_llm_client(legacy_manager)
        news = build_news_service(mongo_collection)
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)

        # Build orchestrator with direct Redis access
        orchestrator = build_orchestrator(
            llm_client=llm,
            news_service=news,
            redis_client=r,
            instrument="BANKNIFTY"
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
    else:
        # Fallback to API-based providers (legacy)
        market_data_provider = market_store
        technical_provider = technical_data_provider
        options_provider = options_data

    return TradingOrchestrator(
        llm_client=llm_client,
        market_data_provider=market_data_provider,
        options_data_provider=options_provider,
        news_service=news_service,
        technical_data_provider=technical_provider,
        **kwargs
    )

