"""Shim state_manager for tests."""

class StateManager:
    def __init__(self, market_memory=None):
        self.market_memory = market_memory

    def initialize_state(self):
        # Import AgentState lazily to avoid heavy top-level imports during tests
        from agents.state import AgentState
        return AgentState()
