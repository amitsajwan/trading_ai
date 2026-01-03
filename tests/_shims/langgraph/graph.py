"""Shim of langgraph.graph used in tests."""

class _FinalSignal:
    def __init__(self, value='HOLD'):
        self.value = value

class _RunResult:
    def __init__(self):
        self.final_signal = _FinalSignal()

class StateGraph:
    def __init__(self, state_type=None):
        self.state_type = state_type
        self.nodes = {}
        self.edges = []

    def add_node(self, name, fn):
        self.nodes[name] = fn

    def add_edge(self, src, dst):
        self.edges.append((src, dst))

    def compile(self):
        # Return a compiled graph object with invoke/ainvoke methods
        class CompiledGraph:
            def invoke(self, state):
                return _RunResult()
            async def ainvoke(self, state):
                return _RunResult()
        return CompiledGraph()

# Simple START and END placeholders
START = 'start'
END = 'end'
