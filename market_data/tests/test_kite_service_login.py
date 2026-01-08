import time
from pathlib import Path
from datetime import datetime, timedelta
import pytest

from kite_auth_service import KiteAuthService


def test_trigger_interactive_login_calls_helper(monkeypatch, tmp_path):
    # Prepare service
    monkeypatch.chdir(tmp_path)
    service = KiteAuthService(cred_path=str(Path(tmp_path) / "credentials.json"))

    called = {}

    def fake_login_via_browser(api_key=None, api_secret=None, force_mode=False, timeout=300):
        called['args'] = (api_key, api_secret, force_mode, timeout)
        creds = {
            'api_key': api_key or 'k',
            'access_token': 'token123',
            'data': {'login_time': datetime.now().isoformat()}
        }
        return creds, 0

    monkeypatch.setattr('market_data.tools.kite_auth.login_via_browser', fake_login_via_browser)

    saved = {}

    def fake_save(creds):
        saved['creds'] = creds
        Path(service.cred_path).write_text('{}')
        return True

    monkeypatch.setattr(service, 'save_credentials', fake_save)

    assert service.trigger_interactive_login(timeout=1) is True
    assert 'creds' in saved
    assert called


def test_trigger_interactive_login_fallback_subprocess(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    service = KiteAuthService(cred_path=str(Path(tmp_path) / "credentials.json"))

    # Make subprocess write the file after a short delay
    def fake_popen(cmd):
        class P:
            def __init__(self):
                pass
            def terminate(self):
                pass
        # Spawn a tiny background writer
        def writer():
            time.sleep(0.2)
            Path(service.cred_path).write_text('{}')
        import threading
        threading.Thread(target=writer, daemon=True).start()
        return P()

    monkeypatch.setattr('subprocess.Popen', fake_popen)

    assert service.trigger_interactive_login(timeout=2) is True
