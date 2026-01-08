import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

import pytest

from market_data.tools import kite_auth


def test_is_token_valid_valid():
    creds = {
        "access_token": "tok",
        "data": {"login_time": datetime.now().isoformat()}
    }
    assert kite_auth.CredentialsValidator.is_token_valid(creds)


def test_is_token_valid_expired():
    creds = {
        "access_token": "tok",
        "data": {"login_time": (datetime.now() - timedelta(days=2)).isoformat()}
    }
    assert not kite_auth.CredentialsValidator.is_token_valid(creds)


def test_verify_credentials_monkeypatched(monkeypatch):
    class MockKite:
        def __init__(self, api_key):
            pass
        def set_access_token(self, tok):
            self.tok = tok
        def profile(self):
            return {"user_id": "user123"}

    monkeypatch.setattr(kite_auth, "KiteConnect", MockKite)

    assert kite_auth.CredentialsValidator.verify_credentials("key", "tok") is True


def test_main_verify_mode_with_existing_creds(tmp_path, monkeypatch):
    # Create a temp credentials.json
    creds = {
        "api_key": "k",
        "api_secret": "s",
        "access_token": "tok",
        "data": {"login_time": datetime.now().isoformat()}
    }
    tmp_file = tmp_path / "credentials.json"
    tmp_file.write_text(json.dumps(creds))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KITE_API_KEY", "k")
    monkeypatch.setenv("KITE_API_SECRET", "s")

    # Patch verification to avoid external calls
    monkeypatch.setattr(kite_auth.CredentialsValidator, "verify_credentials", staticmethod(lambda api_key, token: True))

    monkeypatch.setattr(sys, "argv", ["prog", "--verify"])
    res = kite_auth.main()
    assert res == 0

