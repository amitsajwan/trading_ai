"""Graph module proxy; real shim moved to tests/_shims/langgraph.graph"""

import importlib

try:
    _mod = importlib.import_module('tests._shims.langgraph.graph')
    StateGraph = _mod.StateGraph
    START = getattr(_mod, 'START', 'start')
    END = getattr(_mod, 'END', 'end')
except Exception:
    # Fall back: define lightweight defaults
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
            class CompiledGraph:
                def invoke(self, state):
                    return _RunResult()
                async def ainvoke(self, state):
                    return _RunResult()
            return CompiledGraph()

    START = 'start'
    END = 'end'

