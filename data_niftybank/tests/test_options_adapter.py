import pytest

from data_niftybank.adapters.zerodha_options_chain import ZerodhaOptionsChainAdapter


class FakeFetcher:
    def __init__(self):
        self.initialized = False
        self.last_strikes = None
        self.instrument_symbol = None

    async def initialize(self):
        self.initialized = True

    async def fetch_options_chain(self, strikes=None):
        self.last_strikes = strikes
        return {"available": True, "instrument": self.instrument_symbol, "strikes": strikes or []}


@pytest.mark.asyncio
async def test_adapter_normalizes_instrument_and_initializes():
    fetcher = FakeFetcher()
    adapter = ZerodhaOptionsChainAdapter(fetcher, instrument_symbol="Nifty Bank")

    await adapter.initialize()
    result = await adapter.fetch_options_chain(strikes=[45000, 45100])

    assert fetcher.initialized is True
    assert fetcher.last_strikes == [45000, 45100]
    # Adapter normalizes to BANKNIFTY
    assert fetcher.instrument_symbol == "BANKNIFTY"
    assert result["instrument"] == "BANKNIFTY"
