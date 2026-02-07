import pytest

from market_data.aliases import normalize_instrument, canonical_instruments


def test_canonical_symbols_present():
    assert set(canonical_instruments) == {"BANKNIFTY", "NIFTY"}


def test_normalize_banknifty_variants():
    variants = ["Bank Nifty", "NIFTY BANK", "banknifty", "nse:banknifty", "NIFTYBANK"]
    for symbol in variants:
        assert normalize_instrument(symbol) == "BANKNIFTY"


def test_normalize_futures_symbols():
    futures_symbols = ["BANKNIFTY26JANFUT", "NIFTY26JANFUT", "BANKNIFTY27FEBFUT"]
    for symbol in futures_symbols:
        assert normalize_instrument(symbol) == symbol


def test_unsupported_symbol_raises():
    with pytest.raises(ValueError):
        normalize_instrument("DOWJONES")

