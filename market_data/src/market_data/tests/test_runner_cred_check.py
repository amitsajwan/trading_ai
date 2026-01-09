import os

from market_data.runner import check_zerodha_credentials


def test_check_zerodha_no_creds(monkeypatch):
    # Ensure no env vars and no credentials file (KiteAuthService.load_credentials returns None)
    monkeypatch.delenv('KITE_API_KEY', raising=False)
    monkeypatch.delenv('KITE_ACCESS_TOKEN', raising=False)

    # Monkeypatch KiteAuthService to simulate no creds
    class FakeSvc:
        def load_credentials(self):
            return None
        def is_token_valid(self, creds):
            return False
    monkeypatch.setitem(__import__('sys').modules, 'market_data.tools.kite_auth_service', __import__('types').SimpleNamespace(KiteAuthService=lambda: FakeSvc()))

    ok, msg = check_zerodha_credentials()
    assert ok is False
    assert 'No valid' in msg


def test_check_zerodha_with_env(monkeypatch):
    # Simulate env vars set
    monkeypatch.setenv('KITE_API_KEY', 'dummy')
    monkeypatch.setenv('KITE_ACCESS_TOKEN', 'token')

    class FakeSvc:
        def load_credentials(self):
            return None
        def is_token_valid(self, creds):
            # Return True when access_token matches 'token'
            return creds.get('data', {}).get('access_token') == 'token'

    monkeypatch.setitem(__import__('sys').modules, 'market_data.tools.kite_auth_service', __import__('types').SimpleNamespace(KiteAuthService=lambda: FakeSvc()))

    ok, msg = check_zerodha_credentials()
    assert ok is True
