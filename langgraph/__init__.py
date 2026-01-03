"""Proxy package: langgraph shim moved to tests/_shims/langgraph.

The real lightweight test shims live in `tests/_shims/langgraph` and are imported
here so top-level imports continue to work during normal runs and tests.
"""

import importlib

try:
    trading_graph = importlib.import_module('tests._shims.langgraph.trading_graph')
    graph = importlib.import_module('tests._shims.langgraph.graph')
    state_manager = importlib.import_module('tests._shims.langgraph.state_manager')
except Exception:
    # Fall back to local modules if the shims are not available on the path
    # (keeps behavior stable if users prefer the old location)
    from . import trading_graph, graph, state_manager

__all__ = ['trading_graph', 'graph', 'state_manager']

