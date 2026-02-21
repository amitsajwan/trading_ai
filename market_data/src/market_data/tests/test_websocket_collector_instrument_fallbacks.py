from market_data.collectors.websocket_tick_collector import WebSocketTickCollector


def test_find_token_in_rows_matches_symbol_case_insensitive():
    rows = [
        {"tradingsymbol": "NIFTY26FEBFUT", "instrument_token": 15150594},
        {"tradingsymbol": "BANKNIFTY26MARFUT", "instrument_token": 13235458},
    ]

    token = WebSocketTickCollector._find_token_in_rows(rows, "banknifty26marfut")
    assert token == "13235458"


def test_resolve_token_via_quote_fallback():
    collector = WebSocketTickCollector.__new__(WebSocketTickCollector)

    class _FakeKite:
        def quote(self, symbols):
            assert symbols == ["NFO:BANKNIFTY26MARFUT"]
            return {"NFO:BANKNIFTY26MARFUT": {"instrument_token": 13235458}}

        def ltp(self, symbols):
            return {}

    collector.kite = _FakeKite()
    token = collector._resolve_token_via_quote("BANKNIFTY26MARFUT")
    assert token == "13235458"


def test_instruments_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("KITE_INSTRUMENTS_CACHE_DIR", str(tmp_path))
    collector = WebSocketTickCollector.__new__(WebSocketTickCollector)
    rows = [{"tradingsymbol": "BANKNIFTY26MARFUT", "instrument_token": 13235458}]

    collector._save_instruments_cache("NFO", rows)
    loaded = collector._load_instruments_cache("NFO", ttl_seconds=86400)
    assert loaded == rows

