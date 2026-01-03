"""Main trading graph shim used for tests."""

# Expose simple stubs so tests can patch these names on the module
class MarketMemory:
    pass

class KiteConnect:
    pass

# Lightweight trading graph stub
class TradingGraph:
    def __init__(self, kite=None, market_memory=None):
        self.kite = kite
        self.market_memory = market_memory
        self.graph = None

    def run(self):
        return None

    async def arun(self):
        class R: pass
        return R()
