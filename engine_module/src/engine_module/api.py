"""Public API factory for engine_module.

This is the stable import surface for the main application.
"""
from typing import Any

from .contracts import Orchestrator
from .orchestrator_stub import TradingOrchestrator


def build_orchestrator(
    llm_client,
    market_store,
    options_data,
    **kwargs: Any
) -> Orchestrator:
    """Build TradingOrchestrator with injected dependencies.
    
    Args:
        llm_client: LLMClient instance (from genai_module.api)
        market_store: MarketStore instance (from data_niftybank.api)
        options_data: OptionsData instance (from data_niftybank.api)
        **kwargs: Additional config (e.g., instrument, timeframe)
    
    Returns:
        Orchestrator instance
    
    Example:
        from genai_module.api import build_llm_client
        from data_niftybank.api import build_store, build_options_client
        from engine_module.api import build_orchestrator
        
        # Build dependencies
        llm = build_llm_client(legacy_manager)
        store = build_store(redis_client)
        options = build_options_client(kite, fetcher)
        
        # Build orchestrator
        orchestrator = build_orchestrator(
            llm_client=llm,
            market_store=store,
            options_data=options,
            instrument="BANKNIFTY"
        )
        
        # Run trading cycle
        result = await orchestrator.run_cycle({"market_hours": True})
        print(result.decision, result.confidence)
    """
    return TradingOrchestrator(
        llm_client=llm_client,
        market_store=market_store,
        options_data=options_data,
        **kwargs
    )
