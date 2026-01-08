import pytest
from providers.factory import get_provider
from schemas import Quote


def test_zerodha_provider_returns_quote_instance():
    p = get_provider('zerodha')
    if p is None:
        pytest.skip("No Zerodha credentials available")
    symbols = ['NSE:NIFTY BANK']
    quotes = p.quote(symbols)
    q = quotes[symbols[0]]
    assert isinstance(q, Quote)
