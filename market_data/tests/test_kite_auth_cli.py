import os
from pathlib import Path
from market_data.tools.kite_auth import login_via_browser


def test_login_fails_without_env(monkeypatch, tmp_path):
    # Ensure no API keys in env
    monkeypatch.delenv("KITE_API_KEY", raising=False)
    monkeypatch.delenv("KITE_API_SECRET", raising=False)

    # Run in an isolated temp dir
    monkeypatch.chdir(tmp_path)
    creds, code = login_via_browser()

    assert creds is None
    assert code == 1


def test_verify_mode_with_invalid_creds(monkeypatch, tmp_path):
    # Provide dummy API key/secret but credentials file without token
    monkeypatch.setenv("KITE_API_KEY", "dummykey")
    monkeypatch.setenv("KITE_API_SECRET", "dummysecret")
    monkeypatch.chdir(tmp_path)

    # Create credentials.json with no access_token
    Path("credentials.json").write_text('{}')

    creds, code = login_via_browser(verify_mode=True)

    assert creds is None
    assert code == 1
