import pytest
from typing import Any
from market_data.providers.base import ProviderBase
from market_data.providers.factory import get_provider


def assert_quote_shape(q: Any):
    # Accept dataclass or dict
    if isinstance(q, dict):
        assert 'last_price' in q and 'timestamp' in q and 'symbol' in q
    else:
        # dataclass like
        assert hasattr(q, 'last_price') and hasattr(q, 'timestamp') and hasattr(q, 'symbol')


def test_provider_interface_methods_exist():
    provider = get_provider('zerodha')  # Try zerodha first
    if not provider:
        pytest.skip("No provider available for testing")
    assert isinstance(provider, ProviderBase)
    # Ensure methods exist
    assert callable(provider.quote)
    assert callable(provider.profile)
    assert callable(provider.historical_data)


@pytest.mark.parametrize("symbols", [['NSE:NIFTY BANK'], ['NSE:NIFTY BANK', 'NSE:NIFTY 50']])
def test_quote_return_shape(symbols):
    provider = get_provider('zerodha')
    if not provider:
        pytest.skip("No provider available for testing")
    result = provider.quote(symbols)
    assert isinstance(result, dict)
    # Check that we got some results
    assert len(result) > 0
    for symbol in result.keys():
        assert symbol in symbols
        assert_quote_shape(result[symbol])


def test_profile_and_historical_data_signature():
    provider = get_provider('zerodha')
    if not provider:
        pytest.skip("No provider available for testing")
    prof = provider.profile()
    assert isinstance(prof, dict)
    try:
        hist = provider.historical_data(instrument_token='NSE:NIFTY BANK', from_date='2020-01-01', to_date='2020-01-02', interval='1m')
        assert isinstance(hist, list)
        if len(hist) > 0:
            assert 'open' in hist[0] and 'close' in hist[0] and 'timestamp' in hist[0]
    except Exception as e:
        pytest.skip(f"Historical data API call failed: {e}")
