import pytest


def test_depth_collector_prefers_futures_when_configured(monkeypatch):
    from data.depth_collector import DepthCollector

    class Kite:
        def instruments(self, exch):
            if exch == "NSE":
                return [{"tradingsymbol": "NIFTY BANK", "instrument_token": 26009}]
            if exch == "NFO":
                return [
                    {"segment": "NFO-FUT", "instrument_type": "FUT", "tradingsymbol": "BANKNIFTY26JANFUT", "instrument_token": 999, "expiry": __import__("datetime").date(2026,1,26)},
                ]
            return []

    class MM:
        pass

    # Force settings.instrument_exchange = NFO
    import types
    settings = types.SimpleNamespace(instrument_exchange="NFO", instrument_symbol="NIFTY BANK")

    import data.depth_collector as mod
    monkeypatch.setattr(mod, "settings", settings, raising=False)

    dc = DepthCollector(Kite(), MM())
    token = dc._resolve_token()
    assert token == 999
