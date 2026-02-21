from market_data import runtime


def test_resolve_kite_credentials_prefers_file_over_env(monkeypatch):
    monkeypatch.setenv("KITE_API_KEY", "env-key")
    monkeypatch.setenv("KITE_ACCESS_TOKEN", "env-token")
    creds = {"api_key": "file-key", "access_token": "file-token"}

    api_key, access_token, source = runtime._resolve_kite_credentials(
        creds=creds, prefer_env=False
    )

    assert api_key == "file-key"
    assert access_token == "file-token"
    assert source == "credentials"


def test_build_collector_env_overrides_stale_env_with_file_creds(monkeypatch):
    monkeypatch.setattr(
        runtime,
        "_load_credentials_from_candidates",
        lambda require_valid=False: (
            {"api_key": "file-key", "access_token": "file-token"},
            object(),
        ),
    )

    out = runtime.build_collector_env(
        {
            "KITE_API_KEY": "stale-env-key",
            "KITE_ACCESS_TOKEN": "stale-env-token",
        }
    )

    assert out["KITE_API_KEY"] == "file-key"
    assert out["KITE_ACCESS_TOKEN"] == "file-token"


def test_kite_startup_preflight_uses_file_creds_when_env_differs(monkeypatch):
    monkeypatch.setenv("KITE_API_KEY", "stale-env-key")
    monkeypatch.setenv("KITE_ACCESS_TOKEN", "stale-env-token")
    monkeypatch.setattr(
        runtime,
        "_load_credentials_from_candidates",
        lambda require_valid=False: (
            {"api_key": "file-key", "access_token": "file-token"},
            object(),
        ),
    )

    called = {}

    class _FakeKite:
        def profile(self):
            return {"user_id": "U1"}

    def _fake_create_kite_client(api_key: str, access_token: str):
        called["api_key"] = api_key
        called["access_token"] = access_token
        return _FakeKite()

    monkeypatch.setattr(runtime, "create_kite_client", _fake_create_kite_client)

    ok, reason, _ = runtime.kite_startup_preflight(attempts=1, base_delay_sec=0)
    assert ok is True
    assert reason == "ok"
    assert called["api_key"] == "file-key"
    assert called["access_token"] == "file-token"

