"""UI Shell API facade with factory functions."""

from typing import Optional, Any

from .providers import EngineDataProvider, MockEngineInterface as MockEngineForData
from .dispatchers import EngineActionDispatcher, MockEngineInterface as MockEngineForActions


def build_ui_data_provider(engine_interface=None) -> EngineDataProvider:
    """Build UI data provider for dashboard data access.

    Args:
        engine_interface: Interface to engine module for real data.
                         Uses mock interface if None.

    Returns:
        EngineDataProvider instance for UI data access

    Example:
        # With real engine
        from engine_module.api import build_orchestrator
        orchestrator = build_orchestrator(...)
        provider = build_ui_data_provider(orchestrator)

        # With mock data (default)
        provider = build_ui_data_provider()
    """
    return EngineDataProvider(engine_interface)


def build_ui_dispatcher(engine_interface=None) -> EngineActionDispatcher:
    """Build UI dispatcher for handling user actions.

    Args:
        engine_interface: Interface to engine module for action processing.
                         Uses mock interface if None.

    Returns:
        EngineActionDispatcher instance for UI action handling

    Example:
        # With real engine
        from engine_module.api import build_orchestrator
        orchestrator = build_orchestrator(...)
        dispatcher = build_ui_dispatcher(orchestrator)

        # With mock processing (default)
        dispatcher = build_ui_dispatcher()

        # Process user action
        from ui_shell.contracts import BuyOverride
        action = BuyOverride("NIFTY", 10, 22000.0)
        result = await dispatcher.submit_override(action)
    """
    return EngineActionDispatcher(engine_interface)


def build_ui_shell(engine_interface=None) -> tuple[EngineDataProvider, EngineActionDispatcher]:
    """Build complete UI shell with both data provider and dispatcher.

    Args:
        engine_interface: Interface to engine module. Uses mock if None.

    Returns:
        Tuple of (data_provider, dispatcher) for complete UI shell

    Example:
        # Build complete UI shell
        provider, dispatcher = build_ui_shell()

        # Get dashboard data
        decision = await provider.get_latest_decision()
        portfolio = await provider.get_portfolio_summary()

        # Handle user actions
        from ui_shell.contracts import BuyOverride
        action = BuyOverride("NIFTY", 10)
        result = await dispatcher.submit_override(action)
    """
    return (
        build_ui_data_provider(engine_interface),
        build_ui_dispatcher(engine_interface)
    )


__all__ = [
    "build_ui_data_provider",
    "build_ui_dispatcher",
    "build_ui_shell",
]
