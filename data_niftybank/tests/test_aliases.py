import pytest

from data_niftybank.aliases import normalize_instrument, canonical_instruments


def test_canonical_symbols_present():
    assert set(canonical_instruments) == {"BANKNIFTY", "NIFTY"}


def test_normalize_banknifty_variants():
    variants = ["Bank Nifty", "NIFTY BANK", "banknifty", "nse:banknifty", "NIFTYBANK"]
    for symbol in variants:
        assert normalize_instrument(symbol) == "BANKNIFTY"


def test_normalize_nifty_variants():
    variants = ["Nifty", "NIFTY 50", "nifty50", "NSE:NIFTY", "nsei"]
    for symbol in variants:
        assert normalize_instrument(symbol) == "NIFTY"


def test_unsupported_symbol_raises():
    with pytest.raises(ValueError):
        normalize_instrument("DOWJONES")
