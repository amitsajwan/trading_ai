import types

from market_data.runner import check_zerodha_credentials


def test_prompt_login_success(monkeypatch):
    # Simulate no pre-existing credentials
    class FakeSvc:
        def __init__(self):
            self.prompted = False
        def load_credentials(self):
            return None
        def is_token_valid(self, creds):
            # valid only after interactive login
            return self.prompted
        def trigger_interactive_login(self, timeout=300):
            self.prompted = True
            return True

    fake_mod = types.SimpleNamespace(KiteAuthService=lambda: FakeSvc())
    monkeypatch.setitem(__import__('sys').modules, 'market_data.tools.kite_auth_service', fake_mod)

    ok, msg = check_zerodha_credentials(prompt_login=True)
    assert ok is True
    assert msg is None


def test_prompt_login_failure(monkeypatch):
    class FakeSvc:
        def __init__(self):
            self.prompted = False
        def load_credentials(self):
            return None
        def is_token_valid(self, creds):
            return False
        def trigger_interactive_login(self, timeout=300):
            self.prompted = True
            return False

    fake_mod = types.SimpleNamespace(KiteAuthService=lambda: FakeSvc())
    monkeypatch.setitem(__import__('sys').modules, 'market_data.tools.kite_auth_service', fake_mod)

    ok, msg = check_zerodha_credentials(prompt_login=True)
    assert ok is False
    assert 'No valid' in msg
