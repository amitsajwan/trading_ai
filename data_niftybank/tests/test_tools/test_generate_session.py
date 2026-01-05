import json
from pathlib import Path

import pytest

from data_niftybank.tools.generate_session import *


class MockKite:
    def __init__(self, api_key):
        pass
    def generate_session(self, request_token, api_secret=None):
        return {"access_token": "abc123", "user_id": "u1", "login_time": "2026-01-05T00:00:00"}
    def set_access_token(self, tok):
        self.tok = tok


def test_generate_session_writes_credentials(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KITE_API_KEY", "k")
    monkeypatch.setenv("KITE_API_SECRET", "s")

    monkeypatch.setattr(generate_session, "KiteConnect", MockKite)

    # Provide a dummy request token via input
    monkeypatch.setattr("builtins.input", lambda prompt='': "rtok")

    generate_session.main()

    out = Path("credentials.json")
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["access_token"] == "abc123"
    assert data["user_id"] == "u1"
