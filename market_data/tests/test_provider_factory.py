import os
import pytest
from market_data.providers.factory import get_provider


def test_get_provider_zerodha_env(monkeypatch):
    monkeypatch.setenv("TRADING_PROVIDER", "zerodha")
    p = get_provider()
    if p is None:
        pytest.skip("No Zerodha credentials available")
    assert p.__class__.__name__.lower().startswith("zerodha")


def test_get_provider_explicit_zerodha():
    p = get_provider("zerodha")
    if p is None:
        pytest.skip("No Zerodha credentials available")
    assert p.__class__.__name__.lower().startswith("zerodha")


def test_get_provider_none_when_no_creds(monkeypatch):
    # Mock no credentials available
    from market_data.providers.zerodha import ZerodhaProvider
    monkeypatch.setattr(ZerodhaProvider, 'from_credentials_file', lambda: None)
    p = get_provider()
    assert p is None
